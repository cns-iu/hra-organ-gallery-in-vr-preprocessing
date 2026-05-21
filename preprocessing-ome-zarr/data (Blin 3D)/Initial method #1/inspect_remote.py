from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from ome_zarr.format import FormatV04
import numpy as np
from pathlib import Path
import json

url = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"

zloc = parse_url(url, mode="r", fmt=FormatV04())
reader = Reader(zloc)

nodes = list(reader())
print("nodes:", nodes)

image_node = nodes[0]
arr = image_node.data[0]   # highest-resolution level

print("shape:", arr.shape)
print("dtype:", arr.dtype)

# Pick one channel for a first export if the array is (c, z, y, x)
volume = np.asarray(arr[0])

out_dir = Path("unity_volume")
out_dir.mkdir(exist_ok=True)

(volume).tofile(out_dir / "volume.raw")
(out_dir / "volume.json").write_text(json.dumps({
    "shape": list(volume.shape),
    "dtype": str(volume.dtype),
    "axis_order": ["z", "y", "x"]
}, indent=2))