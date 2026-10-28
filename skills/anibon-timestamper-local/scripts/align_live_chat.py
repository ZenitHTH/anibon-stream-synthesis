#!/usr/bin/env python3
"""Slice a seconds-prefixed LiveChat event feed to per-transcript-chunk logs (local runner wrapper)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[3] / "scripts" / "align_live_chat.py"
_spec = importlib.util.spec_from_file_location("root_align_live_chat", _TARGET)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

align = _mod.align
load_events = _mod.load_events
load_chunk_windows = _mod.load_chunk_windows
slice_events = _mod.slice_events

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, help="Raw event feed from parse_live_chat.py --raw-events")
    ap.add_argument("--chunks", required=True, help="Transcript chunk directory")
    ap.add_argument("-o", "--output-dir", default="livechat", help="Output dir for per-chunk chat logs")
    args = ap.parse_args()
    align(Path(args.events), Path(args.chunks), Path(args.output_dir))
