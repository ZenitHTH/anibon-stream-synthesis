#!/usr/bin/env python3
"""Label timestamps with their chunk's mood + tone guidance (report-only).

Companion to analyze_555.py. analyze_555.py emits mood_555.json verdicts per chunk;
this script annotates each generated timestamp with the chunk's mood + the Thai
tone-hint verbs the AI MAY draw from.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TS_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})")

_FALLBACK_TONE = {"tone": "เขียนตามอารมณ์ของเหตุการณ์", "verbs": ["แซว", "วิเคราะห์", "สรุป"]}

_OLD_FALLBACK = {
    "MEME_PULSE": {"tone": "ตลกปั่น ๆ แซวขำ ๆ", "verbs": ["แซว", "ล้อ", "ขำ", "ปั่น"]},
    "WARM": {"tone": "บรรยากาศเป็นกันเอง คุยเพลิน ๆ", "verbs": ["แซว", "เม้าท์", "เล่า"]},
    "HOT": {"tone": "บรรยากาศคึกคัก", "verbs": ["กระตุ้น", "ปั่น"]},
    "QUIET": {"tone": "คุยสบาย ๆ เลือกคำอิสระ", "verbs": ["พูดคุย", "วิเคราะห์"]},
}


def to_abs_sec(hh: str, mm: str, ss: str) -> int:
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


@dataclass
class Timestamp:
    """A parsed timestamp line."""
    abs_sec: int
    desc: str
    raw: str


def _load_windows_from_index(index_path: Path) -> Dict[str, Tuple[int, int]]:
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    windows = {}
    for chunk, info in idx.items():
        if isinstance(info, dict) and isinstance(info.get("start"), int) and isinstance(info.get("end"), int):
            windows[chunk] = (info["start"], info["end"])
    return windows


def _load_windows_from_dir(livechat_dir: Path) -> Dict[str, Tuple[int, int]]:
    windows = {}
    for p in sorted(livechat_dir.glob("livechat_chunk_*.txt")):
        times = [to_abs_sec(*m.groups()) for line in p.read_text(encoding="utf-8").splitlines() if (m := TS_RE.search(line))]
        if times:
            windows[p.stem.replace("livechat_chunk_", "chunk_")] = (min(times), max(times) + 1)
    return windows


def load_chunk_windows(livechat_dir: str, index_path: str = "") -> Dict[str, Tuple[int, int]]:
    """Resolve chunk -> (start_sec, end_sec) from index or chat logs."""
    if index_path and Path(index_path).is_file():
        return _load_windows_from_index(Path(index_path))
    if livechat_dir and Path(livechat_dir).is_dir():
        return _load_windows_from_dir(Path(livechat_dir))
    return {}


def parse_timestamps(path: Path) -> List[Timestamp]:
    """Extract (time, description) records from the timestamp file."""
    stamps: List[Timestamp] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = TS_RE.match(line)
        if m and "]" in line:
            desc = line.split("] ")[-1] if "] " in line else line
            stamps.append(Timestamp(abs_sec=to_abs_sec(*m.groups()), desc=desc, raw=line))
    return stamps


class Validator:
    """Resolves timestamps to chunks and annotates them with mood + tone."""

    def __init__(self, mood: dict, windows: Dict[str, Tuple[int, int]]):
        self.mood = mood
        self.windows = windows

    def chunk_for(self, abs_sec: int) -> Optional[str]:
        for c, (s, e) in self.windows.items():
            if s <= abs_sec < e:
                return c
        return None

    def _seg_secs(self, seg_time: str) -> int:
        h, m, s = seg_time.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    def in_mood_segment(self, chunk: str, abs_sec: int) -> bool:
        segs = self.mood.get(chunk, {}).get("segments")
        if not segs:
            return True
        for s in segs:
            if self._seg_secs(s["start"]) <= abs_sec < self._seg_secs(s["end"]):
                return s.get("mood") != "natural"
        return False

    def annotate(self, stamp: Timestamp) -> Optional[dict]:
        chunk = self.chunk_for(stamp.abs_sec)
        if not chunk or chunk not in self.mood:
            return None
        verdict = self.mood[chunk].get("verdict", "")
        return {
            "chunk": chunk,
            "verdict": verdict,
            "tone": self._tone_for(chunk, verdict),
            "in_pulse": self.in_mood_segment(chunk, stamp.abs_sec),
        }

    def _tone_for(self, chunk: str, verdict: str) -> dict:
        tone = self.mood.get(chunk, {}).get("tone")
        if isinstance(tone, dict) and tone.get("tone"):
            return {"tone": tone["tone"], "verbs": tone.get("verbs", [])}
        hint = _OLD_FALLBACK.get(verdict)
        return {"tone": hint["tone"], "verbs": hint["verbs"]} if hint else _FALLBACK_TONE


def report(timestamps: List[Timestamp], validator: Validator) -> List[dict]:
    """Annotate every timestamp with chunk and mood info."""
    return [{"stamp": st, "info": info} for st in timestamps if (info := validator.annotate(st))]


def print_report(rows: List[dict]) -> None:
    pulse_rows = [r for r in rows if r["info"]["in_pulse"]]
    print(f"Timestamps resolved to chunks: {len(rows)} | in pulse spans: {len(pulse_rows)}")
    if not pulse_rows:
        print("No timestamps fall inside a pulse segment — nothing to annotate.")
        return
    print("MOOD / TONE GUIDANCE (pulse spans):")
    for r in pulse_rows:
        info = r["info"]
        verbs = " / ".join(info["tone"]["verbs"]) or "(free choice)"
        print(f"  [chunk {info['chunk']}] {info['verdict']}: {info['tone']['tone']} — verbs: {verbs}")
        print(f"    {r['stamp'].raw}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timestamps", required=True)
    ap.add_argument("--mood", required=True)
    ap.add_argument("--livechat", default="")
    ap.add_argument("--index", default="")
    a = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mood = json.loads(Path(a.mood).read_text(encoding="utf-8"))
    windows = load_chunk_windows(a.livechat, a.index)
    validator = Validator(mood, windows)
    stamps = parse_timestamps(Path(a.timestamps))
    print_report(report(stamps, validator))
    return 0


if __name__ == "__main__":
    main()
