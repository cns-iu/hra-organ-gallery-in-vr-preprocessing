#!/usr/bin/env python3
"""
setup_and_run.py — One-command pipeline runner.

Creates a virtual environment, installs dependencies from requirements.txt,
then runs all scripts in scripts/ in numeric order (skipping shared.py).

Usage:
    python setup_and_run.py
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
VENV = ROOT / ".venv"

# Step 1: create venv if it doesn't exist
if not VENV.exists():
    print("Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

# Step 2: install dependencies
pip_path = VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "pip"
print("Installing dependencies...")
subprocess.check_call([str(pip_path), "install", "-r", str(ROOT / "requirements.txt")])

# Step 3: run scripts sequentially (numeric order, skip shared.*)
python_path = VENV / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
SCRIPTS_DIR = ROOT / "scripts"

scripts_to_run = sorted([
    f for f in os.listdir(SCRIPTS_DIR)
    if f.endswith(".py") and "shared" not in f.split(".")[0]
])

for script in scripts_to_run:
    script_path = SCRIPTS_DIR / script
    print(f"\nRunning {script_path.relative_to(ROOT)}...")
    subprocess.check_call([str(python_path), str(script_path)])

print("\nAll scripts completed successfully!")
