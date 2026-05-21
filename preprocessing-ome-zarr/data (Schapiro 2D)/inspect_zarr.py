from pathlib import Path
import zarr

root_path = Path("mcmicro_io.zarr")
root = zarr.open(root_path, mode="r")

print("Tree:")
print(root.tree())

print("\nTop-level keys:")
print(list(root.keys()))