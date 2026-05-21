from pathlib import Path
import json
import numpy as np

from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from ome_zarr.format import FormatV04

URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
OUT_DIR = Path("exported_volume")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# Open the remote OME-Zarr store
zloc = parse_url(URL, mode="r", fmt=FormatV04())
reader = Reader(zloc)
nodes = list(reader())

if not nodes:
    raise RuntimeError("No image nodes found in the OME-Zarr store.")

image_node = nodes[0]

manifest = {
    "source_url": URL,
    "levels": []
}

# image_node.data is the multiscale pyramid
for level_index, arr in enumerate(image_node.data):
    arr = np.asarray(arr)
    if arr.ndim != 4:
        raise ValueError(
            f"Expected array shape (c, z, y, x) at level {level_index}, got {arr.shape}"
        )

    c, z, y, x = arr.shape
    level_dir = OUT_DIR / f"level_{level_index}"
    level_dir.mkdir(parents=True, exist_ok=True)

    level_entry = {
        "level_index": level_index,
        "shape": [c, z, y, x],
        "channels": []
    }

    print(f"Exporting level {level_index}: shape={arr.shape}, dtype={arr.dtype}")

    for channel_index in range(c):
        volume = np.asarray(arr[channel_index])  # shape: (z, y, x)

        raw_path = level_dir / f"c{channel_index}.raw"
        meta_path = level_dir / f"c{channel_index}.json"

        volume.tofile(raw_path)

        meta = {
            "source_url": URL,
            "level_index": level_index,
            "channel_index": channel_index,
            "shape": [z, y, x],
            "dtype": str(volume.dtype),
            "axis_order": ["z", "y", "x"]
        }
        meta_path.write_text(json.dumps(meta, indent=2))

        level_entry["channels"].append({
            "channel_index": channel_index,
            "raw_file": f"c{channel_index}.raw",
            "json_file": f"c{channel_index}.json"
        })

        print(f"  wrote channel {channel_index}: {raw_path}")

    manifest["levels"].append(level_entry)

(OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"\nDone. Exported to: {OUT_DIR.resolve()}")