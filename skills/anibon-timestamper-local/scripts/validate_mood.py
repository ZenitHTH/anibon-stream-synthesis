#!/usr/bin/env python3
"""Label timestamps with their chunk's mood + tone guidance (local runner wrapper)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[3] / "scripts" / "validate_mood.py"
_spec = importlib.util.spec_from_file_location("root_validate_mood", _TARGET)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

Validator = _mod.Validator
load_chunk_windows = _mod.load_chunk_windows
parse_timestamps = _mod.parse_timestamps
report = _mod.report
print_report = _mod.print_report
main = _mod.main

if __name__ == "__main__":
    sys.exit(main())
