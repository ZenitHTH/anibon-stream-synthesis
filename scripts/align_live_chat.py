#!/usr/bin/env python3
"""Slice a seconds-prefixed LiveChat event feed to per-transcript-chunk logs.

Input:   --events  parse_live_chat.py --raw-events feed (each line: <sec>TAB<[HH:MM:SS]> msg)
         --chunks transcript chunk dir (chunk_*.xml/.json/.txt, carries start_sec/end_sec)
Output:  livechat/<idx>.txt per chunk (events whose sec falls in [start_sec, end_sec)),
         livechat_index.json mapping chunk name -> file path.

Purpose: give each timestamper chunk runner the watchers' chat for its own
chunk, so it can infer situation + emotion of the live from both sides.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from interface import chunk_sort_key
try:
    from process.music.sensor import has_music_chat_surge
except ImportError:
    def has_music_chat_surge(_lines: list[str]) -> bool:
        return False


def load_events(events_path: Path) -> list[tuple[int, str]]:
    """Return sorted [(sec, line), ...] from the raw feed."""
    out = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                sec_str, text = line.split("\t", 1)
                out.append((int(sec_str), text))
            except ValueError:
                continue
    out.sort(key=lambda x: x[0])
    return out


def _parse_time_str(ts: str) -> int:
    """Parse HH:MM:SS or MM:SS to total seconds."""
    parts = [int(x) for x in ts.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def _parse_txt_chunk_window(p: Path) -> tuple[str, int, int]:
    """Parse start and end seconds from .txt chunk header line."""
    lines = p.read_text(encoding="utf-8").splitlines()
    start_sec, end_sec = 0, 0
    if lines:
        m = re.search(r"(\d{2}:\d{2}:\d{2})[–-](\d{2}:\d{2}:\d{2})", lines[0])
        if m:
            start_sec = _parse_time_str(m.group(1))
            end_sec = _parse_time_str(m.group(2))
    return p.stem, start_sec, end_sec


def _parse_chunk_window(p: Path) -> tuple[str, int, int]:
    """Parse window for a single chunk file based on format."""
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        return p.stem, int(data.get("start_sec", 0)), int(data.get("end_sec", 0))
    if p.suffix == ".xml":
        import xml.etree.ElementTree as ET
        root = ET.parse(p).getroot()
        return p.stem, int(root.get("start_sec", 0)), int(root.get("end_sec", 0))
    return _parse_txt_chunk_window(p)


def load_chunk_windows(chunks_dir: Path) -> list[tuple[str, int, int]]:
    """Return sorted [(name, start_sec, end_sec), ...] for all chunks."""
    candidates = sorted(chunks_dir.glob("chunk_*.json"), key=chunk_sort_key)
    if not candidates:
        candidates = sorted(chunks_dir.glob("chunk_*.xml"), key=chunk_sort_key)
    if not candidates:
        candidates = sorted(chunks_dir.glob("chunk_*.txt"), key=chunk_sort_key)
    windows = [_parse_chunk_window(p) for p in candidates]
    windows.sort(key=lambda w: w[1])
    return windows


def slice_events(events: list[tuple[int, str]], start_sec: int, end_sec: int) -> list[str]:
    """Slice events within half-open interval [start_sec, end_sec)."""
    return [text for sec, text in events if start_sec <= sec < end_sec]


def _write_chunk_livechat(out_dir: Path, name: str, lines: list[str], start: int, end: int) -> dict:
    out_file = out_dir / f"livechat_{name}.txt"
    out_file.write_text("".join(f"{l}\n" for l in lines), encoding="utf-8")
    print(f"[*] {name}: {len(lines)} chat lines ({start}-{end}s) -> {out_file}")
    return {"file": str(out_file), "count": len(lines), "start": start, "end": end}


def annotate_music_surges(index: dict[str, dict], slices: dict[str, list[str]]) -> None:
    """Flag chunks in index where chat music density indicates active background song."""
    for name, meta in index.items():
        meta["music_detected"] = has_music_chat_surge(slices.get(name, []))


def align(events_path: Path, chunks_dir: Path, out_dir: Path) -> dict:
    """Align raw events feed to chunk windows and write per-chunk files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(events_path)
    windows = load_chunk_windows(chunks_dir)
    if not windows or not events:
        print(f"[!] Missing chunks or events ({chunks_dir}, {events_path})", file=sys.stderr)
        return {}

    slices = {name: slice_events(events, start, end) for name, start, end in windows}
    index = {
        name: _write_chunk_livechat(out_dir, name, slices[name], start, end)
        for name, start, end in windows
    }
    (out_dir / "livechat_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(v["count"] for v in index.values())
    print(f"[*] Wrote {len(index)} aligned chat logs, {total} events total.")
    return index


def align_with_music_scan(events_path: Path, chunks_dir: Path, out_dir: Path) -> dict:
    """Align chat logs and annotate chunks exhibiting background music surges."""
    index = align(events_path, chunks_dir, out_dir)
    if not index:
        return {}
    events = load_events(events_path)
    windows = load_chunk_windows(chunks_dir)
    slices = {name: slice_events(events, start, end) for name, start, end in windows}
    annotate_music_surges(index, slices)
    (out_dir / "livechat_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, help="Raw event feed from parse_live_chat.py --raw-events")
    ap.add_argument("--chunks", required=True, help="Transcript chunk directory")
    ap.add_argument("-o", "--output-dir", default="livechat", help="Output dir for per-chunk chat logs")
    ap.add_argument("--scan-music", action="store_true", help="Scan chat for music mentions and annotate index")
    args = ap.parse_args()
    if args.scan_music:
        align_with_music_scan(Path(args.events), Path(args.chunks), Path(args.output_dir))
    else:
        align(Path(args.events), Path(args.chunks), Path(args.output_dir))
