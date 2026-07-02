#!/usr/bin/env python3
"""
50_generate_pngs.py — Generate stacked horizontal bar chart SVGs showing
cell type distributions across all anatomical structures.

Reads:  config.yaml
        Outputs/annotated_organs/<organ>/json/<stem>_distribution.json
Writes: Outputs/annotated_organs/<organ>/outputs-organ-svg-withlegend/<output_name>-option-b-with-legend.svg
        Outputs/annotated_organs/<organ>/outputs-organ-svg-withoutlegend/<output_name>-option-b-without-legend.svg

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
    load_supertree,
    compact_ontology_id,
    PALETTE,
)

try:
    import plotly.graph_objects as go
except ImportError:
    raise ImportError("plotly is required: pip install plotly kaleido")


# =============================================================================
# EDITABLE VISUAL PARAMETERS
# =============================================================================

CHART_WIDTH         = 1400
BG_COLOR            = "#201E3D"
PAPER_BG_COLOR      = "#201E3D"
LABEL_WRAP_WIDTH    = 30
CHART_HEIGHT_PER_AS = 200
CHART_HEIGHT_MIN    = 600

FONT_FAMILY         = "Nunito, Arial, sans-serif"
TITLE_FONT_SIZE     = 28
SUBTITLE_FONT_SIZE  = 20
LABEL_FONT_SIZE     = 22
VALUE_FONT_SIZE     = 20
LEGEND_FONT_SIZE    = 18
TEXT_COLOR          = "#D6E8F8"
MUTED_TEXT_COLOR    = "#D6E8F8"

BAR_GAP             = 0.25
BAR_STROKE_COLOR    = "rgba(255,255,255,0.25)"
BAR_STROKE_WIDTH    = 0.5

MARGIN_LEFT         = 360
MARGIN_RIGHT        = 180
MARGIN_TOP          = 100
MARGIN_BOTTOM       = 180

LEGEND_X            = 0.0
LEGEND_Y            = -0.16
LEGEND_ORIENTATION  = "h"


# =============================================================================
# Helpers
# =============================================================================

def build_output_stem(stem: str, uberon_id: str, tool_slug: str, shape: str) -> str:
    parts = [stem]
    if uberon_id:
        parts.append(uberon_id)
    parts += ["all-as", tool_slug, shape, "hra-pop"]
    return "-".join(parts)


def wrap_label(text: str, max_width: int = LABEL_WRAP_WIDTH) -> str:
    words = text.split()
    lines, current = [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "<br>".join(lines)


def get_color_map(color_order: List[str]) -> Dict[str, str]:
    """Map label → hex color based on rank in color_order."""
    return {
        color: PALETTE[i] if i < len(PALETTE) else PALETTE[-1]
        for i, color in enumerate(color_order)
    }


# =============================================================================
# Data preparation
# =============================================================================

def prepare_chart_data(
    dist_data: dict,
    supertree: Dict[str, str],
    color_order: List[str],
) -> Tuple[List[str], Dict[str, List[float]], List[float], List[float]]:
    """
    Aggregate per-AS cell counts by cell type, grouped via supertree.
    Returns cell-type-keyed count lists aligned to as_labels.
    """
    as_labels:            List[str]                   = dist_data["as_labels"]
    as_total_counts:      Dict[str, float]            = dist_data["as_total_counts"]
    per_as_distributions: Dict[str, Dict[str, float]] = dist_data["per_as_distributions"]
    cell_id_map:          Dict[str, str]              = dist_data.get("cell_id_map", {})

    organ_total = sum(as_total_counts.values())

    cell_type_counts: Dict[str, List[float]] = {ct: [] for ct in color_order}

    for as_label in as_labels:
        as_total = as_total_counts.get(as_label, 0.0)
        dist     = per_as_distributions.get(as_label, {})

        per_cell_type: Dict[str, float] = {ct: 0.0 for ct in color_order}

        for cell_type, weight in dist.items():
            count   = weight * as_total if weight <= 1.0 else weight
            cl_id   = cell_id_map.get(normalize_cell_label_key(cell_type), "")
            ct_level = supertree.get(cl_id)
            if ct_level and ct_level in per_cell_type:
                per_cell_type[ct_level] += count

        for ct in color_order:
            cell_type_counts[ct].append(per_cell_type[ct])

    organ_pcts = [
        (as_total_counts.get(l, 0.0) / organ_total * 100) if organ_total > 0 else 0.0
        for l in as_labels
    ]
    as_totals = [as_total_counts.get(l, 0.0) for l in as_labels]

    return as_labels, cell_type_counts, as_totals, organ_pcts


# =============================================================================
# Chart generation
# =============================================================================

def make_figure(
    organ: str,
    sex: str,
    tool: str,
    as_labels: List[str],
    wrapped_labels: List[str],
    cell_type_counts: Dict[str, List[float]],
    as_totals: List[float],
    organ_pcts: List[float],
    color_order: List[str],
    show_legend: bool,
) -> go.Figure:
    fig = go.Figure()
    organ_total       = sum(as_totals)
    color_map  = get_color_map(color_order)

    for cell_type in color_order:
        raw_counts = cell_type_counts.get(cell_type, [0.0] * len(as_labels))

        # Convert to % of whole organ
        organ_pct_counts = [
            (count / organ_total * 100) if organ_total > 0 else 0.0
            for count in raw_counts
        ]

        fig.add_trace(go.Bar(
            name=cell_type,
            x=organ_pct_counts,
            y=wrapped_labels,
            orientation="h",
            marker=dict(
                color=color_map[cell_type],
                line=dict(color=BAR_STROKE_COLOR, width=BAR_STROKE_WIDTH),
            ),
            legendgroup=cell_type,
            showlegend=show_legend,
            hovertemplate=(
                f"<b>{cell_type}</b><br>"
                "%{y}<br>"
                "Organ %: %{x:.2f}%<extra></extra>"
            ),
        ))

    annotations = []
    for wrapped, as_label, total, pct in zip(
        wrapped_labels, as_labels, as_totals, organ_pcts
    ):
        annotations.append(dict(
            x=pct,
            y=wrapped,
            text=f"  {int(total):,} · {pct:.0f}%",
            xanchor="left",
            yanchor="middle",
            showarrow=False,
            font=dict(family=FONT_FAMILY, size=VALUE_FONT_SIZE, color=MUTED_TEXT_COLOR),
        ))
        annotations.append(dict(
            x=-0.01,
            y=wrapped,
            xref="paper",
            yref="y",
            text=wrap_label(as_label, max_width=30),
            xanchor="right",
            yanchor="middle",
            align="right",
            showarrow=False,
            font=dict(family=FONT_FAMILY, size=LABEL_FONT_SIZE, color=MUTED_TEXT_COLOR),
        ))

    title_text    = f"<b>{organ.title()} — {tool.title()} — {sex.title()}</b>"
    subtitle_text = (
        f"<span style='font-size:{SUBTITLE_FONT_SIZE}px;color:{MUTED_TEXT_COLOR}'>"
        f"Each bar shows an anatomical structure's share of total organ cells, colored by cell type cell_type"
        f"</span>"
    )

    fig.update_layout(
        barmode="stack",
        bargap=BAR_GAP,
        title=dict(
            text=f"{title_text}<br>{subtitle_text}",
            font=dict(family=FONT_FAMILY, size=TITLE_FONT_SIZE, color=TEXT_COLOR),
            x=0.0,
            xanchor="left",
            pad=dict(l=MARGIN_LEFT),
        ),
        xaxis=dict(
            visible=True,
            showgrid=True,
            gridcolor="rgba(214,232,248,0.06)",
            ticksuffix="%",
            tickvals=[0, 25, 50, 75, 100],
            tickfont=dict(family=FONT_FAMILY, size=10, color=MUTED_TEXT_COLOR),
            range=[0, 105],
            zeroline=False,
        ),
        yaxis=dict(
            showticklabels=False,
            autorange="reversed",
            showgrid=False,
            ticklen=0,
        ),
        legend=dict(
            orientation=LEGEND_ORIENTATION,
            x=LEGEND_X,
            y=LEGEND_Y,
            font=dict(family=FONT_FAMILY, size=LEGEND_FONT_SIZE, color=TEXT_COLOR),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            itemsizing="constant",
        ) if show_legend else dict(visible=False),
        annotations=annotations,
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=PAPER_BG_COLOR,
        width=CHART_WIDTH,
        height=max(CHART_HEIGHT_MIN, len(as_labels) * CHART_HEIGHT_PER_AS),
        margin=dict(
            l=MARGIN_LEFT,
            r=MARGIN_RIGHT,
            t=MARGIN_TOP,
            b=MARGIN_BOTTOM if show_legend else 60,
        ),
        font=dict(family=FONT_FAMILY, color=TEXT_COLOR),
    )

    return fig


# =============================================================================
# Save
# =============================================================================

def save_svg(fig: go.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(str(output_path), format="svg")
        print(f"Saved SVG: {output_path}")
    except Exception as e:
        print(f"Error saving SVG (is kaleido installed?): {e}")
        print("Install with: pip install kaleido")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    organ_name     = config["organ"]["name"]
    organ_sex      = config["organ"]["sex"]
    tool           = config["filters"]["tool"]
    shape          = config["markers"]["shape"]
    supertree_path = config["apis"]["cell_hierarchy"]

    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    organ_side   = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)

    stem      = Path(glb_filename).stem
    tool_slug = tool.lower()

    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    json_folder = base_folder / "json"
    svg_with    = base_folder / "outputs-organ-svg-withlegend"
    svg_without = base_folder / "outputs-organ-svg-withoutlegend"

    distribution_path = json_folder / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(
            f"Distribution JSON not found: {distribution_path}. "
            "Run 20_fetch_cell_distribution.py first."
        )

    dist_data          = json.loads(distribution_path.read_text(encoding="utf-8"))
    uberon_id          = dist_data.get("uberon_id", "")
    output_name        = build_output_stem(stem, uberon_id, tool_slug, shape)
    color_order = dist_data["color_order"]

    print(f"Loading supertree from: {supertree_path}")
    supertree = load_supertree(supertree_path)

    as_labels, cell_type_counts, as_totals, organ_pcts = prepare_chart_data(
        dist_data, supertree, color_order
    )
    wrapped_labels = [wrap_label(l) for l in as_labels]

    print(f"Generating Option B SVGs for: {output_name}")

    fig_with = make_figure(
        organ=organ_name, sex=organ_sex, tool=tool,
        as_labels=as_labels, wrapped_labels=wrapped_labels,
        cell_type_counts=cell_type_counts,
        as_totals=as_totals, organ_pcts=organ_pcts,
        color_order=color_order, show_legend=True,
    )
    save_svg(fig_with, svg_with / f"{output_name}-option-b-with-legend.svg")

    fig_without = make_figure(
        organ=organ_name, sex=organ_sex, tool=tool,
        as_labels=as_labels, wrapped_labels=wrapped_labels,
        cell_type_counts=cell_type_counts,
        as_totals=as_totals, organ_pcts=organ_pcts,
        color_order=color_order, show_legend=False,
    )
    save_svg(fig_without, svg_without / f"{output_name}-option-b-without-legend.svg")


if __name__ == "__main__":
    main()