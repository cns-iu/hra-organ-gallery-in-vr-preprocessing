from pathlib import Path
import gcsfs

SOURCE = "gs://vitessce-demo-data/spatialdata-september-2023/mcmicro_io.zarr"
DEST = Path("mcmicro_io.zarr")

fs = gcsfs.GCSFileSystem(token="anon")

DEST.mkdir(parents=True, exist_ok=True)

prefix = SOURCE.rstrip("/") + "/"

for remote_path in fs.find(SOURCE):
    # Skip the root entry if it appears in the listing.
    if remote_path.rstrip("/") == SOURCE.rstrip("/"):
        continue

    rel = remote_path[len(prefix):] if remote_path.startswith(prefix) else remote_path
    local_path = DEST / rel

    if remote_path.endswith("/"):
        local_path.mkdir(parents=True, exist_ok=True)
        continue

    local_path.parent.mkdir(parents=True, exist_ok=True)
    fs.get_file(remote_path, str(local_path))

print(f"Downloaded to {DEST.resolve()}")