#!/usr/bin/env python3
"""
palette.py — A5's colors for the top-9-granular + Other scheme.

The 10 fixed AS/2 category colors (LEVEL2_TOP9_COLORS) are
shared.CT_COLORS, not A5-specific — a given supertree category (e.g.
"endothelial cell") means the same color, everywhere, in every organ/
sex/tool block, in both A5 and HRA. This is a fixed name->hex lookup, not
a positional palette — "endothelial cell" is always #e31a1c, never
reassigned based on which order categories happen to appear in for a
given block. What A5 supplies locally is OTHER_COLOR (the aggregate
"Other" bucket) and BG_MODE, which tells
shared.build_top9_granular_color_scheme() to shade those hues for a
light background (#FAF8F5): the wide 0.20-0.88 lightness range gives
genuinely dark shades, since they still contrast fine on paper/on light.

Imported by 30, 40, 50, 51, 60 — all five pass these into
build_top9_granular_color_scheme() so GLB markers, the CSV hex_color
column, the HTML/JSON legend, the chart legend, and the color spreadsheet
all match.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
from shared import CT_COLORS

LEVEL2_TOP9_COLORS: Dict[str, str] = CT_COLORS

OTHER_COLOR: str = "#b15928"

# Passed as bg_mode= into shared.build_top9_granular_color_scheme().
BG_MODE: str = "light"
