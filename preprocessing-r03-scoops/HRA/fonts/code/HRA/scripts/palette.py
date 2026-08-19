#!/usr/bin/env python3
"""
palette.py — HRA's colors for the top-9-granular + Other scheme.

The 10 fixed AS/2 category colors (LEVEL2_TOP9_COLORS) are
shared.CT_COLORS — the same fixed name->hex lookup A5 uses — so a given
supertree category (e.g. "muscle cell") means the same color, in the
same order-independent way, in both projects. "endothelial cell" is
always #e31a1c, never reassigned based on which order categories happen
to appear in for a given organ/sex/tool block. HRA previously had its
own distinct bright palette; that's gone in favor of one shared identity
across the whole atlas.

What HRA supplies locally is OTHER_COLOR and BG_MODE, which tells
shared.build_top9_granular_color_scheme() to shade those same hues for a
dark VR background (#0F1117) instead: BG_MODE="dark" shifts the whole
shading lightness range brighter (see shared.BG_LIGHTNESS_RANGES) so no
shade gets dark enough to disappear into near-black, while keeping the
exact same hue/saturation as A5's version of that category.

Imported by 30, 40, 50, 60 — all four pass these into
build_top9_granular_color_scheme() so GLB markers, the CSV hex_color
column, the HTML/JSON legend, and the color spreadsheet all match.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
from shared import CT_COLORS

LEVEL2_TOP9_COLORS: Dict[str, str] = CT_COLORS

OTHER_COLOR: str = "#C08552"

# Passed as bg_mode= into shared.build_top9_granular_color_scheme().
BG_MODE: str = "dark"
