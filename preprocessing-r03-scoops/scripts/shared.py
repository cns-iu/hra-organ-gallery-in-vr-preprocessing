#!/usr/bin/env python3
"""
shared.py — Single source of truth for constants and shared utilities.

Imports from here:
    resolve_glb_filename, load_config, normalize_match_text,
    normalize_cell_label_key, compact_ontology_id, parse_float,
    safe_name, values_match_filter, auto_match_as_to_glb_nodes,
    hex_to_rgb, hex_to_float, load_supertree,
    PALETTE, CELL_TYPE_FULL_NAMES, ORGAN_CELL_COUNTS
"""

from __future__ import annotations

import csv
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

# =============================================================================
# Color palette (hex strings — single source of truth)
# =============================================================================
# 11 colors, one per supertree cell type, ranked from most to least prevalent.
# PALETTE[0] → highest cell-count cell type, PALETTE[10] → lowest.

PALETTE: List[str] = [
    "#70A5A8",  # 1 — most prevalent cell type
    "#8DC599",  # 2
    "#F9CE8D",  # 3
    "#E97B74",  # 4
    "#CD8490",  # 5
    "#A294C9",  # 6
    "#637597",  # 7
    "#EDB8AC",  # 8
    "#D6B6D7",  # 9
    "#95CBCF",  # 10
    "#8C3C41",  # 11 — least prevalent cell type
]


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
# Supertree loading
# =============================================================================

def load_supertree(path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Load Bruce's supertree CSV (local path or Google Sheets export URL) and return
    two mappings:
        cell_to_label: CL:XXXXXXX (leaf cell ID) → supertree label (AS/2/LABEL or AS/3/LABEL fallback)
        cell_to_id:    CL:XXXXXXX (leaf cell ID) → supertree CL ID (AS/2/ID or AS/3/ID fallback)

    Filters to azimuth, celltypist, and popv sources only.
    Skips the root 'cell' row (CL:0000000 with no AS/2 or AS/3).
    For rows with an AS/2/LABEL but no AS/2/ID, generates ASCTB-TEMP-<label>.
    """
    sources = {"azimuth", "celltypist", "popv"}
    cell_to_label: Dict[str, str] = {}
    cell_to_id:    Dict[str, str] = {}

    df = pd.read_csv(path, encoding="utf-8-sig")

    for _, row in df.iterrows():
        source = str(row.get("CT/1 - Sources", "")).strip().lower()
        if source not in sources:
            continue

        # Resolve leaf cell ID — deepest non-null AS/n/ID
        leaf_id = None
        for i in range(12, 0, -1):
            v = str(row.get(f"AS/{i}/ID", "")).strip()
            if v and v.lower() != "nan":
                leaf_id = compact_ontology_id(v)
                break
        if not leaf_id:
            continue

        # Resolve label and ID — AS/2 first, then AS/3 fallback
        as2_label = str(row.get("AS/2/LABEL", "")).strip()
        as2_id    = str(row.get("AS/2/ID",    "")).strip()
        as3_label = str(row.get("AS/3/LABEL", "")).strip()
        as3_id    = str(row.get("AS/3/ID",    "")).strip()

        as2_label = "" if as2_label.lower() == "nan" else as2_label
        as2_id    = "" if as2_id.lower()    == "nan" else as2_id
        as3_label = "" if as3_label.lower() == "nan" else as3_label
        as3_id    = "" if as3_id.lower()    == "nan" else as3_id

        if as2_label:
            level_label = as2_label
            level_id    = compact_ontology_id(as2_id) if as2_id else f"ASCTB-TEMP-{as2_label}"
        elif as3_label:
            level_label = as3_label
            level_id    = compact_ontology_id(as3_id) if as3_id else f"ASCTB-TEMP-{as3_label}"
        else:
            continue

        if leaf_id not in cell_to_label:
            cell_to_label[leaf_id] = level_label
            cell_to_id[leaf_id]    = level_id

    return cell_to_label, cell_to_id


# =============================================================================
# Cell type display names
# =============================================================================

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
        "total_cells":  7_500_000_000,
        "notes":        "The human heart contains an estimated 2-3 billion cardiac muscle cells, but these account for less than a third of the total cell number in the heart.",
        "source":       "Cell Communications in the Heart",
        "doi":          "10.1161/CIRCULATIONAHA.108.847731",
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

AS_LABEL_OVERRIDES: Dict[str, List[str]] = {
    "posteromedial head of posterior papillary muscle of left ventricle": [
        "VH_F_papillary_muscle_of_heart_posmed",
        "VH_M_papillary_muscle_of_heart_posmed",
    ],
}

# =============================================================================
# GLB filename resolution
# =============================================================================

def resolve_glb_filename(organ_name: str, organ_sex: str, side: str = "") -> str:
    sex_code  = "f" if organ_sex.lower() == "female" else "m"
    name_slug = organ_name.lower().strip().replace(" ", "-")
    side      = (side or "").strip().lower()
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
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_cell_label_key(label: str) -> str:
    return re.sub(r"[\s\-]+", "_", label.strip().lower())


def safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)


# =============================================================================
# Ontology / data helpers
# =============================================================================

def compact_ontology_id(url_or_id: str) -> str:
    """
    Compact a full ontology URL to a short CURIE-style ID.

    Examples:
        http://purl.obolibrary.org/obo/CL_0000057  →  CL:0000057
        CL_0000057                                  →  CL:0000057
    """
    s = (url_or_id or "").strip()
    tail = s.rstrip("/").split("/")[-1]
    match = re.match(r"^([A-Za-z]+)[_:](\d+)$", tail)
    if match:
        return f"{match.group(1).upper()}:{match.group(2)}"
    return tail


def parse_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def values_match_filter(value: str, filter_value: str) -> bool:
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

        for norm_node, original in norm_to_glb.items():
            if norm_as == norm_node:
                matches.append(original)

        if not matches:
            for norm_node, original in norm_to_glb.items():
                if norm_as in norm_node or norm_node in norm_as:
                    matches.append(original)

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