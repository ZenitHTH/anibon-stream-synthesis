"""Compatibility entrypoint delegating to root ``scripts/validate_mood.py``."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_mood.py"


def _load_root_module():
    """Load the canonical root validate_mood module without self-import recursion."""
    spec = importlib.util.spec_from_file_location("_root_validate_mood", _ROOT_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {_ROOT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_root = _load_root_module()

TS_RE = _root.TS_RE
_FALLBACK_TONE = _root._FALLBACK_TONE
_OLD_FALLBACK = _root._OLD_FALLBACK
to_abs_sec = _root.to_abs_sec
Timestamp = _root.Timestamp
load_chunk_windows = _root.load_chunk_windows
parse_timestamps = _root.parse_timestamps
Validator = _root.Validator
report = _root.report
print_report = _root.print_report
main = _root.main

__all__ = [
    "TS_RE",
    "_FALLBACK_TONE",
    "_OLD_FALLBACK",
    "to_abs_sec",
    "Timestamp",
    "load_chunk_windows",
    "parse_timestamps",
    "Validator",
    "report",
    "print_report",
    "main",
]

if __name__ == "__main__":
    sys.exit(main())
