#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh


SCRIPT_DIR = Path(__file__).resolve().parent

INPUT_GLB = SCRIPT_DIR / r"10_organs\downloaded_organs\3d-vh-f-heart.glb"

OUTPUT_GLB = SCRIPT_DIR / r"10_organs\amended_organs\3d-vh-f-heart-with-cube.glb"

# Set to None to auto-size the cube based on the model bounds.
# For this heart model, a manual value like 0.01 should also work.
CUBE_SIZE = None

# Used only when CUBE_SIZE is None.
# The cube will be this fraction of the model's smallest bounding-box dimension.
AUTO_CUBE_SIZE_FRACTION = 0.10

CUBE_NODE_NAME = "internal_cube"
CUBE_GEOMETRY_NAME = "internal_cube_geometry"


def load_glb_as_scene(glb_path: Path) -> trimesh.Scene:
    loaded = trimesh.load(glb_path, force="scene")

    if isinstance(loaded, trimesh.Scene):
        return loaded

    if isinstance(loaded, trimesh.Trimesh):
        scene = trimesh.Scene()
        scene.add_geometry(loaded, node_name="reference_model")
        return scene

    raise TypeError(f"Unsupported GLB type: {type(loaded)}")


def scene_to_single_mesh(scene: trimesh.Scene) -> trimesh.Trimesh:
    meshes: list[trimesh.Trimesh] = []

    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        geometry = scene.geometry[geometry_name]

        if not isinstance(geometry, trimesh.Trimesh):
            continue

        mesh = geometry.copy()
        mesh.apply_transform(transform)
        meshes.append(mesh)

    if not meshes:
        raise ValueError("No mesh geometries were found in the GLB file.")

    combined_mesh = trimesh.util.concatenate(meshes)
    combined_mesh.remove_unreferenced_vertices()

    return combined_mesh


def get_auto_cube_size(reference_mesh: trimesh.Trimesh) -> float:
    bounds_min, bounds_max = reference_mesh.bounds
    bounds_size = bounds_max - bounds_min

    smallest_dimension = float(np.min(bounds_size))
    cube_size = smallest_dimension * AUTO_CUBE_SIZE_FRACTION

    if cube_size <= 0:
        raise ValueError("Could not compute a valid automatic cube size.")

    return cube_size


def make_cube(center: np.ndarray, size: float) -> trimesh.Trimesh:
    cube = trimesh.creation.box(extents=(size, size, size))
    cube.apply_translation(center)

    # Optional: give the cube a visible material color.
    # RGBA: red, green, blue, alpha
    cube.visual.face_colors = [255, 0, 0, 255]

    return cube


def get_cube_corners(center: np.ndarray, size: float) -> np.ndarray:
    half = size / 2.0

    offsets = np.array(
        [
            [-half, -half, -half],
            [-half, -half, half],
            [-half, half, -half],
            [-half, half, half],
            [half, -half, -half],
            [half, -half, half],
            [half, half, -half],
            [half, half, half],
        ],
        dtype=float,
    )

    return center + offsets


def cube_fits_inside_bounds(
    reference_mesh: trimesh.Trimesh,
    cube_center: np.ndarray,
    cube_size: float,
) -> bool:
    cube_corners = get_cube_corners(cube_center, cube_size)
    bounds_min, bounds_max = reference_mesh.bounds

    return bool(
        np.all(cube_corners >= bounds_min)
        and np.all(cube_corners <= bounds_max)
    )


def cube_fits_inside_mesh(
    reference_mesh: trimesh.Trimesh,
    cube_center: np.ndarray,
    cube_size: float,
) -> bool:
    if not reference_mesh.is_watertight:
        return False

    cube_corners = get_cube_corners(cube_center, cube_size)

    try:
        contains = reference_mesh.contains(cube_corners)
    except Exception:
        return False

    return bool(np.all(contains))


def find_cube_center(reference_mesh: trimesh.Trimesh, cube_size: float) -> np.ndarray:
    centroid = np.asarray(reference_mesh.centroid, dtype=float)
    bounds_center = np.asarray(reference_mesh.bounds.mean(axis=0), dtype=float)

    if cube_fits_inside_mesh(reference_mesh, centroid, cube_size):
        print("Using mesh centroid. Cube passed strict inside-mesh check.")
        return centroid

    if cube_fits_inside_mesh(reference_mesh, bounds_center, cube_size):
        print("Using bounding-box center. Cube passed strict inside-mesh check.")
        return bounds_center

    if cube_fits_inside_bounds(reference_mesh, centroid, cube_size):
        print(
            "Using mesh centroid. Mesh is not watertight, so using bounding-box containment."
        )
        return centroid

    if cube_fits_inside_bounds(reference_mesh, bounds_center, cube_size):
        print(
            "Using bounding-box center. Mesh is not watertight, so using bounding-box containment."
        )
        return bounds_center

    bounds_min, bounds_max = reference_mesh.bounds
    bounds_size = bounds_max - bounds_min

    raise ValueError(
        "Could not place the cube inside the model bounds.\n"
        f"Cube size: {cube_size}\n"
        f"Model bounds size: {bounds_size}\n"
        "Try reducing CUBE_SIZE or AUTO_CUBE_SIZE_FRACTION."
    )


def export_scene_as_glb(scene: trimesh.Scene, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported = scene.export(file_type="glb")

    if isinstance(exported, bytes):
        output_path.write_bytes(exported)
    else:
        output_path.write_bytes(bytes(exported))


def main() -> None:
    if not INPUT_GLB.exists():
        raise FileNotFoundError(f"Could not find input GLB: {INPUT_GLB}")

    print(f"Loading GLB: {INPUT_GLB}")

    scene = load_glb_as_scene(INPUT_GLB)
    reference_mesh = scene_to_single_mesh(scene)

    bounds_min, bounds_max = reference_mesh.bounds
    bounds_size = bounds_max - bounds_min

    cube_size = CUBE_SIZE if CUBE_SIZE is not None else get_auto_cube_size(reference_mesh)

    print(f"Reference vertices: {len(reference_mesh.vertices)}")
    print(f"Reference faces: {len(reference_mesh.faces)}")
    print(f"Reference watertight: {reference_mesh.is_watertight}")
    print(f"Reference bounds min: {bounds_min}")
    print(f"Reference bounds max: {bounds_max}")
    print(f"Reference bounds size: {bounds_size}")
    print(f"Cube size: {cube_size}")

    cube_center = find_cube_center(reference_mesh, cube_size)
    cube = make_cube(center=cube_center, size=cube_size)

    scene.add_geometry(
        cube,
        node_name=CUBE_NODE_NAME,
        geom_name=CUBE_GEOMETRY_NAME,
    )

    export_scene_as_glb(scene, OUTPUT_GLB)

    print(f"Cube center: {cube_center}")
    print(f"Exported modified GLB to: {OUTPUT_GLB}")


if __name__ == "__main__":
    main()