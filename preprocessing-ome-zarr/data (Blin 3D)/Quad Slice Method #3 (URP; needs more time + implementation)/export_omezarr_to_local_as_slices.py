from pathlib import Path
import json
import numpy as np
from PIL import Image

from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from ome_zarr.format import FormatV04

URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
OUT_DIR = Path("exported_volume")

OUT_DIR.mkdir(parents=True, exist_ok=True)

STACKS_DIR = OUT_DIR / "stacks"
STACKS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_to_u8(volume: np.ndarray) -> np.ndarray:
    vmin = float(volume.min())
    vmax = float(volume.max())
    normalized = (volume - vmin) / (vmax - vmin + 1e-8)
    return (normalized * 255.0).astype(np.uint8)


def orient_slice_z(slice_img: np.ndarray) -> np.ndarray:
    # XY plane: keep a consistent image orientation.
    # If you need a different handedness later, change only here.
    return np.flipud(slice_img)


def orient_slice_y(slice_img: np.ndarray) -> np.ndarray:
    # XZ plane: transpose into image space, then flip to match the same convention.
    return np.flipud(slice_img.T)


def orient_slice_x(slice_img: np.ndarray) -> np.ndarray:
    # YZ plane: transpose into image space, then flip to match the same convention.
    return np.rot90(slice_img, k=3)


def save_stack(volume_u8: np.ndarray, out_dir: Path, axis: str) -> int:
    """
    volume_u8 shape: (z, y, x)

    axis:
      'z' -> XY planes stacked along Z
      'y' -> XZ planes stacked along Y
      'x' -> YZ planes stacked along X
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0

    if axis == "z":
        for i in range(volume_u8.shape[0]):
            slice_img = volume_u8[i, :, :]          # (y, x)
            slice_img = orient_slice_z(slice_img)
            img = Image.fromarray(slice_img, mode="L")
            img.save(out_dir / f"slice_{i:04d}.png")
            count += 1

    elif axis == "y":
        for i in range(volume_u8.shape[1]):
            slice_img = volume_u8[:, i, :]          # (z, x)
            slice_img = orient_slice_y(slice_img)
            img = Image.fromarray(slice_img, mode="L")
            img.save(out_dir / f"slice_{i:04d}.png")
            count += 1

    elif axis == "x":
        for i in range(volume_u8.shape[2]):
            slice_img = volume_u8[:, :, i]          # (z, y)
            slice_img = orient_slice_x(slice_img)
            img = Image.fromarray(slice_img, mode="L")
            img.save(out_dir / f"slice_{i:04d}.png")
            count += 1

    else:
        raise ValueError(f"Unsupported axis: {axis}")

    return count


# Open remote OME-Zarr store
zloc = parse_url(URL, mode="r", fmt=FormatV04())
reader = Reader(zloc)

nodes = list(reader())
if not nodes:
    raise RuntimeError("No image nodes found in the OME-Zarr store.")

image_node = nodes[0]

arr = np.asarray(image_node.data[0])

if arr.ndim != 4:
    raise ValueError(f"Expected array shape (c, z, y, x), got {arr.shape}")

c, z, y, x = arr.shape
print(f"Loaded volume shape: {arr.shape}")

manifest = {
    "source_url": URL,
    "shape_czyx": [c, z, y, x],
    "stacks": [
        {
            "key": "z",
            "name": "axial",
            "plane": "xy",
            "stack_axis": "z",
            "folder": "stacks/z",
        },
        {
            "key": "y",
            "name": "coronal",
            "plane": "xz",
            "stack_axis": "y",
            "folder": "stacks/y",
        },
        {
            "key": "x",
            "name": "sagittal",
            "plane": "yz",
            "stack_axis": "x",
            "folder": "stacks/x",
        },
    ],
    "channels": [],
}

for channel_index in range(c):
    volume = np.asarray(arr[channel_index], dtype=np.float32)
    volume_u8 = normalize_to_u8(volume)

    channel_info = {
        "channel_index": channel_index,
        "dtype": "uint8",
        "normalized": True,
        "paths": {}
    }

    print(f"Channel {channel_index}: min={volume.min()} max={volume.max()}")

    for axis_key in ["z", "y", "x"]:
        axis_dir = STACKS_DIR / axis_key / f"c{channel_index}"
        axis_count = save_stack(volume_u8, axis_dir, axis_key)
        channel_info["paths"][axis_key] = f"stacks/{axis_key}/c{channel_index}"
        print(f"  {axis_key}-stack: {axis_count} slices -> {axis_dir}")

    manifest["channels"].append(channel_info)

(OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"\nDone. Exported to: {OUT_DIR.resolve()}")