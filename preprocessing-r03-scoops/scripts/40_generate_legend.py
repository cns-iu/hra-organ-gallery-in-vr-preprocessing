#!/usr/bin/env python3
"""
40_generate_legend.py — Generate a companion HTML legend file for the GLB output.

Reads:  config.yaml
        Outputs/annotated_organs/<organ>/json/<stem>_distribution.json
        Outputs/annotated_organs/<organ>/csv/<stem>-<uberon>-all-as-<tool>-<shape>-hra-pop.csv
Writes: Outputs/annotated_organs/<organ>/html/<stem>-<uberon>-all-as-<tool>-<shape>-hra-pop_legend.html
        Outputs/annotated_organs/<organ>/json/<stem>-<uberon>-all-as-<tool>-<shape>-hra-pop_legend.json
"""

from __future__ import annotations

import csv
import datetime
import json
import math
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config,
    PALETTE,
    ORGAN_CELL_COUNTS,
    resolve_glb_filename,
)

REAL_CELL_SIZE_UM = 10.0

def build_output_stem(stem: str, uberon_id: str, tool_slug: str, shape: str) -> str:
    parts = [stem]
    if uberon_id:
        parts.append(uberon_id)
    parts += ["all-as", tool_slug, shape, "hra-pop"]
    return "-".join(parts)


def load_distribution(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_nodes_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def get_plotted_counts_by_as(rows: List[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        as_label = row.get("as_label", "").strip()
        counts[as_label] = counts.get(as_label, 0) + 1
    return counts


def generate_html(
    organ: str,
    sex: str,
    tool: str,
    glb_filename: str,
    cell_type_color_order: List[str],
    as_labels: List[str],
    as_total_counts: Dict[str, float],
    node_allocation: Dict[str, int],
    plotted_by_as: Dict[str, int],
    total_nodes_requested: int,
    organ_total_cells: int,
    sphere_radius: float,
) -> str:
    total_plotted = sum(plotted_by_as.values())

    cell_size_m = REAL_CELL_SIZE_UM * 1e-6
    log_min, log_max = -9, -3
    log_cell = math.log10(cell_size_m)
    marker_pct = (log_cell - log_min) / (log_max - log_min) * 100

    color_key_rows = ""
    for i, cell in enumerate(cell_type_color_order):
        hex_color = PALETTE[i] if i < len(PALETTE) else PALETTE[-1]
        color_key_rows += f"""
        <tr>
            <td><span class="swatch" style="background:{hex_color}"></span></td>
            <td class="label">{cell}</td>
            <td class="mono">{hex_color}</td>
        </tr>"""

    as_rows_html = ""
    for as_label in as_labels:
        hra_count = int(as_total_counts.get(as_label, 0))
        allocated = node_allocation.get(as_label, 0)
        plotted   = plotted_by_as.get(as_label, 0)
        as_rows_html += f"""
        <tr>
            <td class="label">{as_label}</td>
            <td class="num">{hra_count:,}</td>
            <td class="num">{allocated:,}</td>
            <td class="num">{plotted:,}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legend — {organ.title()} ({sex.title()})</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0f1117; color: #e8eaf0;
            padding: 2rem; line-height: 1.5;
        }}
        h1 {{ font-size: 1.4rem; font-weight: 600; margin-bottom: 0.25rem; color: #ffffff; }}
        .subtitle {{ font-size: 0.85rem; color: #888; margin-bottom: 2rem; }}
        .section {{
            background: #1a1d27; border: 1px solid #2a2d3a;
            border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
        }}
        .section h2 {{
            font-size: 0.75rem; text-transform: uppercase;
            letter-spacing: 0.08em; color: #6c7aff; margin-bottom: 1rem;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
        thead th {{
            text-align: left; font-size: 0.7rem; text-transform: uppercase;
            letter-spacing: 0.06em; color: #666;
            padding: 0 0.75rem 0.5rem 0; border-bottom: 1px solid #2a2d3a;
        }}
        tbody tr:hover {{ background: #20232f; }}
        td {{
            padding: 0.5rem 0.75rem 0.5rem 0;
            border-bottom: 1px solid #1f2230; vertical-align: middle;
        }}
        td.num {{ text-align: right; font-variant-numeric: tabular-nums; color: #ccc; }}
        td.mono {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 0.8rem; color: #aaa; }}
        td.label {{ font-weight: 500; }}
        .swatch {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: middle; }}
        .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; }}
        .meta-item {{ background: #12141e; border-radius: 8px; padding: 0.75rem 1rem; }}
        .meta-item .key {{
            font-size: 0.7rem; text-transform: uppercase;
            letter-spacing: 0.06em; color: #666; margin-bottom: 0.25rem;
        }}
        .meta-item .value {{ font-size: 0.95rem; font-weight: 600; color: #e8eaf0; }}
        .size-note {{
            font-size: 0.8rem; color: #888; margin-top: 0.75rem;
            padding: 0.6rem 0.75rem; background: #12141e;
            border-radius: 6px; border-left: 3px solid #6c7aff;
        }}
        .footer {{ font-size: 0.75rem; color: #444; margin-top: 2rem; text-align: center; }}
    </style>
</head>
<body>
    <h1>{organ.title()} </h1>
    <p class="subtitle">{sex.title()} &nbsp;·&nbsp; {tool} &nbsp;·&nbsp; Source: {glb_filename}</p>

    <div class="section">
        <h2>Cell Type Colour Key</h2>
        <table>
            <thead><tr><th style="width:28px"></th><th>Cell type ({len(cell_type_color_order)} total)</th><th>Hex Color</th></tr></thead>
            <tbody>{color_key_rows}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Anatomical Structures</h2>
        <table>
            <thead>
                <tr>
                    <th>Anatomical Structure</th>
                    <th style="text-align:right">HRApop Cell Count</th>
                    <th style="text-align:right">Allocated Markers</th>
                    <th style="text-align:right">Plotted</th>
                </tr>
            </thead>
            <tbody>{as_rows_html}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Cell Count Comparison</h2>
        <div class="meta-grid">
            <div class="meta-item"><div class="key">Total Plotted</div><div class="value">{total_plotted:,}</div></div>
            <div class="meta-item"><div class="key">Total Requested</div><div class="value">{total_nodes_requested:,}</div></div>
            <div class="meta-item"><div class="key">Real Cells per Marker</div><div class="value">~{organ_total_cells // max(total_plotted, 1):,}</div></div>
        </div>
        <p class="size-note">Markers are a representative sample. Each marker represents roughly {organ_total_cells // max(total_plotted, 1):,} real cells.</p>
    </div>

    <div class="section">
        <h2>Size Reference</h2>
        <p style="font-size:0.8rem;color:#888;margin-bottom:1.5rem;">
            Biological scale from 1 nm to 1 mm. Cell markers represent
            <strong style="color:#e8eaf0">{REAL_CELL_SIZE_UM:.0f} µm</strong> in diameter.
        </p>
        <div style="position:relative;margin:2.5rem 0 1rem 0;">
            <div style="position:relative;height:8px;background:linear-gradient(to right,#1a1d27,#3a3d8a,#6c7aff,#a0aaff,#e8eaf0);border-radius:4px;"></div>
            <div style="position:absolute;left:{marker_pct:.2f}%;top:-28px;transform:translateX(-50%);">
                <div style="text-align:center;font-size:0.75rem;font-weight:600;color:#ffd700;white-space:nowrap;margin-bottom:2px;">{REAL_CELL_SIZE_UM:.0f} µm</div>
                <div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:8px solid #ffd700;margin:0 auto;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.65rem;color:#555;">
                <span>1 nm</span><span>10 nm</span><span>100 nm</span><span>1 µm</span><span>10 µm</span><span>100 µm</span><span>1 mm</span>
            </div>
        </div>
    </div>

    <p class="footer">Generated by HRA 3D Cell Population Pipeline &nbsp;·&nbsp; Human Reference Atlas &nbsp;·&nbsp; humanatlas.io</p>
</body>
</html>"""


def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    organ_name  = config["organ"]["name"]
    organ_sex   = config["organ"]["sex"]
    tool        = config["filters"]["tool"]
    total_nodes_requested = config["markers"]["num_nodes"]
    sphere_radius = config["markers"]["sphere_radius"]
    shape         = config["markers"]["shape"]

    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    organ_side   = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)

    stem      = Path(glb_filename).stem
    tool_slug = tool.lower()

    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    json_folder = base_folder / "json"
    html_folder = base_folder / "html"
    csv_folder  = base_folder / "csv"
    html_folder.mkdir(parents=True, exist_ok=True)
    json_folder.mkdir(parents=True, exist_ok=True)

    distribution_path = json_folder / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(f"Distribution JSON not found: {distribution_path}.")

    dist_data  = load_distribution(distribution_path)
    uberon_id  = dist_data.get("uberon_id", "")
    output_name = build_output_stem(stem, uberon_id, tool_slug, shape)

    nodes_csv_path = csv_folder  / f"{output_name}.csv"
    output_html    = html_folder / f"{output_name}_legend.html"
    output_json    = json_folder / f"{output_name}_legend.json"

    if not nodes_csv_path.exists():
        raise FileNotFoundError(f"Nodes CSV not found: {nodes_csv_path}.")

    nodes_rows     = load_nodes_csv(nodes_csv_path)
    plotted_by_as  = get_plotted_counts_by_as(nodes_rows)
    cell_type_color_order: List[str] = dist_data["cell_type_color_order"]
    organ_info = ORGAN_CELL_COUNTS.get(organ_name.lower(), {})
    organ_total_cells = organ_info.get("total_cells", 1)

    html = generate_html(
        organ=organ_name,
        sex=organ_sex,
        tool=tool,
        glb_filename=glb_filename,
        cell_type_color_order=cell_type_color_order,
        as_labels=dist_data["as_labels"],
        as_total_counts=dist_data["as_total_counts"],
        node_allocation=dist_data["node_allocation"],
        plotted_by_as=plotted_by_as,
        total_nodes_requested=total_nodes_requested,
        sphere_radius=sphere_radius,
        organ_total_cells = organ_total_cells,
    )

    output_html.write_text(html, encoding="utf-8")
    print(f"Legend HTML saved to: {output_html}")

    total_plotted = sum(plotted_by_as.values())

    legend_json = {
        "metadata": {
            "organ": organ_name, "sex": organ_sex, "tool": tool,
            "uberon_id": uberon_id, "glb_filename": glb_filename,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "organ_total_cell_count": {
            "organ":       organ_name,
            "total_cells": organ_info.get("total_cells", "unknown"),
            "notes":       organ_info.get("notes", ""),
            "source":      organ_info.get("source", ""),
            "doi":         organ_info.get("doi", ""),
        },
        "cell_type_color_key": {
            "cell type": cell_type_color_order,
            "colors": {
                cell: PALETTE[i] if i < len(PALETTE) else PALETTE[-1]
                for i, cell in enumerate(cell_type_color_order)
            },
        },
        "anatomical_structures": [
            {
                "name":              as_label,
                "glb_node":          dist_data["as_to_glb_node"].get(as_label, ""),
                "hra_pop_cell_count": int(dist_data["as_total_counts"].get(as_label, 0)),
                "allocated_markers": dist_data["node_allocation"].get(as_label, 0),
                "plotted":           plotted_by_as.get(as_label, 0),
            }
            for as_label in dist_data["as_labels"]
        ],
        "cell_count_comparison": {
            "total_plotted":       total_plotted,
            "total_requested":     total_nodes_requested,
            "real_cells_per_marker": organ_total_cells // max(total_plotted, 1),
        },
        "size_reference": {
            "assumed_cell_size_um": REAL_CELL_SIZE_UM,
            "note": "All cell types assumed to be 10 µm in diameter.",
        },
    }

    output_json.write_text(
        json.dumps(legend_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Legend JSON saved to: {output_json}")


if __name__ == "__main__":
    main()