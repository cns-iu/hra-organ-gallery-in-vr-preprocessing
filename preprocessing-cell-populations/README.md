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

## Generating PNG Visualizations (RO3 - Heart)

This section describes how to generate PNG visualizations for heart cell population data.

### Prerequisites

1. **Install dependencies:**
   ```bash
   cd RO3-preprocessing
   pip install -r requirements.txt
   ```

### Step-by-Step Process

1. **Download raw data:**
   ```bash
   cd scripts
   python download_data.py
   ```
   Downloads the cell population CSV from the HRA API to `../input/as-cell-populations.csv`

2. **Filter and process data:** DONT USE IF GENERATING FOR ALL ORGANS
   ```bash
   python process_data.py
   ```
   Filters the data for heart organ only (azimuth/celltypist tools, male/female) and saves to `../input/filtered_data.csv`


3. **Generate PNG charts:** IF GENERATING FOR PARTICULAR ORGANS - CHANGE load_csv_data in generate_png.py --> config.FILTERED_CSV
   ```bash
   python generate_pngs.py
   ```
   Generates two sets of combined anatomical structure charts:
   - **With legend/title**: Saved to `../output/pngs/with_legend/`
   - **Without legend/title**: Saved to `../output/pngs/no_legend/`
   
   PNG files are named: `{ref_organ_id}-{organ_id}-{organ}-{tool}.png`
   - Example: `m-UBERON_0000948-heart-azimuth.png`

### Output

- `input/heart_filtered.csv` - Filtered heart cell population data
- `output/pngs/with_legend/*.png` - Charts with legend and titles
- `output/pngs/no_legend/*.png` - Charts without legend and titles

## Notes

- Input CSVs and output YAMLs are gitignored (can be regenerated)
- Run the pipeline whenever you need updated data from the HRA API