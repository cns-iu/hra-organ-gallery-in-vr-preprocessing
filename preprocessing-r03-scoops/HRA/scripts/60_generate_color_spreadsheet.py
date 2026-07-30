#!/usr/bin/env python3
"""
60_generate_color_spreadsheet.py — Build/refresh the cumulative Supertree
color reference spreadsheet for every organ/sex/tool combination this
project's pipeline has processed so far.

Unlike scripts 10-50, this stage isn't scoped to the single organ named in
config.yaml — it rescans every distribution JSON already on disk under
outputs/annotated organs/*/json/*_distribution.json (one per organ/sex/tool
run through 20_fetch_cell_distribution.py) and recomputes each one's
top-9-granular + Other color scheme with THIS project's palette, so the
spreadsheet always reflects exactly what 30/40/50 actually rendered for
every organ processed to date. Running the pipeline for a new organ and
re-running this stage grows the spreadsheet by one more (Organ, Sex, Tool)
block — nothing needs to be re-entered by hand.

Reads:  outputs/annotated organs/<organ>/json/<stem>_distribution.json  (one per organ/sex/tool run through script 20)
Writes: outputs/Supertree_colors_all_organs_HRA.xlsx
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from shared import load_config, load_supertree, build_top9_granular_color_scheme
from palette import LEVEL2_TOP9_COLORS, OTHER_COLOR, BG_MODE

PROJECT_LABEL = "HRA"
BG_MODE_LABEL = "dark-background" if BG_MODE == "dark" else "light-background"


# =============================================================================
# Gather one row-group per (Organ, Sex, Tool) distribution JSON on disk
# =============================================================================

def find_distribution_files(amended_folder: Path) -> List[Path]:
    if not amended_folder.exists():
        return []
    return sorted(amended_folder.glob("*/json/*_distribution.json"))


def build_rows_for_distribution(
    dist_path: Path,
    supertree: Dict[str, str],
) -> List[Tuple]:
    dist_data = json.loads(dist_path.read_text(encoding="utf-8"))
    organ = dist_data.get("organ", "")
    sex   = dist_data.get("sex", "")
    tool  = dist_data.get("tool", "")
    organ_cell_counts = dist_data.get("organ_cell_counts", {})
    cell_id_map       = dist_data.get("cell_id_map", {})

    if not organ_cell_counts:
        print(f"  Skipping {dist_path.name} — no organ_cell_counts in file.")
        return []

    _color_map, legend_entries = build_top9_granular_color_scheme(
        organ_cell_counts=organ_cell_counts,
        cell_id_map=cell_id_map,
        supertree=supertree,
        palette=LEVEL2_TOP9_COLORS,
        other_color=OTHER_COLOR,
        bg_mode=BG_MODE,
    )

    # legend_entries is (label, hex, level2_label, count), count-descending
    # with "Other" (level2_label == "") pinned last. Reconstruct which base
    # hue (LEVEL2_TOP9_COLORS[i]) each level-2 parent got, in the same
    # first-appearance order build_top9_granular_color_scheme() itself used
    # internally — that order is preserved by the final count-descending
    # sort since the input was already count-ranked before grouping.
    ordered_lvl2: List[str] = []
    for _label, _hex, lvl2, _count in legend_entries:
        if lvl2 and lvl2 not in ordered_lvl2:
            ordered_lvl2.append(lvl2)
    lvl2_base = {
        lvl2: LEVEL2_TOP9_COLORS[i] if i < len(LEVEL2_TOP9_COLORS) else OTHER_COLOR
        for i, lvl2 in enumerate(ordered_lvl2)
    }

    rows = []
    for rank, (label, hex_color, lvl2, count) in enumerate(legend_entries, start=1):
        base_color = lvl2_base.get(lvl2, "") if lvl2 else ""
        rows.append((organ, sex, tool, rank, label, lvl2, base_color, hex_color, count))
    return rows


# =============================================================================
# xlsx output
# =============================================================================

def write_xlsx(blocks: List[List[Tuple]], out_path: Path) -> None:
    """blocks: one list of row-tuples per (Organ, Sex, Tool) distribution
    file, in the order they should appear. A blank row separates each
    block, and the Organ column is merged into one cell spanning every
    block that shares the same organ (including the blank separator rows
    between those same-organ blocks — the merge only breaks where the
    organ actually changes)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    thin   = Side(style="thin", color="FFB7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    TITLE_FONT     = Font(name="Arial", size=14, bold=True, color="FF000000")
    SUBTITLE_FONT  = Font(name="Arial", size=11, color="FF535353")
    HEADER_FONT    = Font(name="Arial", size=12, bold=True, color="FFFFFFFF")
    HEADER_FILL    = PatternFill("solid", fgColor="FF666666")
    BODY_FONT      = Font(name="Arial", size=11, color="FF000000")
    WHITE_FILL     = PatternFill("solid", fgColor="FFFFFFFF")
    CENTER         = Alignment(horizontal="center", vertical="center")
    ORGAN_ALIGN    = Alignment(horizontal="left", vertical="center")

    N_COLS = 9

    def _banner_row(row: int, text: str, font: Font) -> None:
        ws.cell(row=row, column=1, value=text).font = font
        for c in range(1, N_COLS + 1):
            ws.cell(row=row, column=c).fill = WHITE_FILL
            ws.cell(row=row, column=c).border = border

    _banner_row(3, (
        f"Top-9 granular cell types + Other, by organ / sex / tool "
        f"(organ-wide ranking, colored by supertree level-2 parent) — {PROJECT_LABEL} palette"
    ), TITLE_FONT)
    _banner_row(4, (
        'Rank 1-9 = top granular cell types by organ-wide cell count; rank 10 = "Other" '
        "(everything else, aggregate count)."
    ), SUBTITLE_FONT)
    _banner_row(5, (
        f"Auto-generated by 60_generate_color_spreadsheet.py against {PROJECT_LABEL}'s current "
        f"{BG_MODE_LABEL} palette/shading (shared.py's BASE_HUES + _shades_for_group, "
        f'bg_mode="{BG_MODE}"). "Base Color" = the unshaded supertree level-2 color; blank for '
        '"Other" rows, which aren\'t tied to a single level-2 parent. Regenerate this stage after '
        "processing a new organ to add its block below."
    ), SUBTITLE_FONT)
    for c in range(1, N_COLS + 1):
        ws.cell(row=6, column=c).fill = WHITE_FILL
        ws.cell(row=6, column=c).border = border

    headers = ["Organ", "Sex", "Tool", "Rank", "Supertree Label", "Base Color",
               "Cell Type", "Hex Color", "Cell Count"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=7, column=c, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = border
        cell.alignment = CENTER

    r = 8
    organ_merges: List[Tuple[str, int, int]] = []  # (organ, first_row, last_row)
    current_organ: Optional[str] = None
    current_organ_start = None
    prev_block_end = None

    for block_idx, block_rows in enumerate(blocks):
        if not block_rows:
            continue

        if block_idx > 0:
            r += 1  # blank separator row between every block, left unstyled

        organ = block_rows[0][0]
        if organ != current_organ:
            if current_organ is not None:
                organ_merges.append((current_organ, current_organ_start, prev_block_end))
            current_organ = organ
            current_organ_start = r

        for organ_v, sex, tool, rank, cell_type, lvl2, base_color, hex_color, count in block_rows:
            values = [None, sex, tool, rank, lvl2, base_color, cell_type, hex_color, count]
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row=r, column=c, value=v)
                cell.font = BODY_FONT
                cell.border = border
                cell.fill = WHITE_FILL

            ws.cell(row=r, column=4).alignment = CENTER  
            if base_color:
                ws.cell(row=r, column=6).fill = PatternFill("solid", fgColor="FF" + base_color.lstrip("#"))
            if hex_color:
                ws.cell(row=r, column=8).fill = PatternFill("solid", fgColor="FF" + hex_color.lstrip("#"))

            r += 1

        prev_block_end = r - 1

    if current_organ is not None:
        organ_merges.append((current_organ, current_organ_start, prev_block_end))

    for organ_name, start_row, end_row in organ_merges:
        if end_row > start_row:
            ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)
        top_cell = ws.cell(row=start_row, column=1, value=organ_name)
        top_cell.font = BODY_FONT
        top_cell.border = border
        top_cell.fill = WHITE_FILL
        top_cell.alignment = ORGAN_ALIGN

    widths = {"A": 19.25, "B": 10.63, "C": 19.5, "D": 9.25, "E": 19.75,
              "F": 13.5, "G": 57.75, "H": 14.75, "I": 13.5}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")
    supertree_path = config["apis"]["cell_hierarchy"]
    amended_folder = Path(config["output"]["amended_folder"])
    out_path = Path("outputs") / f"Supertree_colors_all_organs_{PROJECT_LABEL}.xlsx"

    dist_files = find_distribution_files(amended_folder)
    if not dist_files:
        print(f"No distribution JSONs found under {amended_folder}/*/json/. "
              f"Run 20_fetch_cell_distribution.py for at least one organ first — skipping.")
        return

    print(f"Loading supertree from: {supertree_path}")
    supertree, _ = load_supertree(supertree_path)

    blocks: List[List[Tuple]] = []
    for dist_path in dist_files:
        print(f"Processing: {dist_path}")
        rows = build_rows_for_distribution(dist_path, supertree)
        if rows:
            blocks.append(rows)

    if not blocks:
        print("No rows produced — nothing to write.")
        return

    # Group blocks by organ (each organ's blocks get merged into one Organ
    # cell), sub-sorted by sex/tool for a stable, readable layout.
    blocks.sort(key=lambda rows: (rows[0][0].lower(), rows[0][1].lower(), rows[0][2].lower()))

    write_xlsx(blocks, out_path)
    total_rows = sum(len(b) for b in blocks)
    print(f"\nWrote {total_rows} rows across {len(blocks)} organ/sex/tool combination(s) to: {out_path}")


if __name__ == "__main__":
    main()