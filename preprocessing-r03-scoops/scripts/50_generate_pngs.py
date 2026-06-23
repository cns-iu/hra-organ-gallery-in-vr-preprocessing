#!/usr/bin/env python3
"""
50_generate_pngs.py — Generate stacked bar chart PNGs showing cell type
distributions across all anatomical structures for the configured organ.

Produces two versions:
  - with-legend:    chart includes color key legend overlay
  - without-legend: clean chart, no legend

Reads:  config.yaml
        Outputs/annotated_organs/<organ>/json/<stem>_distribution.json
Writes: Outputs/annotated_organs/<organ>/png/with-legend/<output_name>-with-legend.png
        Outputs/annotated_organs/<organ>/png/without-legend/<output_name>-without-legend.png

Requires: plotly, kaleido
    pip install plotly kaleido
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config,
    resolve_glb_filename,
    normalize_cell_label_key,
    PALETTE,
    OTHERS,
)

try:
    import plotly.graph_objects as go
except ImportError:
    raise ImportError("plotly is required: pip install plotly kaleido")


# =============================================================================
# Chart constants
# =============================================================================

CHART_WIDTH       = 1240
CHART_HEIGHT      = 800
CHART_BG_COLOR    = "#263139"
PAPER_BG_COLOR    = "#263139"
TEXT_COLOR        = "#fcfcfc"
GRIDLINE_COLOR    = "#3a4a55"
BAR_STROKE_COLOR  = "#BDC6D7"
BAR_STROKE_WIDTH  = 0.5
X_AXIS_ANGLE      = -21.4
FONT_FAMILY       = "Arial, sans-serif"


# =============================================================================
# Helpers
# =============================================================================

def build_output_stem(stem: str, uberon_id: str, tool_slug: str, shape: str) -> str:
    parts = [stem]
    if uberon_id:
        parts.append(uberon_id)
    parts += ["all-as", tool_slug, shape, "hra-pop"]
    return "-".join(parts)


def get_color_for_label(label: str, global_top_labels: List[str]) -> str:
    key = normalize_cell_label_key(label)
    for i, top_label in enumerate(global_top_labels):
        if normalize_cell_label_key(top_label) == key:
            return PALETTE[i] if i < len(PALETTE) else OTHERS
    return OTHERS


# =============================================================================
# Chart data preparation
# =============================================================================

def prepare_chart_data(
    dist_data: dict,
) -> Tuple[List[str], Dict[str, Dict[str, float]]]:
    """
    Returns:
        as_labels: list of AS labels (x-axis categories)
        cell_type_data: dict of cell_type -> {as_label -> cell_count}
    """
    as_labels: List[str] = dist_data["as_labels"]
    as_total_counts: Dict[str, float] = dist_data["as_total_counts"]
    per_as_distributions: Dict[str, Dict[str, float]] = dist_data["per_as_distributions"]
    global_top_labels: List[str] = dist_data["global_top_labels"]

    # Collect all cell types across all AS
    all_cell_types: set = set()
    for dist in per_as_distributions.values():
        all_cell_types.update(dist.keys())

    # Group non-top cell types into "Other"
    top_set = {normalize_cell_label_key(l) for l in global_top_labels}

    cell_type_data: Dict[str, Dict[str, float]] = {}

    for cell_type in all_cell_types:
        key = normalize_cell_label_key(cell_type)
        display_label = cell_type if key in top_set else "Other"
        if display_label not in cell_type_data:
            cell_type_data[display_label] = {as_label: 0.0 for as_label in as_labels}
        for as_label in as_labels:
            raw_count = per_as_distributions.get(as_label, {}).get(cell_type, 0.0)
            # Convert from percentage weight back to approximate count
            total = as_total_counts.get(as_label, 1.0)
            count = raw_count * total if raw_count <= 1.0 else raw_count
            cell_type_data[display_label][as_label] = (
                cell_type_data[display_label].get(as_label, 0.0) + count
            )

    return as_labels, cell_type_data


# =============================================================================
# Chart generation
# =============================================================================

def make_figure(
    organ: str,
    sex: str,
    tool: str,
    as_labels: List[str],
    cell_type_data: Dict[str, Dict[str, float]],
    global_top_labels: List[str],
    show_legend: bool,
) -> go.Figure:
    fig = go.Figure()

    # Order: top cell types first (in rank order), then Other
    ordered_labels = list(global_top_labels) + (["Other"] if "Other" in cell_type_data else [])

    for cell_type in ordered_labels:
        if cell_type not in cell_type_data:
            continue
        counts = [cell_type_data[cell_type].get(as_label, 0.0) for as_label in as_labels]
        color = get_color_for_label(cell_type, global_top_labels) if cell_type != "Other" else OTHERS

        fig.add_trace(go.Bar(
            name=cell_type,
            x=as_labels,
            y=counts,
            marker=dict(
                color=color,
                line=dict(color=BAR_STROKE_COLOR, width=BAR_STROKE_WIDTH),
            ),
            showlegend=show_legend,
        ))

    title_text = f"Anatomical Structures — {tool.title()} — {sex.title()}"

    fig.update_layout(
        barmode="stack",
        title=dict(
            text=title_text,
            font=dict(family=FONT_FAMILY, size=20, color=TEXT_COLOR),
            x=0.05,
        ),
        xaxis=dict(
            title=dict(text="Anatomical Structure", font=dict(family=FONT_FAMILY, size=14, color=TEXT_COLOR)),
            tickfont=dict(family=FONT_FAMILY, size=11, color=TEXT_COLOR),
            tickangle=X_AXIS_ANGLE,
            showgrid=False,
            linecolor=GRIDLINE_COLOR,
        ),
        yaxis=dict(
            title=dict(text="Cell Count", font=dict(family=FONT_FAMILY, size=14, color=TEXT_COLOR)),
            tickfont=dict(family=FONT_FAMILY, size=11, color=TEXT_COLOR),
            gridcolor=GRIDLINE_COLOR,
            showgrid=True,
            linecolor=GRIDLINE_COLOR,
        ),
        legend=dict(
            title=dict(text="Cell Type", font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR)),
            font=dict(family=FONT_FAMILY, size=11, color=TEXT_COLOR),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
        ) if show_legend else dict(visible=False),
        plot_bgcolor=CHART_BG_COLOR,
        paper_bgcolor=PAPER_BG_COLOR,
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=80, r=200 if show_legend else 40, t=80, b=160),
    )

    return fig


def save_png(fig: go.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(str(output_path), format="png", scale=2)
        print(f"Saved PNG: {output_path}")
    except Exception as e:
        print(f"Error saving PNG (is kaleido installed?): {e}")
        print("Install with: pip install kaleido")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    organ_name = config["organ"]["name"]
    organ_sex  = config["organ"]["sex"]
    tool       = config["filters"]["tool"]
    shape      = config["markers"]["shape"]

    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    organ_side   = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)

    stem      = Path(glb_filename).stem
    tool_slug = tool.lower()

    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    json_folder = base_folder / "json"
    png_with    = base_folder / "png" / "with-legend"
    png_without = base_folder / "png" / "without-legend"
    png_with.mkdir(parents=True, exist_ok=True)
    png_without.mkdir(parents=True, exist_ok=True)

    distribution_path = json_folder / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(
            f"Distribution JSON not found: {distribution_path}. "
            "Run 20_fetch_cell_distribution.py first."
        )

    dist_data  = json.loads(distribution_path.read_text(encoding="utf-8"))
    uberon_id  = dist_data.get("uberon_id", "")
    output_name = build_output_stem(stem, uberon_id, tool_slug, shape)

    global_top_labels: List[str] = dist_data["global_top_labels"]
    as_labels, cell_type_data = prepare_chart_data(dist_data)

    # With legend
    fig_with = make_figure(
        organ=organ_name,
        sex=organ_sex,
        tool=tool,
        as_labels=as_labels,
        cell_type_data=cell_type_data,
        global_top_labels=global_top_labels,
        show_legend=True,
    )
    save_png(fig_with, png_with / f"{output_name}-with-legend.png")

    # Without legend
    fig_without = make_figure(
        organ=organ_name,
        sex=organ_sex,
        tool=tool,
        as_labels=as_labels,
        cell_type_data=cell_type_data,
        global_top_labels=global_top_labels,
        show_legend=False,
    )
    save_png(fig_without, png_without / f"{output_name}-without-legend.png")


if __name__ == "__main__":
    main()