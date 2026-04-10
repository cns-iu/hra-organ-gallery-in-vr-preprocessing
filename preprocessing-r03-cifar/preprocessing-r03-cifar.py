import subprocess
import sys
from pathlib import Path
import pandas as pd
from pprint import pprint
import requests
from io import StringIO
import os
import matplotlib.pyplot as plt
import numpy as np


def install_requirements(requirements_file="requirements.txt"):
    path = Path(requirements_file)

    if not path.exists():
        print(f"Error: {requirements_file} not found.")
        sys.exit(1)

    print(f"Installing dependencies from {requirements_file}...")

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(path)])
        print("Installation complete.")
    except subprocess.CalledProcessError as e:
        print("Failed to install dependencies.")
        sys.exit(e.returncode)


def fetch_csv(url):
    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

        return pd.read_csv(StringIO(response.text))

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def get_data():
    folder = "data"
    file_path = Path(f"{folder}/cell_types_in_anatomical_structurescts_per_as.csv")

    if file_path.exists():
        df = pd.read_csv(file_path)
        return df
    else:
        url = "https://apps.humanatlas.io/api/grlc/hra-pop/cell_types_in_anatomical_structurescts_per_as.csv"

        df = fetch_csv(url)

        if df is not None:
            print(df.head())

            os.makedirs(folder, exist_ok=True)
            df.to_csv(file_path, index=False)

            return df
        else:
            print("Failed to retrieve data.")
            return None


def plot_grouped_bars(df, top_n=15):

    plt.rcParams.update(
        {
            "font.size": 15,
            "axes.titlesize": 16,
            "axes.labelsize": 18,
            "xtick.labelsize": 15,
            "ytick.labelsize": 15,
            "legend.fontsize": 15,
            "figure.titlesize": 18,
        }
    )

    df = df[(df["sex"].str.lower() == "female") & (df["organ"] == "heart")].copy()
    df["cell_percentage"] = df["cell_percentage"] * 100

    top_cell_types = (
        df.groupby("cell_label")["cell_percentage"]
        .mean()
        .sort_values(ascending=False)
        .head(top_n)
        .index
    )
    df = df[df["cell_label"].isin(top_cell_types)].copy()

    pivot = df.pivot_table(
        index="cell_label", columns="tool", values="cell_percentage", aggfunc="mean"
    ).fillna(0)

    ax = pivot.plot(kind="bar", figsize=(14, 7), width=0.85)
    ax.set_xlabel("Cell Type")
    ax.set_ylabel("Percentage (%)")
    ax.set_title(f"Female Heart: Top-{top_n} Cell Type Percentage by Tool")
    plt.xticks(rotation=45, ha="right")

    # ---- manual legend labels ----
    custom_labels = ["Azimuth", "CellTypist"]
    ax.legend(custom_labels, title="Tool")

    plt.tight_layout()
    plt.show()


def main():
    install_requirements()
    df = get_data()
    print(df.head())

    if df is not None:
        print("\nData loaded successfully.")
        plot_grouped_bars(df, top_n=25)
    else:
        print("\nNo data available.")
        return


if __name__ == "__main__":
    main()
