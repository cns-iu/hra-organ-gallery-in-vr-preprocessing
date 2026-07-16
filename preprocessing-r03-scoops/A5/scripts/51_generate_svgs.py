#!/usr/bin/env python3
"""
51_generate_svgs.py — Generate grouped horizontal bar chart SVGs showing
cell type distributions across all anatomical structures.

Forked from 50_generate_pngs.py so PNG and SVG output can evolve
separately. This file keeps the SVG-specific piece: embedding Benton Sans
as base64 @font-face rules, which doesn't apply to a rasterized PNG.

Color scheme: top-9-granular + Other, from
shared.build_top9_granular_color_scheme() — level-2 parent categories
each get one palette color, granular (level-3) types under a parent get
HSL-lightness shades of it, and the legend shows the top 9 granular types
plus one aggregate "Other".

Note: Adobe Illustrator's SVG importer doesn't support @font-face /
data-URI embedded fonts — it substitutes a system font on import. Renders
correctly in browser (which does support them).

Reads:  config.yaml
        outputs/annotated organs/<organ>/json/<stem>_distribution.json
        fonts/BentonSans-Book_T.ttf, fonts/BentonSans-Bold_T.ttf
Writes: outputs/annotated organs/<organ>/svg/with-legend/<output_name>-with-legend.svg
        outputs/annotated organs/<organ>/svg/without-legend/<output_name>-without-legend.svg

Requires: plotly, kaleido
    pip install plotly kaleido
"""

from __future__ import annotations

import base64
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# shared.py is in the repo-root "shared scripts/" folder; palette.py is
# right next to this file.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config,
    resolve_glb_filename,
    load_supertree,
    build_top9_granular_color_scheme,
    canonicalize_cell_label,
)
from palette import LEVEL2_TOP9_COLORS, OTHER_COLOR

try:
    import plotly.graph_objects as go
except ImportError:
    raise ImportError("plotly is required: pip install plotly kaleido")


# =============================================================================
# EDITABLE VISUAL PARAMETERS
# =============================================================================

CHART_WIDTH         = 1400
BG_COLOR            = "#FAF8F5"
PAPER_BG_COLOR      = "#FAF8F5"
GRID_COLOR          = "rgba(0,0,0,0.10)"
CHART_HEIGHT_MIN    = 600

ROW_LINE_HEIGHT     = 30    # px, vertical space per wrapped label line
ROW_PADDING         = 14    # px, extra breathing room added around each AS block

# One thin bar per cell-type bucket per AS — no per-bar value label, so
# rows can pack tightly.
CT_BAR_THICKNESS    = 14    # px
CT_BAR_GAP          = 4     # px
AS_BLOCK_GAP        = 18    # px, vertical gap between one AS's bars and the next

# "BentonSansBook" is a custom family alias — normal weight maps to the
# Book file, bold (e.g. <b> in the title) maps to the true Bold file.
FONT_FAMILY         = "BentonSansBook, Arial, sans-serif"
FONT_BOOK_PATH      = Path(__file__).parent.parent / "fonts" / "BentonSans-Book_T.ttf"
FONT_BOLD_PATH      = Path(__file__).parent.parent / "fonts" / "BentonSans-Bold_T.ttf"

TITLE_FONT_SIZE     = 34
SUBTITLE_FONT_SIZE  = 24
LABEL_FONT_SIZE     = 22
LEGEND_FONT_SIZE    = 22
TEXT_COLOR          = "#3D3D3D"
MUTED_TEXT_COLOR    = "#494747"

BAR_STROKE_COLOR    = "rgba(0,0,0,0.15)"
BAR_STROKE_WIDTH    = 0.5

# MARGIN_LEFT + MARGIN_RIGHT is fixed (PLOT_WIDTH unchanged); the split
# between them controls how much room AS labels vs. value labels get.
MARGIN_LEFT         = 360
MARGIN_RIGHT        = 60
MARGIN_TOP          = 100
MARGIN_BOTTOM_NO_LEGEND = 90  # with-legend margin is computed in make_figure()

# Custom legend grid, built from annotations — Plotly's native legend
# didn't reliably wrap into multiple columns in kaleido's static export.
LEGEND_NUM_COLUMNS   = 3
LEGEND_ROW_HEIGHT    = 38
LEGEND_COL_START_PX  = 40
LEGEND_COL_WIDTH_PX  = (CHART_WIDTH - 2 * LEGEND_COL_START_PX) / LEGEND_NUM_COLUMNS
LEGEND_BOTTOM_PAD    = 30
# Note: xref/yref="paper" for annotations is scoped to the axis/plot
# domain, not the full canvas — paper (0,0) is the axis's bottom-left
# corner, (1,1) its top-right. PLOT_WIDTH converts an absolute canvas px
# into that paper-fraction.
PLOT_WIDTH           = CHART_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
AXIS_TITLE_BAND      = 60

AXIS_TITLE_TEXT      = "Cell count"
AXIS_TITLE_FONT_SIZE = 20
AXIS_HEADROOM_RATIO  = 0.04  # small breathing room past the longest bar

LABEL_LEFT_SAFETY_PX = 10
AVG_CHAR_WIDTH_RATIO = 0.52  # fallback only, see _text_width_px() below
LABEL_AVAILABLE_PX   = MARGIN_LEFT - LEGEND_COL_START_PX - LABEL_LEFT_SAFETY_PX


# =============================================================================
# Helpers
# =============================================================================

def build_output_stem(stem: str, uberon_id: str, tool_slug: str, shape: str) -> str:
    parts = [stem]
    if uberon_id:
        parts.append(uberon_id)
    parts += ["all-as", tool_slug, shape, "hra-pop"]
    return "-".join(parts)


# Pixel-measured word-wrap instead of a char-count heuristic (greedy wrap
# is a step function of word width, so an average-char-width guess can
# land on the wrong side of that step). Tries the real Benton Sans file
# first, then common system-font paths, then falls back to the average
# heuristic if PIL/none of those paths are available.
try:
    from PIL import ImageFont as _ImageFont
    _MEASURE_FONT = None
    for _font_candidate in (
        str(FONT_BOOK_PATH),
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
        "/Library/Fonts/Arial.ttf",  # macOS (older/alt location)
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ):
        if Path(_font_candidate).exists():
            _MEASURE_FONT = _ImageFont.truetype(_font_candidate, LABEL_FONT_SIZE)
            break
except ImportError:
    _MEASURE_FONT = None


def _text_width_px(text: str) -> float:
    if _MEASURE_FONT is not None:
        bbox = _MEASURE_FONT.getbbox(text)
        return bbox[2] - bbox[0]
    return len(text) * LABEL_FONT_SIZE * AVG_CHAR_WIDTH_RATIO


def wrap_label(text: str, max_width_px: float = LABEL_AVAILABLE_PX) -> str:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and _text_width_px(candidate) > max_width_px:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "<br>".join(lines)


def compute_block_layout(
    wrapped_labels: List[str],
    nonzero_buckets_per_as: List[List[str]],
) -> Tuple[List[float], List[List[float]], float]:
    """
    Each AS gets a block tall enough for whichever needs more room: its
    stack of individual cell-type bars, or its wrapped label + total-count
    line. Returns (as_label_y_centers, ct_bar_y_centers, total_content_height).
    ct_bar_y_centers[i] has one y-center per bar in nonzero_buckets_per_as[i],
    in the same order.
    """
    as_label_y_centers: List[float] = []
    ct_bar_y_centers: List[List[float]] = []
    running = 0.0

    for wrapped, buckets in zip(wrapped_labels, nonzero_buckets_per_as):
        n_ct = max(1, len(buckets))
        ct_block_height = n_ct * CT_BAR_THICKNESS + (n_ct - 1) * CT_BAR_GAP

        # +1 line for the total-count line appended under the AS name.
        n_lines = wrapped.count("<br>") + 1 + 1
        text_height = n_lines * ROW_LINE_HEIGHT

        block_height = max(ct_block_height, text_height) + ROW_PADDING
        block_top = running

        as_label_y_centers.append(block_top + block_height / 2)

        ct_start_y = block_top + (block_height - ct_block_height) / 2
        centers = [
            ct_start_y + i * (CT_BAR_THICKNESS + CT_BAR_GAP) + CT_BAR_THICKNESS / 2
            for i in range(len(buckets))
        ]
        ct_bar_y_centers.append(centers)

        running = block_top + block_height + AS_BLOCK_GAP

    content_height = running - AS_BLOCK_GAP if wrapped_labels else 0.0
    return as_label_y_centers, ct_bar_y_centers, content_height


# =============================================================================
# Data preparation
# =============================================================================

def prepare_chart_data(
    dist_data: dict,
    top9_labels: List[str],
) -> Tuple[List[str], Dict[str, List[float]], List[float]]:
    """Aggregate per-AS cell counts into the top-9 granular types plus
    "Other", matching the legend from shared.build_top9_granular_color_scheme().
    Values are raw cell counts, not percentages."""
    as_labels:            List[str]                   = dist_data["as_labels"]
    as_total_counts:      Dict[str, float]            = dist_data["as_total_counts"]
    per_as_distributions: Dict[str, Dict[str, float]] = dist_data["per_as_distributions"]

    top9_set = set(top9_labels)

    cell_type_counts: Dict[str, List[float]] = {ct: [] for ct in top9_labels}
    cell_type_counts["Other"] = []

    for as_label in as_labels:
        as_total = as_total_counts.get(as_label, 0.0)
        dist     = per_as_distributions.get(as_label, {})

        per_bucket: Dict[str, float] = {ct: 0.0 for ct in top9_labels}
        other_sum = 0.0

        for cell_type, weight in dist.items():
            cell_type = canonicalize_cell_label(cell_type)
            count = weight * as_total if weight <= 1.0 else weight
            if cell_type in top9_set:
                per_bucket[cell_type] += count
            else:
                other_sum += count

        for ct in top9_labels:
            cell_type_counts[ct].append(per_bucket[ct])
        cell_type_counts["Other"].append(other_sum)

    as_totals = [as_total_counts.get(l, 0.0) for l in as_labels]

    return as_labels, cell_type_counts, as_totals


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
    legend_entries: List[Tuple[str, str, str, float]],
    show_legend: bool,
) -> go.Figure:
    """legend_entries: ordered (label, hex, level2_label, count) — top 9
    granular cell types plus one "Other" entry. Each AS gets one bar per
    nonzero bucket (small multiples), not a single stacked bar."""
    fig = go.Figure()
    plot_order = [label for label, _hex, _lvl2, _count in legend_entries]
    color_map  = {label: hexcolor for label, hexcolor, _lvl2, _count in legend_entries}

    nonzero_buckets_per_as = [
        [ct for ct in plot_order if cell_type_counts[ct][i] > 0]
        for i in range(len(as_labels))
    ]

    as_label_y_centers, ct_bar_y_centers, content_height = compute_block_layout(
        wrapped_labels, nonzero_buckets_per_as
    )

    annotations: List[dict] = []
    max_ct_value = 0.0

    for cell_type in plot_order:
        xs, ys, hover_labels = [], [], []
        for i in range(len(as_labels)):
            buckets = nonzero_buckets_per_as[i]
            if cell_type not in buckets:
                continue
            row   = buckets.index(cell_type)
            count = cell_type_counts[cell_type][i]
            y     = ct_bar_y_centers[i][row]

            xs.append(count)
            ys.append(y)
            hover_labels.append(as_labels[i])
            max_ct_value = max(max_ct_value, count)

        if not xs:
            continue

        fig.add_trace(go.Bar(
            name=cell_type,
            x=xs,
            y=ys,
            width=[CT_BAR_THICKNESS] * len(xs),
            orientation="h",
            marker=dict(
                color=color_map[cell_type],
                line=dict(color=BAR_STROKE_COLOR, width=BAR_STROKE_WIDTH),
            ),
            legendgroup=cell_type,
            showlegend=False,
            hovertemplate=(
                f"<b>{cell_type}</b><br>"
                "%{customdata}<br>"
                "Cell count: %{x:,.0f}<extra></extra>"
            ),
            customdata=hover_labels,
        ))

    axis_max = max_ct_value * (1 + AXIS_HEADROOM_RATIO) if max_ct_value > 0 else 1.0

    # AS name + total cell count, both anchored left of the bars.
    for wrapped, total, y_center in zip(wrapped_labels, as_totals, as_label_y_centers):
        annotations.append(dict(
            x=-0.01,
            y=y_center,
            xref="paper",
            yref="y",
            text=f"{wrapped}<br><span style='color:{MUTED_TEXT_COLOR}'>{int(total):,} cells</span>",
            xanchor="right",
            yanchor="middle",
            align="right",
            showarrow=False,
            font=dict(family=FONT_FAMILY, size=LABEL_FONT_SIZE, color=MUTED_TEXT_COLOR),
        ))

    title_text    = f"<b>{organ.title()} — {tool.title()} — {sex.title()}</b>"
    subtitle_text = (
        f"<span style='font-size:{SUBTITLE_FONT_SIZE}px;color:{MUTED_TEXT_COLOR}'>"
        f"Each bar shows one cell type's count within an anatomical structure"
        f"</span>"
    )

    legend_rows = math.ceil(len(legend_entries) / LEGEND_NUM_COLUMNS) if show_legend else 0
    margin_bottom = (
        AXIS_TITLE_BAND + legend_rows * LEGEND_ROW_HEIGHT + LEGEND_BOTTOM_PAD
        if show_legend else MARGIN_BOTTOM_NO_LEGEND
    )

    total_height = max(CHART_HEIGHT_MIN, content_height + MARGIN_TOP + margin_bottom)

    if show_legend:
        for i, (label, hexcolor, _lvl2, _count) in enumerate(legend_entries):
            col = i % LEGEND_NUM_COLUMNS
            row = i // LEGEND_NUM_COLUMNS
            x_px = LEGEND_COL_START_PX + col * LEGEND_COL_WIDTH_PX
            d = AXIS_TITLE_BAND + row * LEGEND_ROW_HEIGHT + LEGEND_ROW_HEIGHT / 2
            annotations.append(dict(
                x=(x_px - MARGIN_LEFT) / PLOT_WIDTH,
                y=-d / content_height,
                xref="paper",
                yref="paper",
                text=f"<span style='color:{hexcolor}'>&#9632;</span>&nbsp;&nbsp;{label}",
                xanchor="left",
                yanchor="middle",
                align="left",
                showarrow=False,
                font=dict(family=FONT_FAMILY, size=LEGEND_FONT_SIZE, color=TEXT_COLOR),
            ))

    fig.update_layout(
        showlegend=False,
        title=dict(
            text=f"{title_text}<br>{subtitle_text}",
            font=dict(family=FONT_FAMILY, size=TITLE_FONT_SIZE, color=TEXT_COLOR),
            x=0.0,
            xanchor="left",
            pad=dict(l=LEGEND_COL_START_PX),
        ),
        xaxis=dict(
            visible=True,
            showgrid=True,
            gridcolor=GRID_COLOR,
            gridwidth=1,
            tickformat=",",
            tickfont=dict(family=FONT_FAMILY, size=16, color=MUTED_TEXT_COLOR),
            range=[0, axis_max],
            zeroline=False,
            title=dict(
                text=AXIS_TITLE_TEXT,
                font=dict(family=FONT_FAMILY, size=AXIS_TITLE_FONT_SIZE, color=MUTED_TEXT_COLOR),
            ),
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            ticklen=0,
            range=[content_height, 0],
        ),
        annotations=annotations,
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=PAPER_BG_COLOR,
        width=CHART_WIDTH,
        height=total_height,
        margin=dict(
            l=MARGIN_LEFT,
            r=MARGIN_RIGHT,
            t=MARGIN_TOP,
            b=margin_bottom,
        ),
        font=dict(family=FONT_FAMILY, color=TEXT_COLOR),
    )

    return fig


# =============================================================================
# Save — font embedding (SVG only)
# =============================================================================

def _font_face_css() -> str:
    """Base64-embeds Benton Sans Book/Bold as a 'BentonSansBook' family
    with two weights. Falls back to no embedded font (Arial) with a
    printed warning if the font files aren't present."""
    faces = []
    for path, weight in [(FONT_BOOK_PATH, 400), (FONT_BOLD_PATH, 700)]:
        if not path.exists():
            print(f"  Warning: font not found at {path}; falling back to Arial for this weight.")
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            "@font-face {"
            "font-family:'BentonSansBook';"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
            f"font-weight:{weight};"
            "font-style:normal;"
            "}"
        )
    if not faces:
        return ""
    return "<defs><style type=\"text/css\">" + "".join(faces) + "</style></defs>"


def embed_font_and_resize(svg_path: Path) -> None:
    """
    Post-process a kaleido-written SVG: inject embedded @font-face rules.

    Keeps kaleido's native px width/height + viewBox as-is — an earlier
    version rewrote them to literal cm units for true-physical-size
    printing, but Illustrator's SVG importer doesn't reliably rescale a
    viewBox against physical-unit width/height and rendered everything
    ~38x oversized.
    """
    svg_text = svg_path.read_text(encoding="utf-8")

    font_css = _font_face_css()
    if font_css:
        svg_text = re.sub(r"(<svg[^>]*>)", r"\1" + font_css, svg_text, count=1)

    svg_path.write_text(svg_text, encoding="utf-8")


def save_svg(fig: go.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Pass width/height explicitly — some kaleido versions ignore
        # fig.layout.width/height set via update_layout() and silently
        # fall back to Plotly's 700x500 default, squashing all the
        # content computed for the real (much taller) canvas.
        fig.write_image(
            str(output_path), format="svg",
            width=fig.layout.width, height=fig.layout.height,
        )
        embed_font_and_resize(output_path)
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
    svg_with    = base_folder / "svg" / "with-legend"
    svg_without = base_folder / "svg" / "without-legend"

    distribution_path = json_folder / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(
            f"Distribution JSON not found: {distribution_path}. "
            "Run 20_fetch_cell_distribution.py first."
        )

    dist_data          = json.loads(distribution_path.read_text(encoding="utf-8"))
    uberon_id          = dist_data.get("uberon_id", "")
    output_name        = build_output_stem(stem, uberon_id, tool_slug, shape)

    print(f"Loading supertree from: {supertree_path}")
    supertree, _ = load_supertree(supertree_path)

    color_map, legend_entries = build_top9_granular_color_scheme(
        organ_cell_counts=dist_data.get("organ_cell_counts", {}),
        cell_id_map=dist_data.get("cell_id_map", {}),
        supertree=supertree,
        palette=LEVEL2_TOP9_COLORS,
        other_color=OTHER_COLOR,
    )
    top9_labels = [label for label, _hex, _lvl2, _count in legend_entries if label != "Other"]
    print(f"\nTop-9 granular color scheme ({len(legend_entries)} legend entries):")
    for label, hexcolor, lvl2, count in legend_entries:
        lvl2_note = f" (lvl2: {lvl2})" if lvl2 else ""
        print(f"  {label}{lvl2_note} → {hexcolor}  [{count:,.0f} cells]")

    as_labels, cell_type_counts, as_totals = prepare_chart_data(dist_data, top9_labels)
    wrapped_labels = [wrap_label(l) for l in as_labels]

    print(f"\nGenerating SVGs for: {output_name}")

    fig_with = make_figure(
        organ=organ_name, sex=organ_sex, tool=tool,
        as_labels=as_labels, wrapped_labels=wrapped_labels,
        cell_type_counts=cell_type_counts, as_totals=as_totals,
        legend_entries=legend_entries, show_legend=True,
    )
    save_svg(fig_with, svg_with / f"{output_name}-with-legend.svg")

    fig_without = make_figure(
        organ=organ_name, sex=organ_sex, tool=tool,
        as_labels=as_labels, wrapped_labels=wrapped_labels,
        cell_type_counts=cell_type_counts, as_totals=as_totals,
        legend_entries=legend_entries, show_legend=False,
    )
    save_svg(fig_without, svg_without / f"{output_name}-without-legend.svg")


if __name__ == "__main__":
    main()