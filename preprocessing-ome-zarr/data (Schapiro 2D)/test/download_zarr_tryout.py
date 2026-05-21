# download_zarr.py
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import gcsfs


def copy_local_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_gcs_tree(src: str, dst: Path) -> None:
    fs = gcsfs.GCSFileSystem(token="anon")  # public bucket access
    dst.mkdir(parents=True, exist_ok=True)

    root = src.rstrip("/")
    prefix = root + "/"

    # Find all files under the remote store and copy them one by one.
    for remote_path in fs.find(root):
        if remote_path.rstrip("/") == root:
            continue

        rel = remote_path[len(prefix):] if remote_path.startswith(prefix) else remote_path
        local_path = dst / rel
        local_path.parent.mkdir(parents=True, exist_ok=True)
        fs.get_file(remote_path, str(local_path))

    print(f"Downloaded GCS Zarr to: {dst.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Local Zarr path or gs://... Zarr store")
    parser.add_argument("dest", help="Local destination folder")
    args = parser.parse_args()

    src = args.source
    dst = Path(args.dest)

    if src.startswith("gs://"):
        copy_gcs_tree(src, dst)
    else:
        copy_local_tree(Path(src), dst)
        print(f"Copied local Zarr to: {dst.resolve()}")


if __name__ == "__main__":
    main()