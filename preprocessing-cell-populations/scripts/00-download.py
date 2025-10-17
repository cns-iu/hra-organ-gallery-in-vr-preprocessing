"""
Download cell population CSVs from the HRA grlc API.
"""

import os
import requests
import yaml
from pathlib import Path
from tqdm import tqdm

def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def download_file(url, output_path):
    """Download a file from URL with progress bar"""
    print(f"Downloading from: {url}")
    
    response = requests.get(url, stream=True, headers={
        'User-Agent': 'Python Script',
        'Accept': 'text/csv'
    })
    
    if response.status_code != 200:
        raise Exception(f"Failed to download. Status code: {response.status_code}")
    
    # Get file size for progress bar
    total_size = int(response.headers.get('content-length', 0))
    
    # Download with progress bar
    with open(output_path, 'wb') as f, tqdm(
        desc=output_path.name,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            progress_bar.update(len(chunk))
    
    print(f"✓ Saved to: {output_path}\n")

def main():
    # Load configuration
    config = load_config()
    
    # Get paths relative to this script
    script_dir = Path(__file__).parent
    input_dir = (script_dir / config['paths']['input_dir']).resolve()
    
    # Create input directory if it doesn't exist
    input_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("HRA Cell Populations - Download Script")
    print("=" * 60)
    print()
    
    # Download AS CSV
    print("1. Downloading Anatomical Structure (AS) data...")
    as_url = config['urls']['anatomical_structure']
    as_path = input_dir / "as-ct-hra-pop.csv"
    download_file(as_url, as_path)
    
    # Download ES CSV
    print("2. Downloading Extraction Site (ES) data...")
    es_url = config['urls']['extraction_site']
    es_path = input_dir / "es-ct-hra-pop.csv"
    download_file(es_url, es_path)
    
    print("=" * 60)
    print("✓ Download complete!")
    print(f"Files saved to: {input_dir}")
    print("=" * 60)
    print()
    print("Next step: Run 01-process.py to convert CSVs to YAML")

if __name__ == "__main__":
    main()