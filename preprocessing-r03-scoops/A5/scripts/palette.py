#!/usr/bin/env python3
"""
palette.py — A5's colors for the top-9-granular + Other scheme.

Split out of shared.py so A5 and HRA can each supply their own colors to
the same shared.build_top9_granular_color_scheme() algorithm. A5 renders
on a light background (#FAF8F5), hence these saturated ColorBrewer
"Paired" values.

Imported by 30, 40, 50, 51 — all four pass these into
build_top9_granular_color_scheme() so GLB markers, the CSV hex_color
column, the HTML/JSON legend, and the chart legend all match.
"""

from __future__ import annotations

from typing import List

LEVEL2_TOP9_COLORS: List[str] = [
    "#1f78b4",
    "#33a02c",
    "#e31a1c",
    "#ff7f00",
    "#6a3d9a",
    "#ffff99",
    "#a6cee3",
    "#b2df8a",
    "#fb9a99",
]

OTHER_COLOR: str = "#b15928"