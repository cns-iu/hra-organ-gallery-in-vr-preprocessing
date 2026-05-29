#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import requests
import trimesh
from trimesh.visual.material import PBRMaterial


# ---------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------

DEFAULT_NUM_NODES = 5000

DEFAULT_INPUT_GLB = Path("10_organs/downloaded_organs/3d-vh-f-heart.glb")
DEFAULT_OUTPUT_FOLDER = Path("10_organs/amended_organs")

DEFAULT_TARGET_STRUCTURE = "right_ventricle"

DEFAULT_HRA_SCENE_NODE = "auto"
DEFAULT_HRA_REFERENCE_ORGAN_GLB_URL = "auto"

DEFAULT_REFERENCE_ORGANS_API_URL = (
    "https://apps.humanatlas.io/api--staging/v1/reference-organs"
)

DEFAULT_HRA_3D_CELL_API_URL = (
    "https://apps.humanatlas.io/api/v1/mesh-3d-cell-population"
)

DEFAULT_HRA_POP_API_URL = (
    "https://apps.humanatlas.io/api/grlc/hra-pop/"
    "cell_types_in_anatomical_structurescts_per_as"
)

DEFAULT_HRA_ORGAN_FILTER = "heart"
DEFAULT_HRA_AS_FILTER = "right ventricle"
DEFAULT_HRA_TOOL_FILTER = "Azimuth"
DEFAULT_HRA_SEX_FILTER = "Female"
DEFAULT_HRA_MODALITY_FILTER = ""

# Raw cache CSVs are disabled by default so `python hra_to_heart.py` works
# without file-lock / permission issues.
DEFAULT_HRA_POP_RAW_CSV_OUTPUT = ""
DEFAULT_API_GENERATED_CELL_CSV_OUTPUT = ""

DEFAULT_ORGAN_ALPHA = 35

DEFAULT_MARKER_SHAPE = "sphere"
DEFAULT_SPHERE_RADIUS = 0.0005
DEFAULT_SPHERE_SUBDIVISIONS = 2
DEFAULT_MARKER_SIZE = None

# Keep only this many cell types as explicit categories.
# All remaining cell types are grouped into "Other".
DEFAULT_TOP_CELL_TYPE_COUNT = 9
OTHER_CELL_TYPE_LABEL = "Other"

NODE_PARENT_NAME = "hra_generated_cell_node"


# ---------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate visible cell markers in a local HRA organ GLB using "
            "HRApop/Azimuth cell-type distributions and the HRA 3D Cell "
            "Generation API for coordinates."
        )
    )

    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_GLB)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--csv-output", type=Path, default=None)

    parser.add_argument(
        "--target-structure",
        type=str,
        default=DEFAULT_TARGET_STRUCTURE,
    )

    parser.add_argument(
        "--num-nodes",
        type=int,
        default=DEFAULT_NUM_NODES,
    )

    parser.add_argument(
        "--marker-shape",
        type=str,
        choices=["sphere", "cube", "triangle"],
        default=DEFAULT_MARKER_SHAPE,
    )

    parser.add_argument(
        "--sphere-radius",
        type=float,
        default=DEFAULT_SPHERE_RADIUS,
    )

    parser.add_argument(
        "--marker-size",
        type=float,
        default=DEFAULT_MARKER_SIZE,
    )

    parser.add_argument(
        "--sphere-subdivisions",
        type=int,
        default=DEFAULT_SPHERE_SUBDIVISIONS,
    )

    parser.add_argument(
        "--organ-alpha",
        type=int,
        default=DEFAULT_ORGAN_ALPHA,
    )

    parser.add_argument("--hra-pop-csv", type=Path, default=None)
    parser.add_argument("--hra-pop-api-url", type=str, default=DEFAULT_HRA_POP_API_URL)

    parser.add_argument(
        "--download-hra-pop-csv",
        type=str,
        default=DEFAULT_HRA_POP_RAW_CSV_OUTPUT,
        help=(
            "Path where the raw downloaded HRApop table is saved. "
            "Use an empty string to disable cache writing. Default: disabled."
        ),
    )

    parser.add_argument("--hra-organ-filter", type=str, default=DEFAULT_HRA_ORGAN_FILTER)
    parser.add_argument("--hra-as-filter", type=str, default=DEFAULT_HRA_AS_FILTER)
    parser.add_argument("--hra-tool-filter", type=str, default=DEFAULT_HRA_TOOL_FILTER)
    parser.add_argument("--hra-sex-filter", type=str, default=DEFAULT_HRA_SEX_FILTER)
    parser.add_argument("--hra-modality-filter", type=str, default=DEFAULT_HRA_MODALITY_FILTER)

    parser.add_argument(
        "--top-cell-type-count",
        type=int,
        default=DEFAULT_TOP_CELL_TYPE_COUNT,
        help=(
            "Number of highest-weight HRApop cell types to preserve individually. "
            f"All remaining cell types become {OTHER_CELL_TYPE_LABEL!r}. "
            f"Default: {DEFAULT_TOP_CELL_TYPE_COUNT}."
        ),
    )

    parser.add_argument(
        "--hra-reference-organ-glb-url",
        type=str,
        default=DEFAULT_HRA_REFERENCE_ORGAN_GLB_URL,
    )

    parser.add_argument(
        "--reference-organs-api-url",
        type=str,
        default=DEFAULT_REFERENCE_ORGANS_API_URL,
    )

    parser.add_argument(
        "--hra-scene-node",
        type=str,
        default=DEFAULT_HRA_SCENE_NODE,
    )

    parser.add_argument(
        "--hra-3d-cell-api-url",
        type=str,
        default=DEFAULT_HRA_3D_CELL_API_URL,
    )

    parser.add_argument(
        "--api-generated-cell-csv-output",
        type=str,
        default=DEFAULT_API_GENERATED_CELL_CSV_OUTPUT,
        help=(
            "CSV output path for the raw HRA 3D Cell Generation API response. "
            "Use an empty string to disable this raw cache CSV. Default: disabled."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------

def safe_name(value: str) -> str:
    cleaned = str(value).strip()

    replacements = [
        (" ", "_"),
        ("/", "_"),
        ("\\", "_"),
        (":", "_"),
        (";", "_"),
        (",", "_"),
        ("(", ""),
        (")", ""),
        ("[", ""),
        ("]", ""),
        ("{", ""),
        ("}", ""),
        ("|", "_"),
        ("+", "_"),
        ("*", "_"),
        ("?", "_"),
        ("\"", ""),
        ("'", ""),
        ("<", ""),
        (">", ""),
    ]

    for old, new in replacements:
        cleaned = cleaned.replace(old, new)

    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")

    return cleaned.strip("_")


def compact_ontology_id(value: str) -> str:
    """
    Converts common ontology IRI formats into compact IDs.

    Examples:
        http://purl.obolibrary.org/obo/CL_0000746 -> CL_0000746
        CL:0000746 -> CL_0000746
        CL_0000746 -> CL_0000746
    """
    text = str(value or "").strip()

    if text == "":
        return ""

    if "/" in text:
        text = text.rstrip("/").split("/")[-1]

    text = text.replace(":", "_")

    return safe_name(text)


def normalize_match_text(value: str) -> str:
    return (
        str(value)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("__", "_")
        .strip()
    )


def normalize_filter_text(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def normalize_cell_label_key(value: str) -> str:
    return normalize_filter_text(value)


def values_match_filter(value: object, filter_value: str) -> bool:
    normalized_filter = normalize_filter_text(filter_value)

    if normalized_filter == "":
        return True

    normalized_value = normalize_filter_text(value)
    return normalized_filter in normalized_value


def parse_float(value: object) -> float:
    if value is None:
        return 0.0

    text = str(value).strip()

    if text == "":
        return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


def make_default_output_paths(
    input_glb: Path,
    target_structure: str,
    marker_shape: str,
) -> Tuple[Path, Path]:
    target_name = safe_name(target_structure)
    input_stem = input_glb.stem

    base_name = f"{input_stem}-{target_name}-{marker_shape}-hra-pop"

    output_glb = DEFAULT_OUTPUT_FOLDER / f"{base_name}.glb"
    output_csv = DEFAULT_OUTPUT_FOLDER / f"{base_name}.csv"

    return output_glb, output_csv


# ---------------------------------------------------------------------
# GLB loading and target mesh selection
# ---------------------------------------------------------------------

def load_glb_as_scene(glb_path: Path) -> trimesh.Scene:
    loaded = trimesh.load(glb_path, force="scene")

    if isinstance(loaded, trimesh.Scene):
        return loaded

    if isinstance(loaded, trimesh.Trimesh):
        scene = trimesh.Scene()
        scene.add_geometry(loaded, node_name="reference_model")
        return scene

    raise TypeError(f"Unsupported GLB type: {type(loaded)}")


def print_available_mesh_nodes(scene: trimesh.Scene) -> None:
    print("Available mesh nodes:")

    for node_name in sorted(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph[node_name]
        geometry = scene.geometry[geometry_name]

        vertex_count = len(geometry.vertices) if hasattr(geometry, "vertices") else 0
        face_count = len(geometry.faces) if hasattr(geometry, "faces") else 0

        print(
            f"  node={node_name}, geometry={geometry_name}, "
            f"vertices={vertex_count}, faces={face_count}"
        )


def find_target_mesh_node(
    scene: trimesh.Scene,
    target_structure: str,
) -> Tuple[str, str, np.ndarray, trimesh.Trimesh]:
    target_normalized = normalize_match_text(target_structure)

    matches: List[Tuple[str, str, np.ndarray, trimesh.Trimesh]] = []

    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        geometry = scene.geometry[geometry_name]

        if not isinstance(geometry, trimesh.Trimesh):
            continue

        searchable = normalize_match_text(f"{node_name} {geometry_name}")

        if target_normalized in searchable:
            target_mesh = geometry.copy()
            target_mesh.apply_transform(transform)
            matches.append((node_name, geometry_name, transform, target_mesh))

    if not matches:
        print_available_mesh_nodes(scene)
        raise ValueError(
            f"Could not find a mesh node matching target structure: "
            f"{target_structure!r}"
        )

    if len(matches) > 1:
        print("Multiple matching structures were found. Using the first match:")

        for node_name, geometry_name, _, mesh in matches:
            print(
                f"  node={node_name}, geometry={geometry_name}, "
                f"vertices={len(mesh.vertices)}, faces={len(mesh.faces)}"
            )

    return matches[0]


# ---------------------------------------------------------------------
# Reference organ URL resolution
# ---------------------------------------------------------------------

def fetch_reference_organs(reference_organs_api_url: str) -> List[Dict[str, object]]:
    response = requests.get(reference_organs_api_url, timeout=120)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError("Reference organs API did not return a list.")

    return data


def resolve_reference_organ_glb_url(
    input_glb: Path,
    requested_url: str,
    reference_organs_api_url: str,
) -> str:
    if requested_url.strip().lower() != "auto":
        return requested_url

    input_filename = input_glb.name

    print(
        "Resolving HRA reference organ GLB URL from reference-organs API "
        f"using local filename: {input_filename}"
    )

    organs = fetch_reference_organs(reference_organs_api_url)

    for organ in organs:
        object_data = organ.get("object", {})

        if not isinstance(object_data, dict):
            continue

        file_url = str(object_data.get("file", "")).strip()

        if file_url.endswith("/" + input_filename) or file_url.endswith(input_filename):
            print(f"Resolved HRA reference organ GLB URL: {file_url}")
            return file_url

    raise ValueError(
        "Could not automatically resolve the HRA reference organ GLB URL for "
        f"local file {input_filename!r}. Pass it explicitly with "
        "--hra-reference-organ-glb-url."
    )


def resolve_hra_scene_node(
    requested_scene_node: str,
    matched_local_node_name: str,
) -> str:
    if requested_scene_node.strip().lower() == "auto":
        return matched_local_node_name

    return requested_scene_node


# ---------------------------------------------------------------------
# Transparency
# ---------------------------------------------------------------------

def make_existing_scene_meshes_transparent(
    scene: trimesh.Scene,
    alpha: int,
) -> None:
    if alpha < 0 or alpha > 255:
        raise ValueError("--organ-alpha must be between 0 and 255.")

    alpha_factor = float(alpha) / 255.0
    changed_count = 0

    for geometry_name, geometry in scene.geometry.items():
        if not isinstance(geometry, trimesh.Trimesh):
            continue

        if len(geometry.faces) == 0:
            continue

        base_rgb = np.array([190, 190, 190], dtype=np.uint8)

        try:
            face_colors = np.array(geometry.visual.face_colors, dtype=np.uint8)

            if (
                face_colors.ndim == 2
                and face_colors.shape[0] > 0
                and face_colors.shape[1] >= 3
            ):
                base_rgb = np.mean(face_colors[:, :3], axis=0).astype(np.uint8)
        except Exception:
            pass

        material = PBRMaterial(
            name=f"transparent_organ_{safe_name(geometry_name)}",
            baseColorFactor=[
                float(base_rgb[0]) / 255.0,
                float(base_rgb[1]) / 255.0,
                float(base_rgb[2]) / 255.0,
                alpha_factor,
            ],
            alphaMode="BLEND",
            doubleSided=True,
            metallicFactor=0.0,
            roughnessFactor=0.7,
        )

        geometry.visual = trimesh.visual.TextureVisuals(material=material)
        changed_count += 1

    print(f"Applied transparent PBR materials to organ meshes: {changed_count}")


def patch_glb_material_transparency(glb_path: Path) -> None:
    try:
        from pygltflib import GLTF2
    except ImportError:
        print(
            "Warning: pygltflib is not installed, so GLB material alphaMode "
            "could not be patched. Install it with: pip install pygltflib"
        )
        return

    gltf = GLTF2().load(str(glb_path))

    if not gltf.materials:
        print("No GLB materials found to patch.")
        return

    patched_count = 0

    for material in gltf.materials:
        material_name = material.name or ""

        if material_name.startswith("transparent_organ_"):
            material.alphaMode = "BLEND"
            material.doubleSided = True
            patched_count += 1

        if material_name.startswith("generated_cell_material_"):
            material.alphaMode = "OPAQUE"
            material.doubleSided = True

    gltf.save_binary(str(glb_path))

    print(f"Patched transparent GLB materials: {patched_count}")


# ---------------------------------------------------------------------
# HRApop loading and filtering
# ---------------------------------------------------------------------

def read_hra_pop_csv(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def fetch_url_bytes(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": accept,
            "User-Agent": "hra-organ-cell-marker-script/1.0",
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_hra_pop_rows(api_url: str) -> Tuple[List[Dict[str, str]], bytes]:
    errors: List[str] = []

    csv_url_candidates = [
        api_url,
        api_url + ".csv" if not api_url.endswith(".csv") else api_url,
        api_url + "?_format=csv" if "?" not in api_url else api_url + "&_format=csv",
    ]

    for url in csv_url_candidates:
        try:
            raw = fetch_url_bytes(url, accept="text/csv")
            decoded = raw.decode("utf-8-sig", errors="replace")

            reader = csv.DictReader(decoded.splitlines())
            rows = [dict(row) for row in reader]

            if rows and "cell_label" in rows[0]:
                return rows, raw

        except Exception as exc:
            errors.append(f"CSV attempt failed for {url}: {exc}")

    json_url_candidates = [
        api_url,
        api_url + ".json" if not api_url.endswith(".json") else api_url,
        api_url + "?_format=json" if "?" not in api_url else api_url + "&_format=json",
    ]

    for url in json_url_candidates:
        try:
            raw = fetch_url_bytes(url, accept="application/json")
            data = json.loads(raw.decode("utf-8", errors="replace"))

            if isinstance(data, list):
                rows = [dict(row) for row in data]
                return rows, raw

            if isinstance(data, dict):
                for key in ("results", "data", "rows"):
                    maybe_rows = data.get(key)

                    if isinstance(maybe_rows, list):
                        rows = [dict(row) for row in maybe_rows]
                        return rows, raw

        except Exception as exc:
            errors.append(f"JSON attempt failed for {url}: {exc}")

    joined_errors = "\n".join(errors)

    raise RuntimeError(
        "Could not fetch HRApop rows from the API. "
        "Export the endpoint as CSV and pass it with --hra-pop-csv.\n"
        f"Attempt details:\n{joined_errors}"
    )


def load_hra_pop_rows(
    hra_pop_csv: Optional[Path],
    api_url: str,
    download_hra_pop_csv: Optional[Path],
) -> List[Dict[str, str]]:
    if hra_pop_csv is not None:
        if not hra_pop_csv.exists():
            raise FileNotFoundError(f"Could not find HRApop CSV: {hra_pop_csv}")

        print(f"Loading HRApop CSV: {hra_pop_csv}")
        return read_hra_pop_csv(hra_pop_csv)

    print(f"Fetching HRApop data from: {api_url}")
    rows, raw = fetch_hra_pop_rows(api_url)

    if download_hra_pop_csv is not None:
        try:
            download_hra_pop_csv.parent.mkdir(parents=True, exist_ok=True)
            download_hra_pop_csv.write_bytes(raw)
            print(f"Saved downloaded HRApop response to: {download_hra_pop_csv}")
        except PermissionError:
            print(
                "Warning: Could not write downloaded HRApop CSV cache because "
                f"the file is locked or permission was denied: {download_hra_pop_csv}"
            )
            print("Continuing without updating the HRApop cache file.")
        except OSError as exc:
            print(
                "Warning: Could not write downloaded HRApop CSV cache: "
                f"{download_hra_pop_csv}"
            )
            print(f"Reason: {exc}")
            print("Continuing without updating the HRApop cache file.")

    return rows


def filter_hra_pop_rows(
    rows: Iterable[Dict[str, str]],
    organ_filter: str,
    as_filter: str,
    tool_filter: str,
    sex_filter: str,
    modality_filter: str,
) -> List[Dict[str, str]]:
    filtered: List[Dict[str, str]] = []

    for row in rows:
        if not values_match_filter(row.get("organ", ""), organ_filter):
            continue

        if not values_match_filter(row.get("as_label", ""), as_filter):
            continue

        if not values_match_filter(row.get("tool", ""), tool_filter):
            continue

        if not values_match_filter(row.get("sex", ""), sex_filter):
            continue

        if not values_match_filter(row.get("modality", ""), modality_filter):
            continue

        filtered.append(row)

    return filtered


def summarize_available_hra_pop_matches(
    rows: Iterable[Dict[str, str]],
    organ_filter: str,
    as_filter: str,
) -> None:
    print("Nearby HRApop rows matching organ/anatomical-structure filters:")

    count = 0

    for row in rows:
        if not values_match_filter(row.get("organ", ""), organ_filter):
            continue

        if not values_match_filter(row.get("as_label", ""), as_filter):
            continue

        print(
            "  "
            f"organ={row.get('organ', '')}, "
            f"as_label={row.get('as_label', '')}, "
            f"sex={row.get('sex', '')}, "
            f"tool={row.get('tool', '')}, "
            f"modality={row.get('modality', '')}, "
            f"cell_label={row.get('cell_label', '')}, "
            f"cell_count={row.get('cell_count', '')}, "
            f"cell_percentage={row.get('cell_percentage', '')}, "
            f"dataset_count={row.get('dataset_count', '')}"
        )

        count += 1

        if count >= 25:
            print("  ...")
            break

    if count == 0:
        print("  No nearby rows found.")


def build_distribution_from_hra_pop_rows(
    rows: List[Dict[str, str]],
) -> Dict[str, float]:
    distribution: Dict[str, float] = {}

    for row in rows:
        cell_label = str(row.get("cell_label", "")).strip()

        if cell_label == "":
            continue

        cell_count = parse_float(row.get("cell_count", ""))
        cell_percentage = parse_float(row.get("cell_percentage", ""))

        weight = cell_count if cell_count > 0 else cell_percentage

        if weight <= 0:
            continue

        distribution[cell_label] = distribution.get(cell_label, 0.0) + weight

    if not distribution:
        raise ValueError(
            "No usable HRApop cell distribution could be built from the filtered rows."
        )

    return distribution


def collapse_distribution_to_top_n_plus_other(
    distribution: Dict[str, float],
    top_n: int,
    other_label: str = OTHER_CELL_TYPE_LABEL,
) -> Tuple[Dict[str, float], List[str], List[str]]:
    if top_n <= 0:
        raise ValueError("--top-cell-type-count must be greater than zero.")

    sorted_items = sorted(
        distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_items = sorted_items[:top_n]
    other_items = sorted_items[top_n:]

    collapsed: Dict[str, float] = dict(top_items)

    other_weight = float(sum(weight for _, weight in other_items))

    if other_weight > 0:
        collapsed[other_label] = other_weight

    top_labels = [label for label, _ in top_items]
    other_labels = [label for label, _ in other_items]

    return collapsed, top_labels, other_labels


def build_cell_label_to_cell_id_map(
    filtered_rows: List[Dict[str, str]],
    top_cell_labels: List[str],
) -> Dict[str, str]:
    """
    Builds a lookup from HRApop cell_label to compact cell_id.

    Only top cell labels are included. "Other" intentionally has no cell_id.
    """
    allowed_keys = {
        normalize_cell_label_key(label)
        for label in top_cell_labels
    }

    cell_label_to_cell_id: Dict[str, str] = {}

    for row in filtered_rows:
        cell_label = str(row.get("cell_label", "")).strip()
        cell_id = str(row.get("cell_id", "")).strip()

        if cell_label == "" or cell_id == "":
            continue

        key = normalize_cell_label_key(cell_label)

        if key not in allowed_keys:
            continue

        if key not in cell_label_to_cell_id:
            cell_label_to_cell_id[key] = compact_ontology_id(cell_id)

    return cell_label_to_cell_id


def get_cell_id_for_cell_type(
    cell_type: str,
    cell_label_to_cell_id: Dict[str, str],
) -> str:
    key = normalize_cell_label_key(cell_type)
    return cell_label_to_cell_id.get(key, "")


def make_generated_node_name(
    cell_type: str,
    cell_label_to_cell_id: Dict[str, str],
    fallback_index: int,
) -> str:
    clean_cell_type = safe_name(cell_type)

    if normalize_cell_label_key(cell_type) == normalize_cell_label_key(OTHER_CELL_TYPE_LABEL):
        return OTHER_CELL_TYPE_LABEL

    cell_id = get_cell_id_for_cell_type(
        cell_type=cell_type,
        cell_label_to_cell_id=cell_label_to_cell_id,
    )

    if cell_id != "":
        return f"{cell_id}_{clean_cell_type}"

    return f"generated_cell_{fallback_index:05d}_{clean_cell_type}"


def write_hra_pop_distribution_csv(
    csv_output_path: Path,
    collapsed_distribution: Dict[str, float],
    original_distribution: Dict[str, float],
    filtered_rows: List[Dict[str, str]],
    top_cell_labels: List[str],
    other_cell_labels: List[str],
) -> None:
    csv_output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_by_label: Dict[str, List[Dict[str, str]]] = {}

    for row in filtered_rows:
        label = str(row.get("cell_label", "")).strip()
        rows_by_label.setdefault(label, []).append(row)

    with csv_output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "output_cell_label",
                "is_other_group",
                "source_cell_label",
                "distribution_weight",
                "source_distribution_weight",
                "cell_id",
                "compact_cell_id",
                "organ",
                "organ_id",
                "as",
                "as_label",
                "sex",
                "tool",
                "modality",
                "cell_count",
                "cell_percentage",
                "dataset_count",
            ]
        )

        for cell_label, weight in sorted(
            collapsed_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            if cell_label == OTHER_CELL_TYPE_LABEL:
                for source_label in other_cell_labels:
                    matching_rows = rows_by_label.get(source_label, [])

                    if not matching_rows:
                        writer.writerow(
                            [
                                OTHER_CELL_TYPE_LABEL,
                                True,
                                source_label,
                                collapsed_distribution[OTHER_CELL_TYPE_LABEL],
                                original_distribution.get(source_label, 0.0),
                            ]
                        )
                        continue

                    for row in matching_rows:
                        source_cell_id = row.get("cell_id", "")

                        writer.writerow(
                            [
                                OTHER_CELL_TYPE_LABEL,
                                True,
                                source_label,
                                collapsed_distribution[OTHER_CELL_TYPE_LABEL],
                                original_distribution.get(source_label, 0.0),
                                source_cell_id,
                                compact_ontology_id(source_cell_id),
                                row.get("organ", ""),
                                row.get("organ_id", ""),
                                row.get("as", ""),
                                row.get("as_label", ""),
                                row.get("sex", ""),
                                row.get("tool", ""),
                                row.get("modality", ""),
                                row.get("cell_count", ""),
                                row.get("cell_percentage", ""),
                                row.get("dataset_count", ""),
                            ]
                        )

                continue

            matching_rows = rows_by_label.get(cell_label, [])

            if not matching_rows:
                writer.writerow(
                    [
                        cell_label,
                        False,
                        cell_label,
                        weight,
                        original_distribution.get(cell_label, 0.0),
                    ]
                )
                continue

            for row in matching_rows:
                cell_id = row.get("cell_id", "")

                writer.writerow(
                    [
                        cell_label,
                        False,
                        cell_label,
                        weight,
                        original_distribution.get(cell_label, 0.0),
                        cell_id,
                        compact_ontology_id(cell_id),
                        row.get("organ", ""),
                        row.get("organ_id", ""),
                        row.get("as", ""),
                        row.get("as_label", ""),
                        row.get("sex", ""),
                        row.get("tool", ""),
                        row.get("modality", ""),
                        row.get("cell_count", ""),
                        row.get("cell_percentage", ""),
                        row.get("dataset_count", ""),
                    ]
                )


# ---------------------------------------------------------------------
# Distribution utilities
# ---------------------------------------------------------------------

def normalize_distribution(distribution: Dict[str, float]) -> Tuple[List[str], np.ndarray]:
    labels = list(distribution.keys())
    weights = np.array([distribution[label] for label in labels], dtype=float)

    if not labels:
        raise ValueError("Cell type distribution is empty.")

    if np.any(weights < 0):
        raise ValueError("Cell type distribution cannot contain negative values.")

    total = float(np.sum(weights))

    if total <= 0:
        raise ValueError("Cell type distribution must contain at least one positive value.")

    probabilities = weights / total

    return labels, probabilities


def normalize_distribution_to_dict(distribution: Dict[str, float]) -> Dict[str, float]:
    labels, probabilities = normalize_distribution(distribution)

    return {
        label: float(probability)
        for label, probability in zip(labels, probabilities)
    }


def print_distribution_summary(distribution: Dict[str, float]) -> None:
    labels, probabilities = normalize_distribution(distribution)

    rows = sorted(
        zip(labels, probabilities),
        key=lambda item: item[1],
        reverse=True,
    )

    print("Collapsed cell distribution used for 3D Cell Generation API request:")

    for label, probability in rows:
        print(f"  {label}: {probability:.6f}")


def print_other_group_summary(other_cell_labels: List[str]) -> None:
    print(f"Cell labels grouped into {OTHER_CELL_TYPE_LABEL!r}:")

    if not other_cell_labels:
        print("  None")
        return

    for label in other_cell_labels:
        print(f"  {label}")


# ---------------------------------------------------------------------
# HRA 3D Cell Generation API
# ---------------------------------------------------------------------

def call_3d_cell_api(
    api_url: str,
    file: str,
    scene_node: str,
    num_nodes: int,
    node_distribution: Dict[str, float],
) -> Tuple[np.ndarray, List[str], str]:
    payload = {
        "file": file,
        "file_subpath": scene_node,
        "num_nodes": num_nodes,
        "node_distribution": node_distribution,
    }

    response = requests.post(
        api_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=300,
    )

    response.raise_for_status()

    csv_text = response.text
    reader = csv.DictReader(StringIO(csv_text))
    rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("3D Cell Generation API returned no rows.")

    actual_columns = set(rows[0].keys())

    possible_cell_type_columns = [
        "Cell Type",
        "cell_type",
        "cell_label",
        "cellLabel",
    ]

    cell_type_column = None

    for candidate in possible_cell_type_columns:
        if candidate in actual_columns:
            cell_type_column = candidate
            break

    required_coordinate_columns = {"x", "y", "z"}

    if not required_coordinate_columns.issubset(actual_columns):
        raise ValueError(
            "3D Cell Generation API response did not contain expected coordinate columns. "
            f"Expected at least: {sorted(required_coordinate_columns)}. "
            f"Actual columns: {sorted(actual_columns)}."
        )

    if cell_type_column is None:
        raise ValueError(
            "3D Cell Generation API response did not contain an expected cell type column. "
            f"Expected one of: {possible_cell_type_columns}. "
            f"Actual columns: {sorted(actual_columns)}."
        )

    points = np.array(
        [
            [
                float(row["x"]),
                float(row["y"]),
                float(row["z"]),
            ]
            for row in rows
        ],
        dtype=float,
    )

    cell_types = [str(row[cell_type_column]) for row in rows]

    return points, cell_types, csv_text


# ---------------------------------------------------------------------
# Color and marker generation
# ---------------------------------------------------------------------

def build_cell_type_color_map(cell_types: List[str]) -> Dict[str, Tuple[int, int, int, int]]:
    """
    Assigns one color to each unique generated cell type.

    The first 9 colors are distinct category colors. "Other" has a single
    neutral color. If more categories are present, extra categories are assigned
    deterministic fallback colors.
    """
    palette: List[Tuple[int, int, int, int]] = [
        (230, 25, 75, 255),
        (60, 180, 75, 255),
        (0, 130, 200, 255),
        (245, 130, 48, 255),
        (145, 30, 180, 255),
        (70, 240, 240, 255),
        (240, 50, 230, 255),
        (210, 245, 60, 255),
        (250, 190, 190, 255),
    ]

    other_color = (170, 170, 170, 255)

    unique_cell_types = sorted(set(cell_types))
    non_other = [
        label
        for label in unique_cell_types
        if normalize_cell_label_key(label) != normalize_cell_label_key(OTHER_CELL_TYPE_LABEL)
    ]

    color_map: Dict[str, Tuple[int, int, int, int]] = {}

    for index, label in enumerate(non_other):
        if index < len(palette):
            color_map[label] = palette[index]
        else:
            seed = abs(hash(label)) % (2**32)
            rng = np.random.default_rng(seed)
            rgb = rng.integers(low=50, high=230, size=3)
            color_map[label] = (int(rgb[0]), int(rgb[1]), int(rgb[2]), 255)

    for label in unique_cell_types:
        if normalize_cell_label_key(label) == normalize_cell_label_key(OTHER_CELL_TYPE_LABEL):
            color_map[label] = other_color

    return color_map


def make_cell_type_material(
    marker_shape: str,
    cell_type: str,
    color_map: Dict[str, Tuple[int, int, int, int]],
) -> PBRMaterial:
    rgba = color_map.get(cell_type, (255, 255, 255, 255))

    return PBRMaterial(
        name=f"generated_cell_material_{safe_name(marker_shape)}_{safe_name(cell_type)}",
        baseColorFactor=[
            rgba[0] / 255.0,
            rgba[1] / 255.0,
            rgba[2] / 255.0,
            rgba[3] / 255.0,
        ],
        alphaMode="OPAQUE",
        doubleSided=True,
        metallicFactor=0.0,
        roughnessFactor=0.2,
    )


def make_marker_mesh(
    center: np.ndarray,
    marker_shape: str,
    sphere_radius: float,
    marker_size: Optional[float],
    sphere_subdivisions: int,
    cell_type: str,
    color_map: Dict[str, Tuple[int, int, int, int]],
) -> trimesh.Trimesh:
    if sphere_radius <= 0:
        raise ValueError("--sphere-radius must be greater than zero.")

    if sphere_subdivisions < 0:
        raise ValueError("--sphere-subdivisions must be greater than or equal to zero.")

    shape = marker_shape.lower().strip()
    size = marker_size if marker_size is not None else sphere_radius

    if size <= 0:
        raise ValueError("--marker-size must be greater than zero when supplied.")

    if shape == "sphere":
        mesh = trimesh.creation.icosphere(
            subdivisions=sphere_subdivisions,
            radius=sphere_radius,
        )

    elif shape == "cube":
        mesh = trimesh.creation.box(
            extents=(size, size, size)
        )

    elif shape == "triangle":
        mesh = trimesh.creation.cone(
            radius=size,
            height=size * 2.0,
            sections=3,
        )
        mesh.apply_translation([0.0, 0.0, -size])

    else:
        raise ValueError(f"Unsupported marker shape: {marker_shape!r}")

    mesh.apply_translation(center)

    mesh.visual = trimesh.visual.TextureVisuals(
        material=make_cell_type_material(
            marker_shape=shape,
            cell_type=cell_type,
            color_map=color_map,
        )
    )

    return mesh


def add_markers_to_scene(
    scene: trimesh.Scene,
    points: np.ndarray,
    cell_types: List[str],
    marker_shape: str,
    sphere_radius: float,
    marker_size: Optional[float],
    sphere_subdivisions: int,
    target_structure_name: str,
    cell_label_to_cell_id: Dict[str, str],
    color_map: Dict[str, Tuple[int, int, int, int]],
) -> List[str]:
    if len(points) != len(cell_types):
        raise ValueError("Point count and cell type count do not match.")

    generated_node_names: List[str] = []

    for index, (point, cell_type) in enumerate(zip(points, cell_types)):
        marker = make_marker_mesh(
            center=point,
            marker_shape=marker_shape,
            sphere_radius=sphere_radius,
            marker_size=marker_size,
            sphere_subdivisions=sphere_subdivisions,
            cell_type=cell_type,
            color_map=color_map,
        )

        generated_node_name = make_generated_node_name(
            cell_type=cell_type,
            cell_label_to_cell_id=cell_label_to_cell_id,
            fallback_index=index,
        )

        # If many generated nodes share the same cell_id + cell_type, the scene
        # node name still needs to be unique, so append the row index.
        unique_node_name = f"{generated_node_name}_{index:05d}"

        scene.add_geometry(
            marker,
            node_name=unique_node_name,
            geom_name=f"{unique_node_name}_geometry",
        )

        generated_node_names.append(unique_node_name)

    return generated_node_names


# ---------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------

def write_text_file_safely(
    output_path: Optional[Path],
    text: str,
    description: str,
) -> None:
    if output_path is None:
        return

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"Exported {description} to: {output_path}")

    except PermissionError:
        print(
            f"Warning: Could not write {description} because the file is locked "
            f"or permission was denied: {output_path}"
        )
        print(f"Continuing without updating {description}.")

    except OSError as exc:
        print(f"Warning: Could not write {description}: {output_path}")
        print(f"Reason: {exc}")
        print(f"Continuing without updating {description}.")


def export_scene_as_glb(scene: trimesh.Scene, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported = scene.export(file_type="glb")

    if isinstance(exported, bytes):
        output_path.write_bytes(exported)
    else:
        output_path.write_bytes(bytes(exported))

    patch_glb_material_transparency(output_path)


def write_nodes_csv(
    csv_output_path: Path,
    points: np.ndarray,
    cell_types: List[str],
    generated_node_names: List[str],
    target_node_name: str,
    target_geometry_name: str,
    distribution: Dict[str, float],
    source_api_url: str,
    source_file_url: str,
    source_scene_node: str,
    marker_shape: str,
    cell_label_to_cell_id: Dict[str, str],
    color_map: Dict[str, Tuple[int, int, int, int]],
) -> None:
    if len(points) != len(cell_types):
        raise ValueError("Point count and cell type count do not match.")

    if len(points) != len(generated_node_names):
        raise ValueError("Point count and generated node name count do not match.")

    csv_output_path.parent.mkdir(parents=True, exist_ok=True)

    total_weight = float(sum(distribution.values()))

    with csv_output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "index",
                "generated_node_name",
                "cell_id",
                "x",
                "y",
                "z",
                "cell_type",
                "cell_type_distribution_weight",
                "cell_type_distribution_probability",
                "color_r",
                "color_g",
                "color_b",
                "color_a",
                "target_node_name",
                "target_geometry_name",
                "marker_shape",
                "source_api_url",
                "source_file_url",
                "source_scene_node",
            ]
        )

        for index, (point, cell_type, generated_node_name) in enumerate(
            zip(points, cell_types, generated_node_names)
        ):
            weight = float(distribution.get(cell_type, 0.0))
            probability = weight / total_weight if total_weight > 0 else 0.0

            cell_id = get_cell_id_for_cell_type(
                cell_type=cell_type,
                cell_label_to_cell_id=cell_label_to_cell_id,
            )

            rgba = color_map.get(cell_type, (255, 255, 255, 255))

            writer.writerow(
                [
                    index,
                    generated_node_name,
                    cell_id,
                    float(point[0]),
                    float(point[1]),
                    float(point[2]),
                    cell_type,
                    weight,
                    probability,
                    rgba[0],
                    rgba[1],
                    rgba[2],
                    rgba[3],
                    target_node_name,
                    target_geometry_name,
                    marker_shape,
                    source_api_url,
                    source_file_url,
                    source_scene_node,
                ]
            )


def print_cell_type_summary(cell_types: List[str]) -> None:
    unique, counts = np.unique(np.array(cell_types), return_counts=True)

    print("Generated cell type counts from 3D Cell Generation API response:")

    for label, count in sorted(zip(unique, counts), key=lambda item: item[0]):
        print(f"  {label}: {count}")


def print_cell_id_mapping_summary(
    cell_label_to_cell_id: Dict[str, str],
) -> None:
    print("Top cell_label to cell_id mappings:")

    if not cell_label_to_cell_id:
        print("  No cell_id mappings found.")
        return

    for label_key, cell_id in sorted(cell_label_to_cell_id.items()):
        print(f"  {label_key}: {cell_id}")


def print_color_mapping_summary(
    color_map: Dict[str, Tuple[int, int, int, int]],
) -> None:
    print("Cell type color map:")

    for label, rgba in sorted(color_map.items()):
        print(f"  {label}: rgba{rgba}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    download_hra_pop_csv = (
        Path(args.download_hra_pop_csv)
        if str(args.download_hra_pop_csv).strip() != ""
        else None
    )

    api_generated_cell_csv_output = (
        Path(args.api_generated_cell_csv_output)
        if str(args.api_generated_cell_csv_output).strip() != ""
        else None
    )

    input_glb: Path = args.input

    if args.output is None or args.csv_output is None:
        default_output_glb, default_output_csv = make_default_output_paths(
            input_glb=input_glb,
            target_structure=args.target_structure,
            marker_shape=args.marker_shape,
        )

        output_glb = args.output if args.output is not None else default_output_glb
        output_csv = args.csv_output if args.csv_output is not None else default_output_csv
    else:
        output_glb = args.output
        output_csv = args.csv_output

    if not input_glb.exists():
        raise FileNotFoundError(f"Could not find input GLB: {input_glb}")

    if args.num_nodes <= 0:
        raise ValueError("--num-nodes must be greater than zero.")

    if args.top_cell_type_count <= 0:
        raise ValueError("--top-cell-type-count must be greater than zero.")

    if args.sphere_radius <= 0:
        raise ValueError("--sphere-radius must be greater than zero.")

    if args.marker_size is not None and args.marker_size <= 0:
        raise ValueError("--marker-size must be greater than zero when supplied.")

    print(f"Loading local GLB: {input_glb}")

    scene = load_glb_as_scene(input_glb)

    (
        target_node_name,
        target_geometry_name,
        target_transform,
        target_mesh,
    ) = find_target_mesh_node(
        scene=scene,
        target_structure=args.target_structure,
    )

    hra_scene_node = resolve_hra_scene_node(
        requested_scene_node=args.hra_scene_node,
        matched_local_node_name=target_node_name,
    )

    hra_reference_organ_glb_url = resolve_reference_organ_glb_url(
        input_glb=input_glb,
        requested_url=args.hra_reference_organ_glb_url,
        reference_organs_api_url=args.reference_organs_api_url,
    )

    bounds_min, bounds_max = target_mesh.bounds
    bounds_size = bounds_max - bounds_min

    make_existing_scene_meshes_transparent(
        scene=scene,
        alpha=args.organ_alpha,
    )

    print("Loading HRApop cell type distribution.")

    hra_rows = load_hra_pop_rows(
        hra_pop_csv=args.hra_pop_csv,
        api_url=args.hra_pop_api_url,
        download_hra_pop_csv=download_hra_pop_csv,
    )

    filtered_hra_rows = filter_hra_pop_rows(
        rows=hra_rows,
        organ_filter=args.hra_organ_filter,
        as_filter=args.hra_as_filter,
        tool_filter=args.hra_tool_filter,
        sex_filter=args.hra_sex_filter,
        modality_filter=args.hra_modality_filter,
    )

    if not filtered_hra_rows:
        summarize_available_hra_pop_matches(
            rows=hra_rows,
            organ_filter=args.hra_organ_filter,
            as_filter=args.hra_as_filter,
        )

        raise ValueError(
            "No HRApop rows matched the selected filters. "
            "Try changing --hra-organ-filter, --hra-as-filter, --hra-sex-filter, "
            "--hra-tool-filter, or --hra-modality-filter."
        )

    original_distribution = build_distribution_from_hra_pop_rows(
        rows=filtered_hra_rows,
    )

    collapsed_distribution, top_cell_labels, other_cell_labels = (
        collapse_distribution_to_top_n_plus_other(
            distribution=original_distribution,
            top_n=args.top_cell_type_count,
            other_label=OTHER_CELL_TYPE_LABEL,
        )
    )

    cell_label_to_cell_id = build_cell_label_to_cell_id_map(
        filtered_rows=filtered_hra_rows,
        top_cell_labels=top_cell_labels,
    )

    node_distribution = normalize_distribution_to_dict(collapsed_distribution)

    print(f"Input GLB: {input_glb}")
    print(f"Output GLB: {output_glb}")
    print(f"Output CSV: {output_csv}")
    print(f"Target structure search: {args.target_structure}")
    print(f"Matched local target node: {target_node_name}")
    print(f"Matched local target geometry: {target_geometry_name}")
    print(f"Target vertices: {len(target_mesh.vertices)}")
    print(f"Target faces: {len(target_mesh.faces)}")
    print(f"Target watertight: {target_mesh.is_watertight}")
    print(f"Target bounds min: {bounds_min}")
    print(f"Target bounds max: {bounds_max}")
    print(f"Target bounds size: {bounds_size}")
    print(f"Requested node count: {args.num_nodes}")
    print(f"Top cell type count: {args.top_cell_type_count}")
    print(f"Marker shape: {args.marker_shape}")
    print(f"Sphere radius: {args.sphere_radius}")
    print(f"Marker size: {args.marker_size}")
    print(f"Sphere subdivisions: {args.sphere_subdivisions}")
    print(f"Organ alpha: {args.organ_alpha}")
    print(f"HRApop rows loaded: {len(hra_rows)}")
    print(f"HRApop rows after filters: {len(filtered_hra_rows)}")
    print(f"HRApop organ filter: {args.hra_organ_filter}")
    print(f"HRApop AS filter: {args.hra_as_filter}")
    print(f"HRApop tool filter: {args.hra_tool_filter}")
    print(f"HRApop sex filter: {args.hra_sex_filter}")
    print(f"HRApop modality filter: {args.hra_modality_filter}")
    print(f"HRApop cache path: {download_hra_pop_csv}")
    print(f"HRA 3D Cell API URL: {args.hra_3d_cell_api_url}")
    print(f"HRA reference organ GLB URL: {hra_reference_organ_glb_url}")
    print(f"HRA scene node: {hra_scene_node}")
    print(f"Raw 3D Cell API CSV cache path: {api_generated_cell_csv_output}")

    print_distribution_summary(collapsed_distribution)
    print_other_group_summary(other_cell_labels)
    print_cell_id_mapping_summary(cell_label_to_cell_id)

    print("Calling HRA 3D Cell Generation API for coordinate generation.")

    points, cell_types, api_generated_csv_text = call_3d_cell_api(
        api_url=args.hra_3d_cell_api_url,
        file=hra_reference_organ_glb_url,
        scene_node=hra_scene_node,
        num_nodes=args.num_nodes,
        node_distribution=node_distribution,
    )

    if len(points) == 0:
        raise ValueError("No points were returned from the HRA 3D Cell Generation API.")

    print(f"3D Cell Generation API returned points: {len(points)}")

    write_text_file_safely(
        output_path=api_generated_cell_csv_output,
        text=api_generated_csv_text,
        description="raw 3D Cell Generation API CSV",
    )

    print_cell_type_summary(cell_types)

    color_map = build_cell_type_color_map(cell_types)

    print_color_mapping_summary(color_map)

    generated_node_names = add_markers_to_scene(
        scene=scene,
        points=points,
        cell_types=cell_types,
        marker_shape=args.marker_shape,
        sphere_radius=args.sphere_radius,
        marker_size=args.marker_size,
        sphere_subdivisions=args.sphere_subdivisions,
        target_structure_name=target_node_name,
        cell_label_to_cell_id=cell_label_to_cell_id,
        color_map=color_map,
    )

    export_scene_as_glb(scene, output_glb)

    print(f"Exported modified GLB to: {output_glb}")

    if output_csv is not None:
        write_nodes_csv(
            csv_output_path=output_csv,
            points=points,
            cell_types=cell_types,
            generated_node_names=generated_node_names,
            target_node_name=target_node_name,
            target_geometry_name=target_geometry_name,
            distribution=collapsed_distribution,
            source_api_url=args.hra_3d_cell_api_url,
            source_file_url=hra_reference_organ_glb_url,
            source_scene_node=hra_scene_node,
            marker_shape=args.marker_shape,
            cell_label_to_cell_id=cell_label_to_cell_id,
            color_map=color_map,
        )

        print(f"Exported generated node CSV to: {output_csv}")

        distribution_csv = output_csv.with_name(
            output_csv.stem + "_hra_pop_distribution.csv"
        )

        write_hra_pop_distribution_csv(
            csv_output_path=distribution_csv,
            collapsed_distribution=collapsed_distribution,
            original_distribution=original_distribution,
            filtered_rows=filtered_hra_rows,
            top_cell_labels=top_cell_labels,
            other_cell_labels=other_cell_labels,
        )

        print(f"Exported HRApop distribution CSV to: {distribution_csv}")


if __name__ == "__main__":
    main()