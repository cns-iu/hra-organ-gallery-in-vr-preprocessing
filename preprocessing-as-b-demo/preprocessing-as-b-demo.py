import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
PYTHON = VENV / "bin" / "python"

# On first run, create .venv and install requirements; then re-run this script inside .venv
if Path(sys.prefix).resolve() != VENV:
    if not PYTHON.exists():
        subprocess.check_call([sys.executable, "-m", "venv", VENV])
        subprocess.check_call(
            [PYTHON, "-m", "pip", "install", "-q", "-r", HERE / "requirements.txt"]
        )
    sys.exit(subprocess.call([PYTHON, __file__, *sys.argv[1:]]))

import json

import pandas as pd
import requests

# Inputs are cached in data/, results go to output/ (both next to this script)
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "output"

# HRApop: mean gene expression per dataset, anatomical structure (AS) and cell type
HRA_POP_VERSION = "v1.1"
BRANCH = "main"
DATA_URL = f"https://github.com/x-atlas-consortia/hra-pop/raw/refs/heads/{BRANCH}/output-data/{HRA_POP_VERSION}/reports/atlas-ad-hoc/datasets-as-ct-gene.csv.gz"
DATA_PATH = DATA_DIR / "datasets-as-ct-gene.csv.gz"

# 3D reference organs and their anatomical structures
AS_3D_URL = "https://apps.humanatlas.io/api/v1/rui-reference-data"
AS_3D_PATH = DATA_DIR / "rui-reference-data.json"


def download_if_missing(url: str, file_path: Path, headers=None):
    """Download url to file_path unless it is already there."""
    if file_path.is_file():
        print(f"{file_path.name} already exists.")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    file_path.write_bytes(response.content)


def main():
    download_if_missing(DATA_URL, DATA_PATH)
    download_if_missing(AS_3D_URL, AS_3D_PATH, headers={"Accept": "application/json"})

    rui_reference_data = json.loads(AS_3D_PATH.read_text(encoding="utf-8"))
    df_data = pd.read_csv(DATA_PATH)

    # Average expression of each gene per AS, across all datasets, tools and cell types.
    # dropna=False keeps rows with a missing as_label.
    df_grouped = df_data.groupby(
        ["as_id", "as_label", "gene_id", "gene_label", "ensembl_id"],
        as_index=False,
        dropna=False,
    )["mean_expr"].mean()
    print(df_grouped)

    OUTPUT_DIR.mkdir(exist_ok=True)
    df_grouped.to_csv(OUTPUT_DIR / "as_b_mean.csv", index=False)


if __name__ == "__main__":
    main()
