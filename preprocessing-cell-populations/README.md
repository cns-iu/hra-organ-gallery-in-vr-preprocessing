# Cell Populations Preprocessing

Pipeline to download and process cell population data from the HRA API for use in the HRA Organ Gallery VR application.

## Overview

This pipeline downloads cell summary data for:
- **Anatomical Structures (AS)**: Cell types per anatomical structure
- **Extraction Sites (ES)**: Cell types per tissue extraction site

The data is converted from CSV to YAML format for easy loading in Unity.

## Setup
```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Download CSVs
```bash
python scripts/00-download.py
```

Downloads CSV files from the HRA grlc API to the `input/` folder.

### Step 2: Process to YAML
```bash
python scripts/01-process.py
```

Converts CSV files to YAML format and saves to the `output/` folder.

## Output Files

- `output/as-cell-summaries.yaml` - Anatomical Structure cell summaries (~8,800 rows)
- `output/es-cell-summaries.yaml` - Extraction Site cell summaries (~14,300 rows)

## Data Structure

### AS (Anatomical Structure)
- organ, as, as_label, sex, tool, modality, cell_id, cell_label, cell_count, cell_percentage, dataset_count

### ES (Extraction Site)
- organ_id, organ, extraction_site, sex, tool, modality, cell_id, cell_label, cell_count, cell_percentage

## Notes

- Input CSVs and output YAMLs are gitignored (can be regenerated)
- Run the pipeline whenever you need updated data from the HRA API