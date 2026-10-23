#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

_ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_sections.py"
sys.exit(subprocess.run([sys.executable, str(_ROOT_SCRIPT), *sys.argv[1:]]).returncode)
