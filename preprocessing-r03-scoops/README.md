# HRA 3D Cell Population Pipeline

Generates annotated 3D GLB files for HRA organs with cell type markers placed inside anatomical structures, using data from [HRApop](https://humanatlas.io) and the [HRA 3D Cell Generation API](https://apps.humanatlas.io/api/v1/mesh-3d-cell-population).

---

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Usage

1. Edit `config.yaml` to set your organ, sex, tool, and marker settings.
2. Run the pipeline:

```bash
python setup_and_run.py
```

---

## Output Structure

```
Outputs/
├── downloaded_organs/
│   └── 3d-vh-f-heart.glb
└── annotated_organs/
    └── heart/
        ├── glb/    ← GLB with cell markers
        ├── csv/    ← per-marker data: position, cell type, cell ID, color, % 
        ├── html/   ← visual legend: color key, AS table, size reference
        └── json/   ← distribution data and legend metadata
```

Output filenames include organ, sex, tool, and shape:
```
3d-vh-f-heart-all-as-azimuth-sphere-hra-pop.glb
```

---

## Scripts

| Script | What it does |
|---|---|
| `10_download_organs.py` | Downloads organ GLB from HRA reference organs API |
| `20_fetch_cell_distribution.py` | Fetches cell type distributions per AS from HRApop |
| `30_generate_markers.py` | Places 3D cell markers and exports enriched GLB + CSV |
| `40_generate_legend.py` | Generates HTML legend and JSON metadata |

---

## Supported Organs

| Organ | Sex | Tool |
|---|---|---|
| Heart | Female | Azimuth, CellTypist |
| Kidney (L/R) | Female, Male | Azimuth |