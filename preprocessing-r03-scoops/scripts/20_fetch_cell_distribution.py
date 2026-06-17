#!/usr/bin/env python3
"""
20_fetch_cell_distribution.py — Fetch cell type data from HRApop API for all
anatomical structures of the configured organ, auto-match AS labels to GLB
node names, then output per-AS distributions and proportional node allocations
as JSON for use by script 30.

Reads:  config.yaml
        Outputs/downloaded_organs/<glb_filename>  (to extract GLB node names)
Writes: Outputs/annotated_organs/<organ>/json/<stem>_distribution.json
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    resolve_glb_filename,
    load_config,
    normalize_cell_label_key,
    compact_ontology_id,
    parse_float,
    safe_name,
    values_match_filter,
    auto_match_as_to_glb_nodes,
)


# =============================================================================
# Fetching
# =============================================================================

def fetch_url_bytes(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url=url,
        headers={"Accept": accept, "User-Agent": "hra-cell-pipeline/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_hra_pop_rows(api_url: str) -> Tuple[List[Dict[str, str]], bytes]:
    """Try CSV then JSON formats. Returns (rows, raw_bytes)."""
    errors: List[str] = []

    for url in [api_url, api_url + ".csv", api_url + "?_format=csv"]:
        try:
            raw = fetch_url_bytes(url, accept="text/csv")
            decoded = raw.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(decoded.splitlines())
            rows = [dict(row) for row in reader]
            if rows and "cell_label" in rows[0]:
                return rows, raw
        except Exception as exc:
            errors.append(f"CSV attempt failed for {url}: {exc}")

    for url in [api_url, api_url + ".json", api_url + "?_format=json"]:
        try:
            raw = fetch_url_bytes(url, accept="application/json")
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(data, list):
                return [dict(r) for r in data], raw
            if isinstance(data, dict):
                for key in ("results", "data", "rows"):
                    maybe = data.get(key)
                    if isinstance(maybe, list):
                        return [dict(r) for r in maybe], raw
        except Exception as exc:
            errors.append(f"JSON attempt failed for {url}: {exc}")

    raise RuntimeError("Could not fetch HRApop rows.\n" + "\n".join(errors))


# =============================================================================
# GLB node extraction
# =============================================================================

def get_glb_node_names(glb_path: Path) -> List[str]:
    """Load a GLB and return all geometry node names."""
    loaded = trimesh.load(str(glb_path), force="scene")
    if isinstance(loaded, trimesh.Scene):
        return list(loaded.graph.nodes_geometry)
    return []


# =============================================================================
# Per-AS distribution building
# =============================================================================

def get_all_as_labels(
    rows: List[Dict[str, str]],
    organ: str,
    tool: str,
    sex: str,
    modality: str,
) -> List[str]:
    seen = set()
    result = []
    for row in rows:
        if not values_match_filter(row.get("organ", ""), organ):
            continue
        if not values_match_filter(row.get("tool", ""), tool):
            continue
        if not values_match_filter(row.get("sex", ""), sex):
            continue
        if not values_match_filter(row.get("modality", ""), modality):
            continue
        as_label = str(row.get("as_label", "")).strip()
        if as_label and as_label not in seen:
            seen.add(as_label)
            result.append(as_label)
    return result


def filter_rows_for_as(
    rows: List[Dict[str, str]],
    organ: str,
    as_label: str,
    tool: str,
    sex: str,
    modality: str,
) -> List[Dict[str, str]]:
    return [
        row for row in rows
        if values_match_filter(row.get("organ", ""), organ)
        and values_match_filter(row.get("as_label", ""), as_label)
        and values_match_filter(row.get("tool", ""), tool)
        and values_match_filter(row.get("sex", ""), sex)
        and values_match_filter(row.get("modality", ""), modality)
    ]


def build_distribution_for_as(rows: List[Dict[str, str]]) -> Dict[str, float]:
    distribution: Dict[str, float] = {}
    for row in rows:
        label = str(row.get("cell_label", "")).strip()
        if not label:
            continue
        pct = parse_float(row.get("cell_percentage", ""))
        count = parse_float(row.get("cell_count", ""))
        weight = pct if pct > 0 else count  # prefer percentage
        if weight > 0:
            distribution[label] = distribution.get(label, 0.0) + weight
    return distribution


def normalize_distribution(distribution: Dict[str, float]) -> Dict[str, float]:
    total = sum(distribution.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in distribution.items()}


def get_total_cell_count_for_as(rows: List[Dict[str, str]]) -> float:
    return sum(parse_float(row.get("cell_count", "")) for row in rows)


def build_cell_id_map(rows: List[Dict[str, str]]) -> Dict[str, str]:
    cell_id_map: Dict[str, str] = {}
    for row in rows:
        label = str(row.get("cell_label", "")).strip()
        raw_id = str(row.get("cell_id", "")).strip()
        if not label or not raw_id:
            continue
        key = normalize_cell_label_key(label)
        if key not in cell_id_map:
            cell_id_map[key] = compact_ontology_id(raw_id)
    return cell_id_map


# =============================================================================
# Global top-N cell types across all AS
# =============================================================================

def get_global_top_n(
    per_as_distributions: Dict[str, Dict[str, float]],
    top_n: int,
) -> List[str]:
    global_weights: Dict[str, float] = {}
    for dist in per_as_distributions.values():
        for label, weight in dist.items():
            global_weights[label] = global_weights.get(label, 0.0) + weight
    sorted_labels = sorted(global_weights.items(), key=lambda x: x[1], reverse=True)
    return [label for label, _ in sorted_labels[:top_n]]


# =============================================================================
# Node allocation
# =============================================================================

def allocate_nodes(
    as_total_counts: Dict[str, float],
    total_nodes: int,
) -> Dict[str, int]:
    grand_total = sum(as_total_counts.values())
    if grand_total <= 0:
        equal = total_nodes // len(as_total_counts)
        return {k: equal for k in as_total_counts}

    allocated: Dict[str, int] = {}
    remainder = total_nodes
    as_list = list(as_total_counts.items())

    for i, (as_label, count) in enumerate(as_list):
        if i == len(as_list) - 1:
            allocated[as_label] = remainder
        else:
            n = round(total_nodes * count / grand_total)
            allocated[as_label] = n
            remainder -= n

    return allocated


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")

    api_url = config["apis"]["hra_pop"]
    organ_name = config["organ"]["name"]
    organ_sex = config["organ"]["sex"]
    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    tool = config["filters"]["tool"]
    modality = config["filters"].get("modality", "")
    top_n = config["markers"]["top_cell_type_count"]
    total_nodes = config["markers"]["num_nodes"]
    save_csv = config["output"].get("save_hra_pop_csv", False)
    organs_folder = Path(config["output"]["organs_folder"])

    # Output folders
    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    json_folder = base_folder / "json"
    json_folder.mkdir(parents=True, exist_ok=True)

    # Resolve GLB filename
    organ_side = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)
        print(f"Auto-resolved GLB filename: {glb_filename}")

    stem = Path(glb_filename).stem
    glb_path = organs_folder / glb_filename

    if not glb_path.exists():
        raise FileNotFoundError(
            f"GLB not found: {glb_path}. Run 10_download_organs.py first."
        )

    # Get GLB node names
    print(f"Reading GLB node names from: {glb_path}")
    glb_node_names = get_glb_node_names(glb_path)
    print(f"GLB nodes found: {len(glb_node_names)}")
    for n in sorted(glb_node_names):
        print(f"  {n}")

    # Fetch HRApop data
    print(f"\nFetching HRApop data from: {api_url}")
    rows, raw = fetch_hra_pop_rows(api_url)
    print(f"Total rows fetched: {len(rows)}")

    if save_csv:
        cache_path = json_folder / "hra_pop_raw.csv"
        cache_path.write_bytes(raw)
        print(f"Saved raw HRApop CSV to: {cache_path}")

    # Get all AS labels for this organ/tool/sex
    as_labels = get_all_as_labels(rows, organ_name, tool, organ_sex, modality)
    print(f"\nHRApop AS labels found: {len(as_labels)}")
    for label in as_labels:
        print(f"  {label}")

    if not as_labels:
        raise ValueError(
            f"No AS labels found for organ='{organ_name}', "
            f"tool='{tool}', sex='{organ_sex}'. Check config.yaml."
        )

    # Auto-match AS labels to GLB nodes
    print(f"\nAuto-matching AS labels to GLB nodes (organ='{organ_name}'):")
    as_to_glb_node = auto_match_as_to_glb_nodes(as_labels, glb_node_names, organ_name)

    matched_as_labels = [l for l, n in as_to_glb_node.items() if n is not None]
    unmatched = [l for l, n in as_to_glb_node.items() if n is None]

    print(f"\nMatched: {len(matched_as_labels)} | Unmatched (skipped): {len(unmatched)}")

    if not matched_as_labels:
        raise ValueError(
            "No AS labels could be matched to GLB nodes. "
            "Check organ name and GLB file."
        )

    # Build per-AS distributions
    per_as_distributions: Dict[str, Dict[str, float]] = {}
    per_as_normalized: Dict[str, Dict[str, float]] = {}
    as_total_counts: Dict[str, float] = {}

    for as_label in matched_as_labels:
        as_rows = filter_rows_for_as(rows, organ_name, as_label, tool, organ_sex, modality)
        dist = build_distribution_for_as(as_rows)
        total_count = get_total_cell_count_for_as(as_rows)

        per_as_distributions[as_label] = dist
        per_as_normalized[as_label] = normalize_distribution(dist)
        as_total_counts[as_label] = total_count

        print(f"  {as_label}: {len(dist)} cell types, total count={total_count:.0f}")

    # Global top-N
    global_top_labels = get_global_top_n(per_as_distributions, top_n)
    print(f"\nGlobal top {top_n} cell types:")
    for label in global_top_labels:
        print(f"  {label}")

    # Cell ID map
    cell_id_map = build_cell_id_map(rows)
    print(f"\nCell ID map entries: {len(cell_id_map)}")

    # Proportional node allocation
    node_allocation = allocate_nodes(as_total_counts, total_nodes)
    print(f"\nNode allocation (total={total_nodes}):")
    for as_label, n in node_allocation.items():
        print(f"  {as_label}: {n} nodes")

    # Save distribution JSON
    output_path = json_folder / f"{stem}_distribution.json"
    output_data = {
        "stem": stem,
        "organ": organ_name,
        "sex": organ_sex,
        "tool": tool,
        "modality": modality,
        "top_cell_type_count": top_n,
        "global_top_labels": global_top_labels,
        "as_labels": matched_as_labels,
        "as_to_glb_node": {k: v for k, v in as_to_glb_node.items() if v is not None},
        "as_node_counts": {k: len(v) for k, v in as_to_glb_node.items() if v is not None},
        "unmatched_as_labels": unmatched,
        "per_as_distributions": per_as_distributions,
        "per_as_normalized": per_as_normalized,
        "as_total_counts": as_total_counts,
        "node_allocation": node_allocation,
        "cell_id_map": cell_id_map,
    }

    output_path.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nDistribution saved to: {output_path}")


if __name__ == "__main__":
    main()