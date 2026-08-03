#!/usr/bin/env python3
"""Slice a seconds-prefixed LiveChat event feed to per-transcript-chunk logs.

Input:   --events  parse_live_chat.py --raw-events feed (each line: <sec>TAB<[HH:MM:SS]> msg)
         --chunks transcript chunk dir (chunk_*.xml/.json, carries start_sec/end_sec)
Output:  livechat/<idx>.txt per chunk (events whose sec falls in [start_sec, end_sec)),
         livechat_index.json mapping chunk name -> file path.

Purpose: give each timestamper subagent the watchers' chat for its own 5-minute
chunk, so it can infer situation + emotion of the live from both sides.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anibon.chunk_io import chunk_sort_key


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


def load_chunk_windows(chunks_dir: Path) -> list[tuple[str, int, int]]:
    """Return sorted [(name, start_sec, end_sec), ...] for all chunks."""
    candidates = sorted(chunks_dir.glob("chunk_*.json"), key=chunk_sort_key)
    if not candidates:
        candidates = sorted(chunks_dir.glob("chunk_*.xml"), key=chunk_sort_key)
    windows = []
    for p in candidates:
        if p.suffix == ".json":
            import json as _json
            data = _json.loads(p.read_text(encoding="utf-8"))
            windows.append((p.stem, int(data.get("start_sec", 0)), int(data.get("end_sec", 0))))
        else:
            import xml.etree.ElementTree as ET
            root = ET.parse(p).getroot()
            windows.append((p.stem, int(root.get("start_sec", 0)), int(root.get("end_sec", 0))))
    windows.sort(key=lambda w: w[1])
    return windows


def slice_events(events: list[tuple[int, str]], start_sec: int, end_sec: int) -> list[str]:
    return [text for sec, text in events if start_sec <= sec < end_sec]


def align(events_path: Path, chunks_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(events_path)
    windows = load_chunk_windows(chunks_dir)
    if not windows:
        print(f"[!] No chunk files found in {chunks_dir}", file=sys.stderr)
        return
    if not events:
        print(f"[!] No livechat events in {events_path}", file=sys.stderr)
        return

    index = {}
    for name, start, end in windows:
        lines = slice_events(events, start, end)
        out_file = out_dir / f"livechat_{name}.txt"
        out_file.write_text("".join(f"{l}\n" for l in lines), encoding="utf-8")
        index[name] = {"file": str(out_file), "count": len(lines),
                       "start": start, "end": end}
        print(f"[*] {name}: {len(lines)} chat lines ({start}-{end}s) -> {out_file}")

    (out_dir / "livechat_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(v["count"] for v in index.values())
    print(f"[*] Wrote {len(index)} aligned chat logs, {total} events total.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True, help="Raw event feed from parse_live_chat.py --raw-events")
    ap.add_argument("--chunks", required=True, help="Transcript chunk directory")
    ap.add_argument("-o", "--output-dir", default="livechat", help="Output dir for per-chunk chat logs")
    args = ap.parse_args()
    align(Path(args.events), Path(args.chunks), Path(args.output_dir))
