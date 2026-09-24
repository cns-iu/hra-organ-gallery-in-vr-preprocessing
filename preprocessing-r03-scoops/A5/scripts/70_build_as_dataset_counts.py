#!/usr/bin/env python3
"""
70_build_as_dataset_counts.py — Per-organ/sex reference
table of distinct AS count, dataset count, and total cell count, built
from the raw HRApop data.

Like stage 60 and unlike 10-50, this isn't scoped to the single organ in
config.yaml — it rescans the full raw HRApop CSV (AS membership, cell
counts) plus atlas-as-cell-summaries.jsonld (dataset IDs) across every
organ. Gated by output.build_as_dataset_table in config.yaml (default
False) since it only needs recomputing on a new HRApop data release.

No tool (CTann) column. as_count and dataset_count are unioned across
every tool that reported the AS. total_cells is a single number when
every reporting tool agrees (after rounding, to absorb float summation
noise); when tools disagree, that cell instead holds a
"tool: n  /  tool: n  /  ..." breakdown (TOOL_ORDER) rather than picking
one. 

Reads:  data/hra_pop_raw.csv (cache from 20_fetch_cell_distribution.py
        with output.save_hra_pop_csv: true)
        data/atlas-as-cell-summaries.jsonld
Writes: outputs/AS_dataset_counts_A5.xlsx (columns: organ, sex, AS,
        as_count, dataset_count, total_cells — note banner in row 1,
        header in row 4, one AS row + trailing Total row per organ/sex
        group, blank row between organ blocks)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple, Union

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
from shared import load_config

PROJECT_LABEL = "A5"

TOTAL_ROW_LABEL = "Total (unique)"

TOOL_ORDER_LIST = ["azimuth", "celltypist", "pan-human-azimuth", "popv", "frmatch", "sc_proteomics"]
TOOL_ORDER = {tool: i for i, tool in enumerate(TOOL_ORDER_LIST)}

BREAKDOWN_SEPARATOR = "  /  "

TABLE_NOTE = (
    f"Note: dataset_count (per AS, and in the trailing \"{TOTAL_ROW_LABEL}\" "
    f"row) is the number of DISTINCT datasets (by dataset ID, from "
    f"atlas-as-cell-summaries.jsonld) across every CTann tool that "
    f"reported that structure. total_cells is that AS's cell count where "
    f"tools agree; where tools disagree, it instead lists each tool's own "
    f"total as \"tool: n{BREAKDOWN_SEPARATOR}tool: n{BREAKDOWN_SEPARATOR}...\" "
    f"rather than picking one. The Total (unique) row's total_cells is "
    f"deliberately left blank rather than summed — with some AS resolved "
    f"to a number and others left as a per-tool breakdown, a sum of just "
    f"the resolved ones would be inconsistent (sometimes near-zero, "
    f"sometimes coincidentally equal to a single AS), so no arithmetic "
    f"is attempted on this column's Total row."
)


def tool_sort_key(tool: str) -> Tuple[int, str]:
    return (TOOL_ORDER.get(tool, len(TOOL_ORDER)), tool)


class ASRow(NamedTuple):
    as_label: str
    dataset_count: Optional[int]
    total_cells: Union[int, str]  # int when resolved, str breakdown when tools disagree
    resolved: bool


class GroupRow(NamedTuple):
    organ: str
    sex: str
    num_as: int
    as_rows: List[ASRow]
    total_datasets: int


def load_dataset_ids_jsonld(jsonld_path: Path) -> Dict[Tuple[str, str, str], Set[str]]:
    """(as_label, sex, tool) -> set of dataset IDs, from
    atlas-as-cell-summaries.jsonld. Skips entries with no AS label."""
    with jsonld_path.open(encoding="utf-8") as f:
        data = json.load(f)

    lookup: Dict[Tuple[str, str, str], Set[str]] = {}
    skipped_blank = 0
    for entry in data.get("@graph", []):
        as_label = (entry.get("cell_source_label") or "").strip()
        sex = (entry.get("sex") or "").strip()
        tool = (entry.get("annotation_method") or "").strip()
        if not as_label or not sex or not tool:
            skipped_blank += 1
            continue
        dataset_ids = {
            s.get("aggregated_cell_source")
            for s in entry.get("aggregated_summaries", [])
            if s.get("aggregated_cell_source")
        }
        lookup[(as_label, sex, tool)] = dataset_ids

    if skipped_blank:
        print(f"  Note: skipped {skipped_blank} atlas-as-cell-summaries.jsonld "
              f"entr{'y' if skipped_blank == 1 else 'ies'} with no AS label "
              f"(not attributable to any organ) while building the dataset_count lookup.")

    return lookup


def resolve_total_cells(tool_totals: Dict[str, float]) -> Tuple[Union[int, str], bool]:
    """{tool: total_cell_count} -> (total_cells, resolved). Rounds to the
    nearest whole cell before comparing, to absorb float summation-order
    noise. Returns a single int if tools agree, else a breakdown string
    (TOOL_ORDER) and resolved=False."""
    if not tool_totals:
        return 0, True
    rounded = {tool: round(v) for tool, v in tool_totals.items()}
    if len(set(rounded.values())) == 1:
        return next(iter(rounded.values())), True
    parts = [f"{tool}: {v}"
             for tool, v in sorted(rounded.items(), key=lambda kv: tool_sort_key(kv[0]))]
    return BREAKDOWN_SEPARATOR.join(parts), False


def build_counts(
    raw_csv_path: Path,
    dataset_id_lookup: Dict[Tuple[str, str, str], Set[str]],
) -> List[GroupRow]:
    """One GroupRow per (organ, sex), sorted by organ then sex."""
    tools_by_as: Dict[Tuple[str, str], Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    cell_totals: Dict[Tuple[str, str, str], Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    with raw_csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            organ = (row.get("organ") or "").strip()
            sex = (row.get("sex") or "").strip()
            tool = (row.get("tool") or "").strip()
            as_label = (row.get("as_label") or "").strip()
            if not organ or not sex or not tool or not as_label:
                continue
            tools_by_as[(organ, sex)][as_label].add(tool)
            try:
                cell_count = float(row.get("cell_count") or "")
            except ValueError:
                cell_count = None
            if cell_count is not None:
                cell_totals[(organ, sex, as_label)][tool] += cell_count

    missing: List[Tuple[str, str, str]] = []
    results: List[GroupRow] = []
    for (organ, sex), as_map in tools_by_as.items():
        num_as = len(as_map)
        union_ids: Set[str] = set()
        as_rows: List[ASRow] = []
        for as_label in sorted(as_map.keys(), key=str.lower):
            tools_reporting = as_map[as_label]
            as_ids: Set[str] = set()
            found_any = False
            for tool in tools_reporting:
                ids = dataset_id_lookup.get((as_label, sex, tool))
                if ids is not None:
                    found_any = True
                    as_ids |= ids
            dataset_count: Optional[int]
            if not found_any:
                missing.append((organ, sex, as_label))
                dataset_count = None
            else:
                union_ids |= as_ids
                dataset_count = len(as_ids)

            tool_totals = cell_totals.get((organ, sex, as_label), {})
            total_cells, resolved = resolve_total_cells(tool_totals)

            as_rows.append(ASRow(as_label, dataset_count, total_cells, resolved))

        results.append(GroupRow(organ, sex, num_as, as_rows, len(union_ids)))

    if missing:
        print(f"\n  Note: {len(missing)} (organ, sex, AS) combo(s) from "
              f"hra_pop_raw.csv had no matching entry in "
              f"atlas-as-cell-summaries.jsonld for ANY tool — left blank "
              f"on their own row and excluded from that group's dataset "
              f"total rather than guessed at:")
        for organ, sex, as_label in missing[:20]:
            print(f"    {organ}/{sex}/{as_label}")
        if len(missing) > 20:
            print(f"    ... and {len(missing) - 20} more")

    results.sort(key=lambda r: (r.organ.lower(), r.sex.lower()))
    return results


def check_as_consistency_across_tools(raw_csv_path: Path) -> None:
    """Console-only diagnostic: AS is anatomical, not tool-dependent, so
    the set of AS reported should be identical across tools for the same
    organ+sex. The xlsx table itself unions across tools regardless."""
    as_by_tool: Dict[Tuple[str, str, str], Set[str]] = defaultdict(set)
    with raw_csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            organ = (row.get("organ") or "").strip()
            sex = (row.get("sex") or "").strip()
            tool = (row.get("tool") or "").strip()
            as_label = (row.get("as_label") or "").strip()
            if not organ or not sex or not tool or not as_label:
                continue
            as_by_tool[(organ, sex, tool)].add(as_label)

    by_organ_sex: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(dict)
    for (organ, sex, tool), as_labels in as_by_tool.items():
        by_organ_sex[(organ, sex)][tool] = len(as_labels)

    mismatches = {key: tool_counts for key, tool_counts in by_organ_sex.items()
                  if len(set(tool_counts.values())) > 1}

    if not mismatches:
        print("\nConsistency check: num_as matches across every tool for all organ/sex combos.")
        return

    print(f"\nConsistency check: num_as DIFFERS across tools for {len(mismatches)} organ/sex combo(s) "
          f"(the xlsx table below already unions across tools, so this is diagnostic only):")
    for (organ, sex), tool_counts in sorted(mismatches.items()):
        parts = ", ".join(f"{tool}={n}" for tool, n in sorted(tool_counts.items()))
        print(f"  {organ}/{sex}: {parts}")


def write_xlsx(rows: List[GroupRow], out_path: Path) -> None:
    """Note banner merged across A1:G2, blank row 3, bold header row 4
    (organ, sex, AS, as_count, dataset_count, total_cells). Each (organ,
    sex) group is one row per distinct AS plus a trailing Total row;
    organ merges down its whole block, sex/as_count merge down each
    group's rows. One blank separator row between organ blocks."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    LIGHT = Side(style="thin", color="FFD9D9D9")
    DARK = Side(style="thin", color="FF808080")
    light_border = Border(left=LIGHT, right=LIGHT, top=LIGHT, bottom=LIGHT)
    dark_border = Border(left=DARK, right=DARK, top=DARK, bottom=DARK)
    gap_border = Border(top=DARK, bottom=DARK)

    HEADER_FONT = Font(name="Arial", size=11, bold=True)
    BODY_FONT = Font(name="Arial", size=11)
    TOTAL_FONT = Font(name="Arial", size=11, bold=True)
    NOTE_FONT = Font(name="Arial", size=11)
    BREAKDOWN_FONT = Font(name="Arial", size=10)
    CENTER = Alignment(horizontal="center", vertical="center")
    CENTER_WRAP = Alignment(horizontal="center", vertical="center", wrap_text=True)
    HEADER_FILL = PatternFill("solid", fgColor="FFA4C2F4")
    TOTAL_FILL = PatternFill("solid", fgColor="FFF3F3F3")

    n_cols = 6  # organ, sex, AS, as_count, dataset_count, total_cells

    note_cell = ws.cell(row=1, column=1, value=TABLE_NOTE)
    note_cell.font = NOTE_FONT
    note_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=7)

    headers = ["organ", "sex", "AS", "as_count", "dataset_count", "total_cells"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.fill = HEADER_FILL
        cell.border = dark_border

    def close_organ_block(start_row: int, end_row: int, organ_name: str) -> None:
        cell = ws.cell(row=start_row, column=1, value=organ_name)
        cell.font = BODY_FONT
        cell.alignment = CENTER
        cell.border = light_border
        if end_row > start_row:
            ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)

    r = 5
    prev_organ = None
    last_row = 4
    organ_block_start = r
    for group in rows:
        if prev_organ is not None and group.organ != prev_organ:
            close_organ_block(organ_block_start, r - 1, prev_organ)
            for c in range(1, n_cols + 1):
                ws.cell(row=r, column=c).border = gap_border
            r += 1
            organ_block_start = r
        prev_organ = group.organ

        group_start = r

        for as_row in group.as_rows:
            as_cell = ws.cell(row=r, column=3, value=as_row.as_label)
            as_cell.font = BODY_FONT
            as_cell.border = light_border
            dc_cell = ws.cell(row=r, column=5, value=as_row.dataset_count)
            dc_cell.font = BODY_FONT
            dc_cell.border = light_border
            dc_cell.alignment = CENTER
            tc_cell = ws.cell(row=r, column=6, value=as_row.total_cells)
            tc_cell.border = light_border
            if as_row.resolved:
                tc_cell.font = BODY_FONT
                tc_cell.alignment = CENTER
            else:
                tc_cell.font = BREAKDOWN_FONT
                tc_cell.alignment = CENTER_WRAP
            for c in (1, 2, 4):
                ws.cell(row=r, column=c).border = light_border
            r += 1

        as_cell = ws.cell(row=r, column=3, value=TOTAL_ROW_LABEL)
        as_cell.font = TOTAL_FONT
        as_cell.border = light_border
        as_cell.fill = TOTAL_FILL
        dc_cell = ws.cell(row=r, column=5, value=group.total_datasets)
        dc_cell.font = TOTAL_FONT
        dc_cell.border = light_border
        dc_cell.alignment = CENTER
        dc_cell.fill = TOTAL_FILL
        tc_cell = ws.cell(row=r, column=6, value=None)
        tc_cell.font = TOTAL_FONT
        tc_cell.border = light_border
        tc_cell.alignment = CENTER
        tc_cell.fill = TOTAL_FILL
        for c in (1, 2, 4):
            cell = ws.cell(row=r, column=c)
            cell.border = light_border
            cell.fill = TOTAL_FILL
        r += 1

        group_end = r - 1
        sex_cell = ws.cell(row=group_start, column=2, value=group.sex)
        as_count_cell = ws.cell(row=group_start, column=4, value=group.num_as)
        for cell in (sex_cell, as_count_cell):
            cell.font = BODY_FONT
            cell.alignment = CENTER
        if group_end > group_start:
            ws.merge_cells(start_row=group_start, start_column=2, end_row=group_end, end_column=2)
            ws.merge_cells(start_row=group_start, start_column=4, end_row=group_end, end_column=4)

        last_row = group_end

    close_organ_block(organ_block_start, last_row, prev_organ)

    for row in range(4, last_row + 1):
        left_cell = ws.cell(row=row, column=1)
        right_cell = ws.cell(row=row, column=n_cols)
        left_cell.border = Border(left=DARK, right=left_cell.border.right,
                                   top=left_cell.border.top, bottom=left_cell.border.bottom)
        right_cell.border = Border(right=DARK, left=right_cell.border.left,
                                    top=right_cell.border.top, bottom=right_cell.border.bottom)
    for c in range(1, n_cols + 1):
        bottom_cell = ws.cell(row=last_row, column=c)
        bottom_cell.border = Border(bottom=DARK, top=bottom_cell.border.top,
                                     left=bottom_cell.border.left, right=bottom_cell.border.right)

    widths = {"A": 24.63, "B": 13.88, "C": 45.0, "D": 10.0, "E": 14.0, "F": 34.0}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    if not config.get("output", {}).get("build_as_dataset_table", False):
        print("output.build_as_dataset_table is False in config.yaml — skipping "
              "(this table only needs refreshing on a new HRApop data release).")
        return

    data_dir = Path(__file__).parent.parent.parent / "data"
    raw_csv_path = data_dir / "hra_pop_raw.csv"
    if not raw_csv_path.exists():
        raise FileNotFoundError(
            f"{raw_csv_path} not found. Run 20_fetch_cell_distribution.py with "
            "output.save_hra_pop_csv: true first to cache the raw HRApop data."
        )

    jsonld_path = data_dir / "atlas-as-cell-summaries.jsonld"
    if not jsonld_path.exists():
        raise FileNotFoundError(
            f"{jsonld_path} not found. This is the source for dataset_count "
            "(per-AS dataset IDs) — place the latest export there first."
        )

    print(f"Reading: {raw_csv_path}")
    print(f"Reading: {jsonld_path}")
    dataset_id_lookup = load_dataset_ids_jsonld(jsonld_path)
    rows = build_counts(raw_csv_path, dataset_id_lookup)

    check_as_consistency_across_tools(raw_csv_path)

    print(f"\n{TABLE_NOTE}")
    out_path = Path("outputs") / f"AS_dataset_counts_{PROJECT_LABEL}.xlsx"
    write_xlsx(rows, out_path)
    total_as_rows = sum(len(g.as_rows) for g in rows)
    print(f"Wrote {len(rows)} organ/sex groups ({total_as_rows} AS rows "
          f"+ {len(rows)} total rows) to: {out_path}")


if __name__ == "__main__":
    main()
