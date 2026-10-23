#!/usr/bin/env python3
"""Compatibility forwarder for check_sections.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_sections.py"
_spec = importlib.util.spec_from_file_location("_canonical_check_sections", str(_ROOT_SCRIPT))
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load canonical check_sections from {_ROOT_SCRIPT}")

_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export public and internal utilities required by callers and tests
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

if __name__ == "__main__":
    _mod.main()
