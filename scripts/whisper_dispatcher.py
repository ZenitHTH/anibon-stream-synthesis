#!/usr/bin/env python3
"""Shim for lib/anibon/whisper_dispatcher.py."""
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from anibon.whisper_dispatcher import *

if __name__ == "__main__":
    from anibon.whisper_dispatcher import main
    sys.exit(main())
