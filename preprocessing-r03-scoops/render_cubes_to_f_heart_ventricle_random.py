#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh


# ---------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------

DEFAULT_RANDOM_SEED = 42
DEFAULT_NUM_NODES = 500

# Target anatomical structure inside the GLB scene.
# For the uploaded heart model, the matching node is:
# VH_F_right_ventricle
DEFAULT_TARGET_STRUCTURE = "right_ventricle"

# If None, cube size is calculated from the target structure bounds.
DEFAULT_CUBE_SIZE = None

# Used only when cube size is not manually supplied.
# The cube size becomes this fraction of the target structure's smallest dimension.
DEFAULT_AUTO_CUBE_SIZE_FRACTION = 0.015

# Used for watertight meshes when strict inside-mesh sampling is possible.
DEFAULT_SAMPLE_BATCH_SIZE = 5000
DEFAULT_MAX_SAMPLE_ATTEMPTS = 200

NODE_PARENT_NAME = "random_cell_cube_node"


# ---------------------------------------------------------------------
# Generic cell type distribution
# ---------------------------------------------------------------------
# Values are normalized automatically, so they do not need to sum to 1.0.

CELL_TYPE_DISTRIBUTION: Dict[str, float] = {
    "Cell Type 1": 0.06182582952775565,
    "Cell Type 2": 0.07918079611955897,
    "Cell Type 3": 0.1025719909343514,
    "Cell Type 4": 0.2284502812949354,
    "Cell Type 5": 0.1044009719189105,
    "Cell Type 6": 0.04209067801988033,
    "Cell Type 7": 0.04753494481555039,
    "Cell Type 8": 0.03025986690010765,
    "Cell Type 9": 0.06095887356667489,
    "Cell Type 10": 0.08139610385279325,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add randomly generated weighted cell-type cube nodes to a selected "
            "anatomical structure inside an organ GLB."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the input organ GLB.",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to the output amended GLB.",
    )

    parser.add_argument(
        "--target-structure",
        type=str,
        default=DEFAULT_TARGET_STRUCTURE,
        help=(
            "Structure name to target inside the GLB. "
            "Partial matches are allowed. "
            f"Default: {DEFAULT_TARGET_STRUCTURE}."
        ),
    )

    parser.add_argument(
        "--num-nodes",
        type=int,
        default=DEFAULT_NUM_NODES,
        help=f"Number of random cube nodes to generate. Default: {DEFAULT_NUM_NODES}.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed. Default: {DEFAULT_RANDOM_SEED}.",
    )

    parser.add_argument(
        "--cube-size",
        type=float,
        default=DEFAULT_CUBE_SIZE,
        help=(
            "Manual cube size for generated node cubes. "
            "If omitted, cube size is auto-sized from the target structure bounds."
        ),
    )

    parser.add_argument(
        "--auto-cube-size-fraction",
        type=float,
        default=DEFAULT_AUTO_CUBE_SIZE_FRACTION,
        help=(
            "Fraction of the target structure's smallest dimension used as cube size "
            f"when --cube-size is omitted. Default: {DEFAULT_AUTO_CUBE_SIZE_FRACTION}."
        ),
    )

    parser.add_argument(
        "--sample-batch-size",
        type=int,
        default=DEFAULT_SAMPLE_BATCH_SIZE,
        help=(
            "Number of candidate points sampled per attempt for watertight target meshes. "
            f"Default: {DEFAULT_SAMPLE_BATCH_SIZE}."
        ),
    )

    parser.add_argument(
        "--max-sample-attempts",
        type=int,
        default=DEFAULT_MAX_SAMPLE_ATTEMPTS,
        help=(
            "Maximum sampling attempts for watertight target meshes. "
            f"Default: {DEFAULT_MAX_SAMPLE_ATTEMPTS}."
        ),
    )

    parser.add_argument(
        "--csv-output",
        type=Path,
        default=None,
        help=(
            "Optional CSV output path for generated node positions and cell types. "
            "If omitted, a CSV is not written."
        ),
    )

    return parser.parse_args()


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


def normalize_match_text(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("__", "_")
        .strip()
    )


def get_auto_cube_size(
    target_mesh: trimesh.Trimesh,
    auto_cube_size_fraction: float,
) -> float:
    if auto_cube_size_fraction <= 0:
        raise ValueError("Auto cube size fraction must be greater than zero.")

    bounds_min, bounds_max = target_mesh.bounds
    bounds_size = bounds_max - bounds_min

    smallest_dimension = float(np.min(bounds_size))
    cube_size = smallest_dimension * auto_cube_size_fraction

    if cube_size <= 0:
        raise ValueError("Could not compute a valid automatic cube size.")

    return cube_size


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


def generate_cell_types(
    num_nodes: int,
    distribution: Dict[str, float],
    rng: np.random.Generator,
) -> List[str]:
    labels, probabilities = normalize_distribution(distribution)

    selected = rng.choice(
        labels,
        size=num_nodes,
        replace=True,
        p=probabilities,
    )

    return [str(value) for value in selected]


def random_points_in_bounds(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    return rng.uniform(bounds_min, bounds_max, size=(count, 3))


def generate_random_points_for_target_structure(
    target_mesh: trimesh.Trimesh,
    num_points: int,
    rng: np.random.Generator,
    sample_batch_size: int,
    max_sample_attempts: int,
) -> np.ndarray:
    """
    Generates points for the selected anatomical structure.

    If the target mesh is watertight:
        generate points strictly inside the mesh.

    If the target mesh is not watertight:
        generate points on the target mesh surface.

    Surface sampling is better than bounding-box sampling for non-watertight
    anatomical GLB structures because the points stay visually attached to the
    selected structure instead of filling empty space around it.
    """
    if num_points <= 0:
        raise ValueError("Number of points must be greater than zero.")

    if sample_batch_size <= 0:
        raise ValueError("Sample batch size must be greater than zero.")

    if max_sample_attempts <= 0:
        raise ValueError("Max sample attempts must be greater than zero.")

    bounds_min, bounds_max = target_mesh.bounds

    if not target_mesh.is_watertight:
        print(
            "Target structure mesh is not watertight. "
            "Using surface sampling on the selected structure."
        )

        points, face_indices = trimesh.sample.sample_surface(
            mesh=target_mesh,
            count=num_points,
        )

        return np.asarray(points, dtype=float)

    accepted_points: List[np.ndarray] = []

    print("Target structure mesh is watertight. Using strict inside-mesh sampling.")

    for attempt in range(1, max_sample_attempts + 1):
        candidates = random_points_in_bounds(
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            count=sample_batch_size,
            rng=rng,
        )

        try:
            contains = target_mesh.contains(candidates)
        except Exception as exc:
            print(f"Strict containment failed: {exc}")
            print("Falling back to surface sampling on the selected structure.")

            points, face_indices = trimesh.sample.sample_surface(
                mesh=target_mesh,
                count=num_points,
            )

            return np.asarray(points, dtype=float)

        inside = candidates[contains]

        if len(inside) > 0:
            accepted_points.append(inside)

        total_accepted = sum(len(points) for points in accepted_points)
        print(f"Attempt {attempt}: accepted {total_accepted} / {num_points}")

        if total_accepted >= num_points:
            all_points = np.vstack(accepted_points)
            return all_points[:num_points]

    print(
        "Could not generate enough inside-mesh points. "
        "Falling back to surface sampling on the selected structure."
    )

    points, face_indices = trimesh.sample.sample_surface(
        mesh=target_mesh,
        count=num_points,
    )

    return np.asarray(points, dtype=float)


def stable_cell_type_seed(cell_type: str) -> int:
    digest = hashlib.sha256(cell_type.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="little", signed=False)


def cell_type_to_color(cell_type: str) -> np.ndarray:
    """
    Creates a stable pseudo-random color from the cell type name.
    """
    seed = stable_cell_type_seed(cell_type)
    local_rng = np.random.default_rng(seed)

    rgb = local_rng.integers(low=40, high=256, size=3, dtype=np.uint8)
    rgba = np.array([rgb[0], rgb[1], rgb[2], 255], dtype=np.uint8)

    return rgba


def make_cube_marker(
    center: np.ndarray,
    cube_size: float,
    cell_type: str,
) -> trimesh.Trimesh:
    cube = trimesh.creation.box(
        extents=(cube_size, cube_size, cube_size)
    )

    cube.apply_translation(center)
    cube.visual.face_colors = cell_type_to_color(cell_type)

    return cube


def safe_name(value: str) -> str:
    cleaned = value.strip()
    cleaned = cleaned.replace(" ", "_")
    cleaned = cleaned.replace("/", "_")
    cleaned = cleaned.replace("\\", "_")
    cleaned = cleaned.replace(":", "_")
    cleaned = cleaned.replace(";", "_")
    cleaned = cleaned.replace(",", "_")
    cleaned = cleaned.replace("(", "")
    cleaned = cleaned.replace(")", "")

    return cleaned


def add_random_cube_nodes_to_scene(
    scene: trimesh.Scene,
    points: np.ndarray,
    cell_types: List[str],
    cube_size: float,
    target_structure_name: str,
) -> None:
    if len(points) != len(cell_types):
        raise ValueError("Point count and cell type count do not match.")

    target_name = safe_name(target_structure_name)

    for index, (point, cell_type) in enumerate(zip(points, cell_types)):
        cube = make_cube_marker(
            center=point,
            cube_size=cube_size,
            cell_type=cell_type,
        )

        cell_type_name = safe_name(cell_type)

        scene.add_geometry(
            cube,
            node_name=(
                f"{NODE_PARENT_NAME}_{target_name}_"
                f"{index:05d}_{cell_type_name}"
            ),
            geom_name=(
                f"{NODE_PARENT_NAME}_geometry_{target_name}_"
                f"{index:05d}_{cell_type_name}"
            ),
        )


def export_scene_as_glb(scene: trimesh.Scene, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported = scene.export(file_type="glb")

    if isinstance(exported, bytes):
        output_path.write_bytes(exported)
    else:
        output_path.write_bytes(bytes(exported))


def write_nodes_csv(
    csv_output_path: Path,
    points: np.ndarray,
    cell_types: List[str],
    target_node_name: str,
    target_geometry_name: str,
) -> None:
    csv_output_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "index",
                "x",
                "y",
                "z",
                "cell_type",
                "target_node_name",
                "target_geometry_name",
            ]
        )

        for index, (point, cell_type) in enumerate(zip(points, cell_types)):
            writer.writerow(
                [
                    index,
                    float(point[0]),
                    float(point[1]),
                    float(point[2]),
                    cell_type,
                    target_node_name,
                    target_geometry_name,
                ]
            )


def print_cell_type_summary(cell_types: List[str]) -> None:
    unique, counts = np.unique(np.array(cell_types), return_counts=True)

    print("Generated cell type counts:")

    for label, count in sorted(zip(unique, counts), key=lambda item: item[0]):
        print(f"  {label}: {count}")


def main() -> None:
    args = parse_args()

    input_glb: Path = args.input
    output_glb: Path = args.output

    if not input_glb.exists():
        raise FileNotFoundError(f"Could not find input GLB: {input_glb}")

    rng = np.random.default_rng(args.seed)

    print(f"Loading GLB: {input_glb}")

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

    bounds_min, bounds_max = target_mesh.bounds
    bounds_size = bounds_max - bounds_min

    cube_size = (
        args.cube_size
        if args.cube_size is not None
        else get_auto_cube_size(
            target_mesh=target_mesh,
            auto_cube_size_fraction=args.auto_cube_size_fraction,
        )
    )

    if cube_size <= 0:
        raise ValueError("Cube size must be greater than zero.")

    distribution_sum = sum(CELL_TYPE_DISTRIBUTION.values())

    print(f"Target structure search: {args.target_structure}")
    print(f"Matched target node: {target_node_name}")
    print(f"Matched target geometry: {target_geometry_name}")
    print(f"Target vertices: {len(target_mesh.vertices)}")
    print(f"Target faces: {len(target_mesh.faces)}")
    print(f"Target watertight: {target_mesh.is_watertight}")
    print(f"Target bounds min: {bounds_min}")
    print(f"Target bounds max: {bounds_max}")
    print(f"Target bounds size: {bounds_size}")
    print(f"Node count: {args.num_nodes}")
    print(f"Cube size: {cube_size}")
    print(f"Distribution sum before normalization: {distribution_sum}")

    points = generate_random_points_for_target_structure(
        target_mesh=target_mesh,
        num_points=args.num_nodes,
        rng=rng,
        sample_batch_size=args.sample_batch_size,
        max_sample_attempts=args.max_sample_attempts,
    )

    cell_types = generate_cell_types(
        num_nodes=args.num_nodes,
        distribution=CELL_TYPE_DISTRIBUTION,
        rng=rng,
    )

    print_cell_type_summary(cell_types)

    add_random_cube_nodes_to_scene(
        scene=scene,
        points=points,
        cell_types=cell_types,
        cube_size=cube_size,
        target_structure_name=target_node_name,
    )

    export_scene_as_glb(scene, output_glb)

    print(f"Exported modified GLB to: {output_glb}")

    if args.csv_output is not None:
        write_nodes_csv(
            csv_output_path=args.csv_output,
            points=points,
            cell_types=cell_types,
            target_node_name=target_node_name,
            target_geometry_name=target_geometry_name,
        )

        print(f"Exported generated node CSV to: {args.csv_output}")


if __name__ == "__main__":
    main()