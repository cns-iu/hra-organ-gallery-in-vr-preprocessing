#!/usr/bin/env python3
"""
52_faceted_bar_graph.py — Grouped bar chart of cell-type
composition by anatomical structure. One group per cell type, one
bar per AS within the group. Bars are colored by AS (AS_COLORS); the
legend shows a color swatch per AS.

Reads:  outputs/annotated organs/<organ>/json/<stem>_distribution.json
Writes: outputs/annotated organs/<organ>/svg/faceted/<stem>-grouped-by-AS.svg

Edit AS_LABELS / UNION_TOP_N_PER_AS / AS_COLORS to reuse for a different
organ or AS set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config,
    canonicalize_cell_label,
    normalize_cell_label_key,
    resolve_glb_filename,
)
from palette import OTHER_COLOR

# =============================================================================
# EDITABLE PARAMETERS
# =============================================================================

AS_LABELS: List[str] = [
    "right cardiac atrium",
    "left cardiac atrium",
    "heart right ventricle",
    "heart left ventricle",
    "interventricular septum",
    "Posteromedial head of posterior papillary muscle of left ventricle",
]
AS_SHORT_LABELS: Dict[str, str] = {
    "right cardiac atrium": "RA",
    "left cardiac atrium": "LA",
    "heart right ventricle": "RV",
    "heart left ventricle": "LV",
    "interventricular septum": "IVS",
    "Posteromedial head of posterior papillary muscle of left ventricle": "PPM",
}
AS_LEGEND_LABELS: Dict[str, str] = {
    "right cardiac atrium": "Right atrium",
    "left cardiac atrium": "Left atrium",
    "heart right ventricle": "Right ventricle",
    "heart left ventricle": "Left ventricle",
    "interventricular septum": "Interventricular septum",
    "Posteromedial head of posterior papillary muscle of left ventricle": "Posteromedial papillary muscle",
}
# Casing must match the distribution JSON's as_labels exactly.
AS_COLORS: Dict[str, str] = {
    "heart left ventricle": "#8dd3c7",
    "heart right ventricle": "#ffffb3",
    "interventricular septum": "#bebada",
    "left cardiac atrium": "#fb8072",
    "Posteromedial head of posterior papillary muscle of left ventricle": "#80b1d3",
    "right cardiac atrium": "#fdb462",
}
UNION_TOP_N_PER_AS = 3     # each AS's own top-N contributes to the shared category list
OMIT_BELOW_PCT = 2.0       # don't draw a bar below this threshold

BG_COLOR       = "#FAF8F5"
TEXT_COLOR     = "#171616"
MUTED_COLOR    = "#444444"
GRID_COLOR     = "#ACA8A8"
AXIS_COLOR     = "#444444"

BAR_WIDTH      = 15
BAR_GAP        = 3    # gap between adjacent AS bars within one group
GROUP_GAP      = 50   # gap between one cell type's group and the next
LEFT_PAD       = 70   # room for the y-axis
RIGHT_PAD      = 40
PLOT_TOP       = 70
PLOT_BOTTOM    = 340  # y of the 0% baseline
LABEL_BAND     = 200  # vertical room below baseline for rotated category labels
FONT_FAMILY    = "Nunito, Arial, Helvetica, sans-serif"

PRINT_WIDTH_PX  = 1470
PRINT_HEIGHT_PX = 546


# =============================================================================
# Data
# =============================================================================

def canonical_pct_within_as(dist_data: dict, as_label: str) -> Dict[str, float]:
    """canonical cell label -> within-AS percentage (0-100), for one AS."""
    per_as_norm = dist_data["per_as_normalized"][as_label]
    result: Dict[str, float] = {}
    for label, frac in per_as_norm.items():
        result[canonicalize_cell_label(label)] = 100.0 * frac
    return result


def build_shared_category_list(
    dist_data: dict,
    as_labels: List[str],
    union_top_n: int,
) -> List[str]:
    """Union of each AS's own top-N (by within-AS %), in first-seen order
    walking as_labels left to right. Every AS then renders bars for this
    same category list."""
    ordered: List[str] = []
    for as_label in as_labels:
        pct_by_label = canonical_pct_within_as(dist_data, as_label)
        ranked = sorted(pct_by_label.items(), key=lambda kv: kv[1], reverse=True)
        for label, _pct in ranked[:union_top_n]:
            if label not in ordered:
                ordered.append(label)
    return ordered


def wrap_label(text: str, max_width_px: float, font_size: float = 13.0,
               avg_char_width_ratio: float = 0.55) -> List[str]:
    """Word-wrap using an estimated char width (no font-metrics dependency)."""
    max_chars = max(1, int(max_width_px / (font_size * avg_char_width_ratio)))
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def sentence_case(label: str) -> str:
    """Display-only; underlying category key is untouched."""
    if not label:
        return label
    return label[0].upper() + label[1:].lower()


def compute_group_data(
    dist_data: dict,
    categories: List[str],
    as_labels: List[str],
) -> Dict[str, List[Tuple[str, float, str]]]:
    """category -> list of (as_label, pct, hexcolor), one entry per AS."""
    pct_by_as = {as_label: canonical_pct_within_as(dist_data, as_label) for as_label in as_labels}
    groups: Dict[str, List[Tuple[str, float, str]]] = {}
    for label in categories:
        groups[label] = [
            (as_label, pct_by_as[as_label].get(label, 0.0), AS_COLORS.get(as_label, OTHER_COLOR))
            for as_label in as_labels
        ]
    return groups


# =============================================================================
# SVG rendering
# =============================================================================

LABEL_LINE_H = 16  # line height for wrapped horizontal category labels


def build_svg(
    groups: Dict[str, List[Tuple[str, float, str]]],
    categories: List[str],
    as_labels: List[str],
    title: str,
    horizontal_labels: bool = False,
    plot_bottom: float = PLOT_BOTTOM,
    legend_mode: str = "bottom_box",
    category_label_font_size: float = 14.0,
    category_label_line_h: float = LABEL_LINE_H,
    legend_single_line: bool = False,
    legend_items_per_row: int = None,
    legend_font_size: float = 13.0,
    axis_title_font_size: float = 14.0,
    bar_value_font_size: float = 12.0,
    canvas_width: float = None,
    canvas_height: float = None,
) -> str:
    """One shared axis, one group of bars per category (cell type). Bars
    are colored by AS (AS_COLORS) and decoded via a color-swatch legend.

    legend_mode: "bottom_box" (boxed callout below the axis title) or
    "top_inline" (single unboxed line under the title).
    canvas_width/canvas_height: pin the SVG to a fixed size; canvas_height
    only applies with legend_mode="bottom_box" (plot_bottom is back-solved
    to fit).
    legend_single_line / legend_items_per_row: control how legend entries
    wrap into rows when legend_mode="bottom_box".
    """
    n_bars_per_group = len(as_labels)
    group_width = n_bars_per_group * BAR_WIDTH + (n_bars_per_group - 1) * BAR_GAP
    n_groups = len(categories)
    natural_total_width = LEFT_PAD + n_groups * group_width + (n_groups - 1) * GROUP_GAP + RIGHT_PAD
    total_width = canvas_width if canvas_width is not None else natural_total_width
    x_offset = (total_width - natural_total_width) / 2 if canvas_width is not None else 0.0
    effective_left_pad = LEFT_PAD + x_offset

    x0 = effective_left_pad
    x1 = effective_left_pad + n_groups * group_width + (n_groups - 1) * GROUP_GAP
    plot_center_x = (x0 + x1) / 2

    legend_entries = [(AS_COLORS.get(a, OTHER_COLOR), AS_LEGEND_LABELS.get(a, a)) for a in as_labels]
    legend_lines = [f'{AS_SHORT_LABELS.get(a, a)} = {AS_LEGEND_LABELS.get(a, a)}' for a in as_labels]

    def legend_row_count() -> int:
        if legend_single_line:
            return 1
        if legend_items_per_row:
            return -(-len(legend_entries) // legend_items_per_row)  # ceil division
        return len(legend_entries)

    if horizontal_labels:
        max_label_lines = max(
            (len(wrap_label(label, max_width_px=group_width, font_size=category_label_font_size))
             for label in categories),
            default=1,
        )
    else:
        max_label_lines = 1

    if canvas_height is not None and legend_mode == "bottom_box":
        legend_line_h = 18
        legend_box_h = 14 + legend_row_count() * legend_line_h
        bottom_margin = 18
        if horizontal_labels:
            label_stack_h = 30 + max_label_lines * category_label_line_h
        else:
            label_stack_h = LABEL_BAND - 10
        plot_bottom = canvas_height - label_stack_h - 12 - legend_box_h - bottom_margin

    top_legend_line_h = 16
    top_legend_start_y = 56
    if legend_mode == "top_inline":
        legend_bottom_y = top_legend_start_y + (len(legend_lines) - 1) * top_legend_line_h
        plot_top = max(PLOT_TOP, legend_bottom_y + 14)
    else:
        plot_top = PLOT_TOP

    max_pct = max((pct for entries in groups.values() for _as, pct, _h in entries), default=1.0)
    axis_max = max(5.0, (int(max_pct / 5) + 1) * 5)
    plot_height = plot_bottom - plot_top

    def y_for(pct: float) -> float:
        return plot_bottom - (pct / axis_max) * plot_height

    body_parts: List[str] = []
    body_parts.append(f'<text x="{total_width/2}" y="30" font-size="16" font-weight="bold" '
                       f'fill="{TEXT_COLOR}" text-anchor="middle">{title}</text>')

    if legend_mode == "top_inline":
        for i, line in enumerate(legend_lines):
            body_parts.append(f'<text x="{plot_center_x:.1f}" y="{top_legend_start_y+i*top_legend_line_h:.1f}" '
                               f'font-size="{legend_font_size:.0f}" fill="{MUTED_COLOR}" text-anchor="middle">{line}</text>')

    step = axis_max / 5
    for i in range(6):
        pct = i * step
        y = y_for(pct)
        body_parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                           f'stroke="{GRID_COLOR}" stroke-width="1"/>')
        body_parts.append(f'<text x="{x0 - 10}" y="{y+4:.1f}" font-size="14" fill="{MUTED_COLOR}" '
                           f'text-anchor="end">{pct:.0f}%</text>')
    y_axis_title_x = 22 + x_offset
    body_parts.append(f'<text x="{y_axis_title_x:.1f}" y="{(plot_top+plot_bottom)/2:.1f}" font-size="{axis_title_font_size:.0f}" fill="{TEXT_COLOR}" '
                       f'transform="rotate(-90 {y_axis_title_x:.1f} {(plot_top+plot_bottom)/2:.1f})" text-anchor="middle">Cells (%)</text>')

    body_parts.append(f'<line x1="{x0}" y1="{plot_top}" x2="{x0}" y2="{plot_bottom}" '
                       f'stroke="{AXIS_COLOR}" stroke-width="1.2"/>')
    body_parts.append(f'<line x1="{x0}" y1="{plot_bottom}" x2="{x1}" y2="{plot_bottom}" '
                       f'stroke="{AXIS_COLOR}" stroke-width="1.2"/>')

    for g_idx, label in enumerate(categories):
        group_x0 = effective_left_pad + g_idx * (group_width + GROUP_GAP)
        entries = groups[label]

        for b_idx, (as_label, pct, hexcolor) in enumerate(entries):
            bar_x = group_x0 + b_idx * (BAR_WIDTH + BAR_GAP)
            if pct >= OMIT_BELOW_PCT:
                bar_y = y_for(pct)
                bar_h = plot_bottom - bar_y
                body_parts.append(f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{BAR_WIDTH}" height="{bar_h:.1f}" '
                                   f'fill="{hexcolor}"/>')
                body_parts.append(f'<text x="{bar_x+BAR_WIDTH/2:.1f}" y="{bar_y-8:.1f}" font-size="{bar_value_font_size:.0f}" '
                                   f'fill="{TEXT_COLOR}" text-anchor="middle">{pct:.0f}%</text>')

        display_label = sentence_case(label)
        group_center_x = group_x0 + group_width / 2
        if horizontal_labels:
            lines = wrap_label(display_label, max_width_px=group_width, font_size=category_label_font_size)
            for li, line in enumerate(lines):
                body_parts.append(f'<text x="{group_center_x:.1f}" y="{plot_bottom+30+li*category_label_line_h:.1f}" '
                                   f'font-size="{category_label_font_size:.0f}" fill="{TEXT_COLOR}" text-anchor="middle">{line}</text>')
        else:
            body_parts.append(f'<text x="{group_center_x:.1f}" y="{plot_bottom+30:.1f}" font-size="14" fill="{TEXT_COLOR}" '
                               f'text-anchor="end" transform="rotate(-90 {group_center_x:.1f} {plot_bottom+30:.1f})">{display_label}</text>')

    if horizontal_labels:
        axis_title_y = plot_bottom + 30 + max_label_lines * category_label_line_h + 12
    else:
        axis_title_y = plot_bottom + LABEL_BAND - 10
    body_parts.append(f'<text x="{(x0+x1)/2:.1f}" y="{axis_title_y}" font-size="{axis_title_font_size:.0f}" '
                       f'fill="{TEXT_COLOR}" text-anchor="middle">Cell type</text>')

    bottom_margin = 18
    swatch_size = 13
    swatch_text_gap = 6
    swatch_item_gap = 26
    if legend_mode == "bottom_box":
        legend_line_h = 18
        item_widths = [
            swatch_size + swatch_text_gap + len(text) * legend_font_size * 0.55
            for _color, text in legend_entries
        ]
        if legend_single_line:
            legend_rows_entries = [list(zip(legend_entries, item_widths))]
        elif legend_items_per_row:
            paired = list(zip(legend_entries, item_widths))
            legend_rows_entries = [
                paired[i:i + legend_items_per_row]
                for i in range(0, len(paired), legend_items_per_row)
            ]
        else:
            legend_rows_entries = [[pair] for pair in zip(legend_entries, item_widths)]

        n_cols = max(len(row) for row in legend_rows_entries)
        col_widths = [
            max((row[c][1] for row in legend_rows_entries if c < len(row)), default=0.0)
            for c in range(n_cols)
        ]
        col_x_offsets = []
        running = 0.0
        for w in col_widths:
            col_x_offsets.append(running)
            running += w + swatch_item_gap
        grid_width = running - swatch_item_gap if col_widths else 0.0

        legend_box_w = max(260.0, grid_width + 40)
        legend_box_h = 16 + len(legend_rows_entries) * legend_line_h
        legend_x = plot_center_x - legend_box_w / 2
        legend_y = axis_title_y + 20
        body_parts.append(f'<rect x="{legend_x:.1f}" y="{legend_y:.1f}" width="{legend_box_w:.1f}" height="{legend_box_h}" '
                           f'fill="{BG_COLOR}" stroke="#dddddd" stroke-width="1"/>')
        grid_left = plot_center_x - grid_width / 2
        for row_idx, row in enumerate(legend_rows_entries):
            row_y = legend_y + 22 + row_idx * legend_line_h
            swatch_y = row_y - swatch_size + 3
            for col_idx, (color, text) in enumerate(e for e, _w in row):
                item_x = grid_left + col_x_offsets[col_idx]
                body_parts.append(f'<rect x="{item_x:.1f}" y="{swatch_y:.1f}" width="{swatch_size}" height="{swatch_size}" '
                                   f'fill="{color}" stroke="#999999" stroke-width="0.5"/>')
                body_parts.append(f'<text x="{item_x+swatch_size+swatch_text_gap:.1f}" y="{row_y:.1f}" '
                                   f'font-size="{legend_font_size:.0f}" fill="{TEXT_COLOR}" text-anchor="start">{text}</text>')
        total_height = canvas_height if canvas_height is not None else legend_y + legend_box_h + bottom_margin
    else:
        total_height = axis_title_y + bottom_margin

    header = (
        f'<svg viewBox="0 0 {total_width} {total_height:.0f}" '
        f'width="{total_width}" height="{total_height:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{FONT_FAMILY}">'
        f'<rect x="0" y="0" width="{total_width}" height="{total_height:.0f}" fill="{BG_COLOR}"/>'
    )
    return header + "\n".join(body_parts) + "</svg>"


def build_print_svg(
    groups: Dict[str, List[Tuple[str, float, str]]],
    categories: List[str],
    as_labels: List[str],
    title: str,
    width_px: float,
    height_px: float,
) -> str:
    """Fixed-canvas print variant. Content is laid out to fit width_px/
    height_px exactly rather than the canvas growing to fit content."""
    n_bars_per_group = len(as_labels)
    n_groups = len(categories)

    left_pad = 90
    right_pad = 30
    group_gap = 30
    bar_gap = 10
    available = width_px - left_pad - right_pad - (n_groups - 1) * group_gap
    group_width = available / n_groups
    bar_width = (group_width - (n_bars_per_group - 1) * bar_gap) / n_bars_per_group

    title_font = 22
    legend_font = 15
    axis_font = 16
    value_font = 14
    tick_font = 13
    label_font = 15
    label_line_h = 19

    x0 = left_pad
    x1 = left_pad + n_groups * group_width + (n_groups - 1) * group_gap
    plot_center_x = (x0 + x1) / 2

    as_legend_lines = [f'{AS_SHORT_LABELS.get(a, a)} = {AS_LEGEND_LABELS.get(a, a)}' for a in as_labels]
    legend_line_h = 19
    legend_start_y = 50
    legend_bottom_y = legend_start_y + (len(as_legend_lines) - 1) * legend_line_h
    plot_top = max(68, legend_bottom_y + 14)

    max_label_lines = max(
        (len(wrap_label(label, max_width_px=group_width, font_size=label_font)) for label in categories),
        default=1,
    )
    bottom_stack = 18 + 6 + max_label_lines * label_line_h + 10
    plot_bottom = height_px - bottom_stack

    max_pct = max((pct for entries in groups.values() for _as, pct, _h in entries), default=1.0)
    axis_max = max(5.0, (int(max_pct / 5) + 1) * 5)
    plot_height = plot_bottom - plot_top

    def y_for(pct: float) -> float:
        return plot_bottom - (pct / axis_max) * plot_height

    body_parts: List[str] = []
    body_parts.append(f'<text x="{plot_center_x:.1f}" y="26" font-size="{title_font}" font-weight="bold" '
                       f'fill="{TEXT_COLOR}" text-anchor="middle">{title}</text>')

    for i, line in enumerate(as_legend_lines):
        body_parts.append(f'<text x="{plot_center_x:.1f}" y="{legend_start_y+i*legend_line_h:.1f}" '
                           f'font-size="{legend_font}" fill="{MUTED_COLOR}" text-anchor="middle">{line}</text>')

    step = axis_max / 5
    for i in range(6):
        pct = i * step
        y = y_for(pct)
        body_parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                           f'stroke="{GRID_COLOR}" stroke-width="1"/>')
        body_parts.append(f'<text x="{x0 - 10}" y="{y+5:.1f}" font-size="{axis_font}" fill="{MUTED_COLOR}" '
                           f'text-anchor="end">{pct:.0f}%</text>')
    body_parts.append(f'<text x="26" y="{(plot_top+plot_bottom)/2:.1f}" font-size="{axis_font}" fill="{TEXT_COLOR}" '
                       f'transform="rotate(-90 26 {(plot_top+plot_bottom)/2:.1f})" text-anchor="middle">Cells (%)</text>')

    body_parts.append(f'<line x1="{x0}" y1="{plot_top}" x2="{x0}" y2="{plot_bottom:.1f}" '
                       f'stroke="{AXIS_COLOR}" stroke-width="1.2"/>')
    body_parts.append(f'<line x1="{x0}" y1="{plot_bottom:.1f}" x2="{x1}" y2="{plot_bottom:.1f}" '
                       f'stroke="{AXIS_COLOR}" stroke-width="1.2"/>')

    for g_idx, label in enumerate(categories):
        group_x0 = left_pad + g_idx * (group_width + group_gap)
        entries = groups[label]

        for b_idx, (as_label, pct, hexcolor) in enumerate(entries):
            bar_x = group_x0 + b_idx * (bar_width + bar_gap)
            if pct >= OMIT_BELOW_PCT:
                bar_y = y_for(pct)
                bar_h = plot_bottom - bar_y
                body_parts.append(f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" '
                                   f'fill="{hexcolor}"/>')
                body_parts.append(f'<text x="{bar_x+bar_width/2:.1f}" y="{bar_y-8:.1f}" font-size="{value_font}" '
                                   f'fill="{TEXT_COLOR}" text-anchor="middle">{pct:.0f}%</text>')
                body_parts.append(f'<text x="{bar_x+bar_width/2:.1f}" y="{plot_bottom+18:.1f}" font-size="{tick_font}" '
                                   f'fill="{MUTED_COLOR}" text-anchor="middle">{AS_SHORT_LABELS.get(as_label, as_label)}</text>')

        group_center_x = group_x0 + group_width / 2
        lines = wrap_label(label, max_width_px=group_width, font_size=label_font)
        label_top_y = plot_bottom + 18 + 6 + label_line_h
        for li, line in enumerate(lines[:max_label_lines]):
            body_parts.append(f'<text x="{group_center_x:.1f}" y="{label_top_y+li*label_line_h:.1f}" '
                               f'font-size="{label_font}" fill="{TEXT_COLOR}" text-anchor="middle">{line}</text>')

    header = (
        f'<svg viewBox="0 0 {width_px:.0f} {height_px:.0f}" width="{width_px:.0f}" height="{height_px:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{FONT_FAMILY}">'
        f'<rect x="0" y="0" width="{width_px:.0f}" height="{height_px:.0f}" fill="{BG_COLOR}"/>'
    )
    return header + "\n".join(body_parts) + "</svg>"


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    organ_name     = config["organ"]["name"]
    organ_sex      = config["organ"]["sex"]
    tool           = config["filters"]["tool"]

    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    organ_side   = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)
    stem = Path(glb_filename).stem

    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    distribution_path = base_folder / "json" / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(
            f"Distribution JSON not found: {distribution_path}. "
            "Run 20_fetch_cell_distribution.py first."
        )
    dist_data = json.loads(distribution_path.read_text(encoding="utf-8"))

    for as_label in AS_LABELS:
        if as_label not in dist_data["as_labels"]:
            raise ValueError(f"AS label {as_label!r} not found in {distribution_path.name}")
        if as_label not in AS_COLORS:
            raise ValueError(f"No AS_COLORS entry for {as_label!r} — add one before running.")

    categories = build_shared_category_list(dist_data, AS_LABELS, UNION_TOP_N_PER_AS)
    print(f"Shared category list ({len(categories)}): {categories}")

    groups = compute_group_data(dist_data, categories, AS_LABELS)
    for label in categories:
        print(f"\n{label}:")
        for as_label, pct, hexcolor in groups[label]:
            print(f"  {AS_SHORT_LABELS.get(as_label, as_label):5s} {pct:5.1f}%  {hexcolor}")

    title = f"{organ_name.title()} — {tool.title()} — {organ_sex.title()}: cell type composition by AS"
    out_dir = base_folder / "svg" / "faceted"
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_text = build_svg(groups, categories, AS_LABELS, title,
                          horizontal_labels=True, legend_mode="bottom_box",
                          category_label_font_size=12.0, category_label_line_h=14.0,
                          legend_single_line=False, legend_items_per_row=2,
                          legend_font_size=12.0, axis_title_font_size=14.0,
                          bar_value_font_size=9.0,
                          canvas_width=840.0, canvas_height=546.0)
    out_path = out_dir / f"{stem}-grouped-by-AS.svg"
    out_path.write_text(svg_text, encoding="utf-8")
    print(f"\nWrote: {out_path} (840x546px, {len(AS_LABELS)} AS, wrapped legend)")


if __name__ == "__main__":
    main()
