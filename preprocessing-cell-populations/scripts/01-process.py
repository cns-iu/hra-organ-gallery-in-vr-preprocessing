"""
Process downloaded CSVs and convert to YAML format for Unity.
"""

import pandas as pd
import yaml
from pathlib import Path
from tqdm import tqdm

def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def csv_to_dict_list(csv_path, expected_columns):
    """
    Load CSV and convert to list of dictionaries.
    Validates that expected columns exist.
    """
    print(f"Reading: {csv_path.name}")
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    print(f"  Rows: {len(df):,}")
    print(f"  Columns: {', '.join(df.columns.tolist())}")
    
    # Validate columns
    missing_cols = set(expected_columns) - set(df.columns)
    if missing_cols:
        print(f"  ⚠️  Warning: Missing columns: {missing_cols}")
    
    # Convert to list of dicts with progress bar
    records = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="  Processing rows"):
        # Convert row to dict, handling NaN values
        record = row.where(pd.notna(row), None).to_dict()
        records.append(record)
    
    return records

def save_yaml(data, output_path):
    """Save data as YAML file"""
    print(f"Saving: {output_path.name}")
    
    with open(output_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"  ✓ Saved {len(data):,} rows\n")

def main():
    # Load configuration
    config = load_config()
    
    # Get paths relative to this script
    script_dir = Path(__file__).parent
    input_dir = (script_dir / config['paths']['input_dir']).resolve()
    output_dir = (script_dir / config['paths']['output_dir']).resolve()
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("HRA Cell Populations - Process Script")
    print("=" * 60)
    print()
    
    # Process AS CSV
    print("1. Processing Anatomical Structure (AS) data...")
    as_csv = input_dir / "as-ct-hra-pop.csv"
    as_data = csv_to_dict_list(as_csv, config['columns']['anatomical_structure'])
    as_output = output_dir / config['output_files']['anatomical_structure']
    save_yaml(as_data, as_output)
    
    # Process ES CSV
    print("2. Processing Extraction Site (ES) data...")
    es_csv = input_dir / "es-ct-hra-pop.csv"
    es_data = csv_to_dict_list(es_csv, config['columns']['extraction_site'])
    es_output = output_dir / config['output_files']['extraction_site']
    save_yaml(es_data, es_output)
    
    print("=" * 60)
    print("✓ Processing complete!")
    print(f"Files saved to: {output_dir}")
    print("=" * 60)
    print()
    print("YAML files ready for Unity:")
    print(f"  - {as_output.name}")
    print(f"  - {es_output.name}")

if __name__ == "__main__":
    main()