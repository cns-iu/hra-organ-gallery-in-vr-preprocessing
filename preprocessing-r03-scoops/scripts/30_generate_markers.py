#!/usr/bin/env python3
"""
30_generate_markers.py — Place 3D cell markers across all anatomical structures
of the organ GLB using the HRA 3D Cell Generation API, then export the enriched GLB.

Reads:  config.yaml
        Outputs/annotated_organs/<organ>/json/<stem>_distribution.json  (from script 20)
        Outputs/downloaded_organs/<glb_filename>                        (from script 10)
Writes: Outputs/annotated_organs/<organ>/glb/<stem>-<uberon>-all-as-<tool>-<shape>-hra-pop.glb
        Outputs/annotated_organs/<organ>/csv/<stem>-<uberon>-all-as-<tool>-<shape>-hra-pop.csv
"""

from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
import trimesh
from trimesh.visual.material import PBRMaterial

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    resolve_glb_filename,
    load_config,
    normalize_match_text,
    normalize_cell_label_key,
    safe_name,
    hex_to_rgb,
    hex_to_float,
    PALETTE,
    OTHERS,
)


# =============================================================================
# Filename helper
# =============================================================================

def build_output_stem(stem: str, uberon_id: str, tool_slug: str, shape: str) -> str:
    """
    Build the output filename stem including UBERON ID and tool.
    e.g. 3d-vh-f-heart-UBERON_0000948-all-as-azimuth-sphere-hra-pop
    """
    parts = [stem]
    if uberon_id:
        parts.append(uberon_id)
    parts += ["all-as", tool_slug, shape, "hra-pop"]
    return "-".join(parts)


# =============================================================================
# GLB loading
# =============================================================================

def load_glb_as_scene(glb_path: Path) -> trimesh.Scene:
    loaded = trimesh.load(glb_path, force="scene")
    if isinstance(loaded, trimesh.Scene):
        return loaded
    if isinstance(loaded, trimesh.Trimesh):
        scene = trimesh.Scene()
        scene.add_geometry(loaded, node_name="reference_model")
        return scene
    raise TypeError(f"Unsupported GLB type: {type(loaded)}")


def find_mesh_node(
    scene: trimesh.Scene,
    node_name: str,
) -> Tuple[str, str, trimesh.Trimesh]:
    for n in scene.graph.nodes_geometry:
        if n == node_name:
            transform, geometry_name = scene.graph[n]
            geometry = scene.geometry[geometry_name]
            if not isinstance(geometry, trimesh.Trimesh):
                continue
            mesh = geometry.copy()
            mesh.apply_transform(transform)
            return n, geometry_name, mesh
    raise ValueError(f"GLB node not found: '{node_name}'")


# =============================================================================
# Reference organ URL resolution
# =============================================================================

def resolve_reference_organ_glb_url(
    glb_filename: str,
    reference_organs_api_url: str,
) -> str:
    print(f"Resolving HRA reference organ GLB URL for: {glb_filename}")
    response = requests.get(reference_organs_api_url, timeout=120)
    response.raise_for_status()
    organs = response.json()
    for organ in organs:
        file_url = str(organ.get("object", {}).get("file", "")).strip()
        if file_url.endswith("/" + glb_filename) or file_url.endswith(glb_filename):
            print(f"Resolved: {file_url}")
            return file_url
    raise ValueError(f"Could not resolve GLB URL for '{glb_filename}'.")


# =============================================================================
# Transparency
# =============================================================================

def make_scene_transparent(scene: trimesh.Scene, alpha: int) -> None:
    alpha_factor = alpha / 255.0
    count = 0
    for geometry_name, geometry in scene.geometry.items():
        if not isinstance(geometry, trimesh.Trimesh) or len(geometry.faces) == 0:
            continue
        base_rgb = np.array([190, 190, 190], dtype=np.uint8)
        try:
            face_colors = np.array(geometry.visual.face_colors, dtype=np.uint8)
            if face_colors.ndim == 2 and face_colors.shape[1] >= 3:
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
        count += 1
    print(f"Applied transparent PBR materials to {count} organ meshes.")


def patch_glb_transparency(glb_path: Path) -> None:
    try:
        from pygltflib import GLTF2
    except ImportError:
        print("Warning: pygltflib not installed; skipping GLB transparency patch.")
        return
    gltf = GLTF2().load(str(glb_path))
    if not gltf.materials:
        return
    patched = 0
    for material in gltf.materials:
        name = material.name or ""
        if name.startswith("transparent_organ_"):
            material.alphaMode = "BLEND"
            material.doubleSided = True
            patched += 1
        elif name.startswith("generated_cell_material_"):
            material.alphaMode = "OPAQUE"
            material.doubleSided = True
    gltf.save_binary(str(glb_path))
    print(f"Patched {patched} transparent GLB materials.")


# =============================================================================
# HRA 3D Cell Generation API
# =============================================================================

def call_cell_api(
    api_url: str,
    file: str,
    scene_node: str,
    num_nodes: int,
    node_distribution: Dict[str, float],
) -> Tuple[np.ndarray, List[str]]:
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

    reader = csv.DictReader(StringIO(response.text))
    rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("3D Cell Generation API returned no rows.")

    actual_cols = set(rows[0].keys())
    cell_type_col = next(
        (c for c in ["Cell Type", "cell_type", "cell_label", "cellLabel"] if c in actual_cols),
        None,
    )
    if cell_type_col is None:
        raise ValueError(f"No cell type column found. Columns: {sorted(actual_cols)}")
    if not {"x", "y", "z"}.issubset(actual_cols):
        raise ValueError(f"Missing coordinate columns. Columns: {sorted(actual_cols)}")

    points = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in rows])
    cell_types = [str(r[cell_type_col]) for r in rows]
    return points, cell_types


# =============================================================================
# Color map — Dict[str, str] (hex strings)
# =============================================================================

def build_color_map(
    all_cell_types: List[str],
    global_top_labels: List[str],
) -> Dict[str, str]:
    top_set = {normalize_cell_label_key(l) for l in global_top_labels}
    color_map: Dict[str, str] = {}

    for label in sorted(set(all_cell_types)):
        key = normalize_cell_label_key(label)
        if key in top_set:
            idx = next(
                (i for i, l in enumerate(global_top_labels)
                 if normalize_cell_label_key(l) == key),
                None,
            )
            color_map[label] = PALETTE[idx] if idx is not None and idx < len(PALETTE) else OTHERS
        else:
            color_map[label] = OTHERS

    return color_map


# =============================================================================
# Marker mesh creation
# =============================================================================

def make_marker_mesh(
    center: np.ndarray,
    shape: str,
    sphere_radius: float,
    sphere_subdivisions: int,
    marker_size: Optional[float],
    cell_type: str,
    color_map: Dict[str, str],
) -> trimesh.Trimesh:
    size = marker_size if marker_size is not None else sphere_radius

    if shape == "sphere":
        mesh = trimesh.creation.icosphere(subdivisions=sphere_subdivisions, radius=sphere_radius)
    elif shape == "cube":
        mesh = trimesh.creation.box(extents=(size, size, size))
    elif shape == "triangle":
        mesh = trimesh.creation.cone(radius=size, height=size * 2.0, sections=3)
        mesh.apply_translation([0.0, 0.0, -size])
    else:
        raise ValueError(f"Unsupported marker shape: '{shape}'")

    mesh.apply_translation(center)

    hex_color = color_map.get(cell_type, OTHERS)
    r, g, b = hex_to_float(hex_color)

    material = PBRMaterial(
        name=f"generated_cell_material_{safe_name(shape)}_{safe_name(cell_type)}",
        baseColorFactor=[r, g, b, 1.0],
        alphaMode="OPAQUE",
        doubleSided=True,
        metallicFactor=0.0,
        roughnessFactor=0.2,
    )
    mesh.visual = trimesh.visual.TextureVisuals(material=material)
    return mesh


# =============================================================================
# Output
# =============================================================================

def export_glb(scene: trimesh.Scene, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exported = scene.export(file_type="glb")
    output_path.write_bytes(exported if isinstance(exported, bytes) else bytes(exported))
    patch_glb_transparency(output_path)


def restructure_glb_hierarchy(
    output_path: Path,
    input_glb_path: Path,
    per_as_cell_node_names: Dict[str, List[str]],
    as_to_glb_node: Dict[str, List[str]],
    stem: str,
) -> None:
    try:
        from pygltflib import GLTF2, Node
    except ImportError:
        print("Warning: pygltflib not installed; skipping hierarchy restructure.")
        return

    gltf = GLTF2().load(str(output_path))
    name_to_idx = {node.name: i for i, node in enumerate(gltf.nodes)}
    scene_root_idx = gltf.scenes[gltf.scene].nodes[0] if gltf.scenes and gltf.scene is not None else 0

    all_cell_indices: set = set()
    attached_count = 0

    for as_label, cell_names in per_as_cell_node_names.items():
        if not cell_names:
            continue
        cell_indices = [name_to_idx[n] for n in cell_names if n in name_to_idx]
        if not cell_indices:
            continue
        all_cell_indices.update(cell_indices)

        glb_nodes = as_to_glb_node.get(as_label)
        if not glb_nodes:
            continue
        if isinstance(glb_nodes, str):
            glb_nodes = [glb_nodes]

        target_glb_node_name = glb_nodes[0]
        target_idx = name_to_idx.get(target_glb_node_name)
        if target_idx is None:
            print(f"  Warning: GLB node '{target_glb_node_name}' not found in output GLB.")
            continue

        cells_node_idx = len(gltf.nodes)
        gltf.nodes.append(Node(name="cells", children=cell_indices))

        target_node = gltf.nodes[target_idx]
        if target_node.children is None:
            target_node.children = []
        target_node.children.append(cells_node_idx)
        attached_count += 1

        print(f"  Attached {len(cell_indices)} cells under '{target_glb_node_name}/cells'")

    root_node = gltf.nodes[scene_root_idx]
    root_node.children = [
        c for c in (root_node.children or [])
        if c not in all_cell_indices
    ]

    gltf.save_binary(str(output_path))
    print(f"Restructured GLB hierarchy: {attached_count} AS groups attached under mesh nodes.")


def write_nodes_csv(
    csv_path: Path,
    all_points: List[np.ndarray],
    all_cell_types: List[str],
    all_as_labels: List[str],
    color_map: Dict[str, str],
    shape: str,
    cell_id_map: Dict[str, str],
    organ_cell_counts: Dict[str, float],
) -> None:
    """
    Write the per-marker CSV with coordinates, cell type, cell ID,
    organ-wide percentage, organ-wide raw cell count, and hex color.
    """
    # Organ-wide marker counts for percentage calculation
    organ_marker_counts: Dict[str, int] = {}
    for cell_type in all_cell_types:
        organ_marker_counts[cell_type] = organ_marker_counts.get(cell_type, 0) + 1
    organ_total = len(all_cell_types)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index", "as_label", "cell_type", "cell_id",
            "organ_percentage", "cell_count",
            "x", "y", "z",
            "hex_color",
            "marker_shape",
        ])
        for i, (point, cell_type, as_label) in enumerate(
            zip(all_points, all_cell_types, all_as_labels)
        ):
            hex_color = color_map.get(cell_type, OTHERS)
            cell_id = cell_id_map.get(normalize_cell_label_key(cell_type), "")
            ct_marker_count = organ_marker_counts.get(cell_type, 0)
            organ_pct = round((ct_marker_count / organ_total) * 100, 4) if organ_total > 0 else 0.0
            raw_count = int(organ_cell_counts.get(cell_type, 0))

            writer.writerow([
                i, as_label, cell_type, cell_id,
                organ_pct, raw_count,
                float(point[0]), float(point[1]), float(point[2]),
                hex_color,
                shape,
            ])


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    organs_folder = Path(config["output"]["organs_folder"])
    organ_name = config["organ"]["name"]
    organ_sex = config["organ"]["sex"]
    organ_side = (config["organ"].get("side") or "").strip()
    glb_filename = (config["organ"].get("glb_filename") or "").strip()

    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)
        print(f"Auto-resolved GLB filename: {glb_filename}")

    input_glb = organs_folder / glb_filename
    if not input_glb.exists():
        raise FileNotFoundError(f"Input GLB not found: {input_glb}. Run 10_download_organs.py first.")

    stem = input_glb.stem

    # Output folders
    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    json_folder = base_folder / "json"
    glb_folder  = base_folder / "glb"
    csv_folder  = base_folder / "csv"
    for folder in [json_folder, glb_folder, csv_folder]:
        folder.mkdir(parents=True, exist_ok=True)

    distribution_path = json_folder / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(f"Distribution JSON not found: {distribution_path}. Run 20_fetch_cell_distribution.py first.")

    with distribution_path.open("r", encoding="utf-8") as f:
        dist_data = json.load(f)

    shape = config["markers"]["shape"]
    sphere_radius = config["markers"]["sphere_radius"]
    sphere_subdivisions = config["markers"]["sphere_subdivisions"]
    marker_size = config["markers"].get("size")
    organ_alpha = config["visualization"]["organ_alpha"]
    cell_api_url = config["apis"]["cell_generation"]
    reference_organs_api_url = config["apis"]["reference_organs"]
    tool_slug = config["filters"]["tool"].lower()

    global_top_labels: List[str] = dist_data["global_top_labels"]
    as_labels: List[str] = dist_data["as_labels"]
    as_to_glb_node: Dict[str, List[str]] = dist_data["as_to_glb_node"]
    per_as_normalized: Dict[str, Dict[str, float]] = dist_data["per_as_normalized"]
    node_allocation: Dict[str, int] = dist_data["node_allocation"]
    cell_id_map: Dict[str, str] = dist_data.get("cell_id_map", {})
    organ_cell_counts: Dict[str, float] = dist_data.get("organ_cell_counts", {})
    uberon_id: str = dist_data.get("uberon_id", "")

    # Build output filename stem with UBERON ID
    output_name = build_output_stem(stem, uberon_id, tool_slug, shape)

    print(f"Loading GLB: {input_glb}")
    scene = load_glb_as_scene(input_glb)
    make_scene_transparent(scene, organ_alpha)

    hra_glb_url = resolve_reference_organ_glb_url(glb_filename, reference_organs_api_url)

    all_points: List[np.ndarray] = []
    all_cell_types: List[str] = []
    all_as_labels_flat: List[str] = []

    per_as_points: Dict[str, List[np.ndarray]] = {}
    per_as_cell_types: Dict[str, List[str]] = {}

    MIN_NODES_PER_CALL = 10

    for as_label in as_labels:
        glb_nodes = as_to_glb_node.get(as_label)
        total_nodes_for_as = node_allocation.get(as_label, 0)
        normalized_dist = per_as_normalized.get(as_label, {})

        if total_nodes_for_as <= 0 or not normalized_dist or not glb_nodes:
            print(f"Skipping {as_label} — no nodes or empty distribution.")
            continue

        if isinstance(glb_nodes, str):
            glb_nodes = [glb_nodes]

        # If splitting would give too few per node, use only the first node
        if total_nodes_for_as // len(glb_nodes) < MIN_NODES_PER_CALL:
            glb_nodes = [glb_nodes[0]]

        nodes_per_mesh = total_nodes_for_as // len(glb_nodes)
        remainder = total_nodes_for_as % len(glb_nodes)

        per_as_points[as_label] = []
        per_as_cell_types[as_label] = []

        for mesh_idx, glb_node in enumerate(glb_nodes):
            num_nodes = nodes_per_mesh + (remainder if mesh_idx == len(glb_nodes) - 1 else 0)
            print(f"\nProcessing: {as_label} → {glb_node} ({num_nodes} nodes)")

            try:
                points, cell_types = call_cell_api(
                    api_url=cell_api_url,
                    file=hra_glb_url,
                    scene_node=glb_node,
                    num_nodes=num_nodes,
                    node_distribution=normalized_dist,
                )
            except Exception as e:
                print(f"  API call failed for {as_label} / {glb_node}: {e}")
                continue

            print(f"  API returned {len(points)} points.")
            per_as_points[as_label].extend(points)
            per_as_cell_types[as_label].extend(cell_types)
            all_points.extend(points)
            all_cell_types.extend(cell_types)
            all_as_labels_flat.extend([as_label] * len(points))

    if not all_points:
        raise ValueError("No points were generated across any anatomical structure.")

    print(f"\nTotal markers placed: {len(all_points)}")

    color_map = build_color_map(all_cell_types, global_top_labels)

    print("Adding markers to scene...")
    per_as_cell_node_names: Dict[str, List[str]] = {
        as_label: [] for as_label in per_as_points
    }

    cell_counter = 0
    for as_label, points in per_as_points.items():
        cell_types_for_as = per_as_cell_types[as_label]
        for point, cell_type in zip(points, cell_types_for_as):
            marker = make_marker_mesh(
                center=point,
                shape=shape,
                sphere_radius=sphere_radius,
                sphere_subdivisions=sphere_subdivisions,
                marker_size=marker_size,
                cell_type=cell_type,
                color_map=color_map,
            )
            cell_id = cell_id_map.get(normalize_cell_label_key(cell_type), "")
            if cell_id:
                cell_node = f"{cell_id}_{safe_name(cell_type)}_{cell_counter:05d}"
            else:
                cell_node = f"{safe_name(cell_type)}_{cell_counter:05d}"

            scene.add_geometry(
                marker,
                node_name=cell_node,
                geom_name=f"{cell_node}_geometry",
            )
            per_as_cell_node_names[as_label].append(cell_node)
            cell_counter += 1

    output_glb = glb_folder / f"{output_name}.glb"
    output_csv = csv_folder / f"{output_name}.csv"

    export_glb(scene, output_glb)
    print(f"Exported GLB: {output_glb}")

    restructure_glb_hierarchy(
        output_path=output_glb,
        input_glb_path=input_glb,
        per_as_cell_node_names=per_as_cell_node_names,
        as_to_glb_node=as_to_glb_node,
        stem=stem,
    )

    write_nodes_csv(
        csv_path=output_csv,
        all_points=all_points,
        all_cell_types=all_cell_types,
        all_as_labels=all_as_labels_flat,
        color_map=color_map,
        shape=shape,
        cell_id_map=cell_id_map,
        organ_cell_counts=organ_cell_counts,
    )
    print(f"Exported CSV: {output_csv}")


if __name__ == "__main__":
    main()