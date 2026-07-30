#!/usr/bin/env python3
"""
palette.py — A5's colors for the top-9-granular + Other scheme.

The 9 base hues (LEVEL2_TOP9_COLORS) are now shared.BASE_HUES, not
A5-specific — a given supertree category means the same color family in
A5 and HRA. What A5 supplies
locally is OTHER_COLOR (the aggregate "Other" bucket) and BG_MODE, which
tells shared.build_top9_granular_color_scheme() to shade those hues for a
light background (#FAF8F5): the wide 0.20-0.88 lightness range gives
genuinely dark shades, since they still contrast fine on paper/on light.

Imported by 30, 40, 50, 51 — all four pass these into
build_top9_granular_color_scheme() so GLB markers, the CSV hex_color
column, the HTML/JSON legend, and the chart legend all match.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
from shared import BASE_HUES

LEVEL2_TOP9_COLORS: List[str] = BASE_HUES

OTHER_COLOR: str = "#b15928"

BG_MODE: str = "light"