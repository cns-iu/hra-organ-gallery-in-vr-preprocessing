#!/usr/bin/env python3
"""
shared.py — Single source of truth for constants and shared utilities.

Imports from here:
    resolve_glb_filename, load_config, normalize_match_text,
    normalize_cell_label_key, safe_name,
    hex_to_rgb, hex_to_float,
    PALETTE, OTHERS, CELL_TYPE_FULL_NAMES, ORGAN_CELL_COUNTS
"""

from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# =============================================================================
# Color palette (hex strings — single source of truth)
# =============================================================================
# Top-9 colors for the most prevalent cell types across all anatomical structures.
# OTHERS is used for all remaining cell types.

PALETTE: List[str] = [
    "#51E1E9",  # teal
    "#CD8490",  # pink
    "#75D68A",  # green
    "#F4A42C",  # orange
    "#507AED",  # blue
    "#E154D8",  # magenta
    "#E5E368",  # yellow
    "#8B68EB",  # purple
    "#DF4B40",  # coral/red
]

OTHERS: str = "#9192BA"  # grey — all cell types beyond the top 9


# =============================================================================
# Hex color helpers
# =============================================================================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert a hex color string (#RRGGBB) to an (R, G, B) integer tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_to_float(hex_color: str) -> Tuple[float, float, float]:
    """Convert a hex color string (#RRGGBB) to a (R, G, B) float tuple (0.0–1.0)."""
    r, g, b = hex_to_rgb(hex_color)
    return r / 255.0, g / 255.0, b / 255.0


# =============================================================================
# Cell type display names
# =============================================================================
# Maps normalized cell label keys → human-readable full names for the legend.

CELL_TYPE_FULL_NAMES: Dict[str, str] = {
    "fibroblast":                       "Fibroblast",
    "endothelial":                      "Endothelial Cell",
    "cardiomyocyte":                    "Cardiomyocyte",
    "macrophage":                       "Macrophage",
    "smooth_muscle":                    "Smooth Muscle Cell",
    "pericyte":                         "Pericyte",
    "t_cell":                           "T Cell",
    "b_cell":                           "B Cell",
    "mast_cell":                        "Mast Cell",
    "neuronal":                         "Neuronal Cell",
    "adipocyte":                        "Adipocyte",
    "epithelial":                       "Epithelial Cell",
    "proximal_tubule":                  "Proximal Tubule Cell",
    "distal_convoluted_tubule":         "Distal Convoluted Tubule Cell",
    "loop_of_henle":                    "Loop of Henle Cell",
    "collecting_duct":                  "Collecting Duct Cell",
    "podocyte":                         "Podocyte",
    "mesangial":                        "Mesangial Cell",
}

# =============================================================================
# Organ total cell counts (for legend / JSON metadata)
# =============================================================================

ORGAN_CELL_COUNTS: Dict[str, Dict] = {
    "heart": {
        "total_cells":  2_000_000_000,
        "notes":        "Estimated 2 billion cells in the adult human heart.",
        "source":       "Bergmann et al., 2015",
        "doi":          "10.1126/science.aaa8697",
    },
    "kidney": {
        "total_cells":  1_500_000_000,
        "notes":        "Estimated 1.5 billion cells per kidney.",
        "source":       "Lote, 2012",
        "doi":          "",
    },
}

# =============================================================================
# Manual AS label → GLB node overrides
# =============================================================================
# Used when fuzzy matching fails due to abbreviations or naming mismatches.
# Key: lowercased HRApop AS label, Value: GLB node name

AS_LABEL_OVERRIDES: Dict[str, List[str]] = {
    "posteromedial head of posterior papillary muscle of left ventricle": [
        "VH_F_papillary_muscle_of_heart_posmed"
    ],
}

# =============================================================================
# GLB filename resolution
# =============================================================================

def resolve_glb_filename(organ_name: str, organ_sex: str, side: str = "") -> str:
    """
    Auto-resolve a GLB filename from organ name, sex, and optional side.

    Examples:
        heart,  female, ""      → 3d-vh-f-heart.glb
        kidney, female, "left"  → 3d-vh-f-kidney-l.glb
        eye,    male,   "right" → 3d-vh-m-eye-r.glb
    """
    sex_code = "f" if organ_sex.lower() == "female" else "m"
    name_slug = organ_name.lower().strip().replace(" ", "-")
    side = (side or "").strip().lower()
    side_code = {"left": "-l", "right": "-r"}.get(side, "")
    return f"3d-vh-{sex_code}-{name_slug}{side_code}.glb"


# =============================================================================
# Config loading
# =============================================================================

def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================
# Text normalisation helpers
# =============================================================================

def normalize_match_text(text: str) -> str:
    """
    Normalise a string for fuzzy AS label → GLB node matching.
    Lowercases, strips punctuation, collapses whitespace.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_cell_label_key(label: str) -> str:
    """
    Normalise a cell type label to a dict key.
    Lowercases and replaces spaces/hyphens with underscores.
    """
    return re.sub(r"[\s\-]+", "_", label.strip().lower())


def safe_name(text: str) -> str:
    """
    Convert arbitrary text to a safe GLB node / material name.
    Replaces non-alphanumeric characters with underscores.
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)


# =============================================================================
# Ontology / data helpers (used by 20_fetch_cell_distribution.py)
# =============================================================================

def compact_ontology_id(url_or_id: str) -> str:
    """
    Compact a full ontology URL to a short CURIE-style ID.

    Examples:
        http://purl.obolibrary.org/obo/CL_0000057  →  CL:0000057
        https://purl.org/sig/ont/fma/fma7088       →  FMA:7088
        CL_0000057                                  →  CL:0000057  (already short)
    """
    s = (url_or_id or "").strip()
    # Extract the final path component
    tail = s.rstrip("/").split("/")[-1]
    # Replace underscore separator with colon (CL_0000057 → CL:0000057)
    match = re.match(r"^([A-Za-z]+)[_:](\d+)$", tail)
    if match:
        return f"{match.group(1).upper()}:{match.group(2)}"
    return tail


def parse_float(value) -> float:
    """Safely parse a value to float; return 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def values_match_filter(value: str, filter_value: str) -> bool:
    """
    Case-insensitive substring filter.
    Returns True if filter_value is empty or is contained in value.
    """
    if not filter_value:
        return True
    return filter_value.lower() in value.lower()


def auto_match_as_to_glb_nodes(
    as_labels: List[str],
    glb_node_names: List[str],
    organ_name: str,
) -> Dict[str, Optional[List[str]]]:
    organ_slug = normalize_match_text(organ_name)

    norm_to_glb: Dict[str, str] = {}
    for node in glb_node_names:
        norm = normalize_match_text(node)
        for prefix in [f"vh_f_{organ_slug}_", f"vh_m_{organ_slug}_",
                       f"vh_f_", f"vh_m_", organ_slug + "_", organ_slug]:
            if norm.startswith(prefix):
                norm = norm[len(prefix):]
                break
        norm_to_glb[norm] = node

    result: Dict[str, Optional[List[str]]] = {}

    for as_label in as_labels:
        # Pass 0: manual override
        if as_label.lower() in AS_LABEL_OVERRIDES:
            result[as_label] = AS_LABEL_OVERRIDES[as_label.lower()]
            print(f"  ✓  '{as_label}' → {result[as_label]} (manual override)")
            continue

        norm_as = normalize_match_text(as_label)
        for prefix in [organ_slug + " ", organ_slug]:
            if norm_as.startswith(prefix):
                norm_as = norm_as[len(prefix):]
                break

        matches: List[str] = []

        # Pass 1: exact normalised match
        for norm_node, original in norm_to_glb.items():
            if norm_as == norm_node:
                matches.append(original)

        # Pass 2: substring match
        if not matches:
            for norm_node, original in norm_to_glb.items():
                if norm_as in norm_node or norm_node in norm_as:
                    matches.append(original)

        # Pass 3: token overlap
        if not matches:
            as_tokens = set(norm_as.split())
            for norm_node, original in norm_to_glb.items():
                node_tokens = set(norm_node.split())
                overlap = as_tokens & node_tokens
                if len(overlap) >= max(1, len(as_tokens) // 2):
                    matches.append(original)

        if matches:
            result[as_label] = matches
            print(f"  ✓  '{as_label}' → {matches}")
        else:
            result[as_label] = None
            print(f"  ✗  '{as_label}' → no match")

    return result