from pathlib import Path
import json
import numpy as np

from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from ome_zarr.format import FormatV04

URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"

OUT_DIR = Path("unity_volume")
OUT_DIR.mkdir(exist_ok=True)

# Open the remote OME-Zarr store as FormatV04
zloc = parse_url(URL, mode="r", fmt=FormatV04())
reader = Reader(zloc)

nodes = list(reader())
print("nodes:", nodes)

# First image node
image_node = nodes[0]

# Highest-resolution level
arr = image_node.data[0]
print("array shape:", arr.shape)
print("array dtype:", arr.dtype)

# Expected shape: (c, z, y, x)
# Export each channel as its own real 3D volume
for channel_index in range(arr.shape[0]):
    volume = np.asarray(arr[channel_index])
    raw_path = OUT_DIR / f"volume_c{channel_index}.raw"
    meta_path = OUT_DIR / f"volume_c{channel_index}.json"

    volume.tofile(raw_path)
    meta = {
        "source": URL,
        "shape": list(volume.shape),
        "dtype": str(volume.dtype),
        "axis_order": ["z", "y", "x"],
        "channel_index": channel_index,
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote channel {channel_index}:")
    print(raw_path)
    print(meta_path)