"""
Configuration file for RO3 (Heart) preprocessing pipeline
"""

# Data source URL
DATA_URL = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/hra-pop//cell_types_in_anatomical_structurescts_per_as.csv"

# Filters for our specific use case
ORGAN_FILTER = "heart"
TOOLS_FILTER = ["azimuth", "celltypist"]
SEX_FILTER = ["male", "female"]

# Paths
INPUT_DIR = "../input"
OUTPUT_DIR = "../output/pngs"

# Output CSV (filtered data)
FILTERED_CSV = "../input/heart_filtered.csv"

# Reference organ ID for naming
REF_ORGAN_ID = "VHMHeart"  # Heart's ID in the HRA

# Chart configuration
CHART_WIDTH = 1200
CHART_HEIGHT = 800
CHART_DPI = 300  # High resolution
