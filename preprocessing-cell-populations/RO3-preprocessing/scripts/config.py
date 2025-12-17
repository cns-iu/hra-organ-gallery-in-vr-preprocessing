"""
Configuration file for RO3 (Heart) preprocessing pipeline
"""

# Data source URL
DATA_URL = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/hra-pop//cell_types_in_anatomical_structurescts_per_as.csv"

# Filters for our specific use case
ORGAN_FILTER = None
TOOLS_FILTER = ["azimuth", "celltypist"]
SEX_FILTER = ["male", "female"]

# Paths
INPUT_DIR = "../input"
OUTPUT_DIR = "../output/pngs"

# Output CSV (filtered data)
FILTERED_CSV = "../input/filtered_data.csv"
ORIGINAL_CSV = "../input/as-cell-populations.csv"

# Reference organ ID prefix 
REF_ORGAN_ID = {
    "male": "m",
    "female": "f"
}
ORGAN_NAME = "Heart"

# Chart configuration
LABEL_FONT_FAMILY = 'Metropolis, Arial, sans-serif'
FONT_FAMILY = 'Nunito, Arial, sans-serif'
CHART_WIDTH = 1240
CHART_HEIGHT = 800

# HRA Color Palette (10 colors: 9 cell types + Other)
HRA_COLORS = [
    '#70A5A8',  # teal
    '#CD8490',  # pink/mauve
    '#8DC599',  # green
    '#F9CE8D',  # orange/peach
    '#7495AE',  # blue-gray
    '#AADCDF',  # light cyan
    '#EDB8AC',  # salmon
    '#A294C9',  # purple
    '#E97B74',  # coral/red
    '#898AB4',  # gray (for "Other")
]

# Chart styling (from Bar Graph Specifications)
CHART_BG_COLOR = '#263139'       # Graph container fill
TEXT_COLOR = '#fcfcfc'           # White text
BAR_STROKE_COLOR = '#BDC6D7'     # Bar outline
BAR_STROKE_WIDTH = 0.5
X_AXIS_ANGLE = -21.4             # X-axis label angle
