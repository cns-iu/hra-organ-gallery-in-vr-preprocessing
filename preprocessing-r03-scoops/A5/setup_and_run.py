#!/usr/bin/env python3
"""
setup_and_run.py — Run the full A5 pipeline (10 -> 20 -> 30 -> 40 -> 50 -> 51)
in order, against this folder's own config.yaml.

50 (PNG) is kept alongside 51 (SVG) for quick-preview/testing purposes,
even though 51 is the actual print deliverable.

Chdirs into its own directory first, so config.yaml's relative output
paths always resolve under A5/ regardless of invocation directory.

If any stage raises, the pipeline stops there — the traceback shows
which of the six stages failed.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Filenames start with a digit, so each is loaded from its file path via
# importlib rather than a plain `import 10_download_organs`.
STAGES = [
    "10_download_organs",
    "20_fetch_cell_distribution",
    "30_generate_markers",
    "40_generate_legend",
    "50_generate_pngs",
    "51_generate_svgs",
]


def run_stage(stage_name: str) -> None:
    module_path = SCRIPTS_DIR / f"{stage_name}.py"
    print(f"\n{'=' * 70}\n{stage_name}\n{'=' * 70}")
    spec = importlib.util.spec_from_file_location(stage_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main() -> None:
    os.chdir(PROJECT_ROOT)
    for stage in STAGES:
        run_stage(stage)
    print(f"\n{'=' * 70}\nA5 pipeline complete.\n{'=' * 70}")


if __name__ == "__main__":
    main()