#!/usr/bin/env python3
"""Label timestamps with their chunk's mood + tone guidance (report-only).

Companion to analyze_555.py (Stage 4 of the "Dual-Side Thai Stream & Chat Mood
Detection" design doc). analyze_555.py emits mood_555.json verdicts per chunk;
this script annotates each generated timestamp with the chunk's mood + the Thai
tone-hint verbs the AI MAY draw from.

Deliberately guidance-only: it never rejects a verb. The AI timestamp-writer
picks its own verbs from the situation + the mood's suggested verbs. The tool
only reminds the human which pulse spans carried which mood, so the AI's verb
creativity is never constrained by a programmed whitelist.

Input:   --timestamps  timestamp list file (HH:MM:SS - [Tag] ...)
         --mood        mood_555.json from analyze_555.py
         --livechat    optional dir of livechat chunk logs with [HH:MM:SS] lines
                       (used to resolve which chunk a timestamp falls in when the
                       mood file alone is ambiguous)
         --index       optional livechat_index.json (preferred chunk boundaries)
Output:  prints each pulse-span timestamp with its mood + tone hint verbs.

Usage:
  validate_mood.py --timestamps out_stamps.txt --mood mood_555.json \
                   --livechat ./livechat --index livechat_index.json
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TS_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})")

_FALLBACK_TONE = {"tone": "เขียนตามอารมณ์ของเหตุการณ์", "verbs": ["แซว", "วิเคราะห์", "สรุป"]}

# core mood "tone" field already present in mood_555.json per chunk (from
# analyze_555.TONE_HINTS). validate_mood consumes it directly; this inline table
# is a final fallback for old mood files that predate the tone field.
_OLD_FALLBACK = {
    "MEME_PULSE": {"tone": "ตลกปั่น ๆ แซวขำ ๆ", "verbs": ["แซว", "ล้อ", "ขำ", "ปั่น"]},
    "WARM": {"tone": "บรรยากาศเป็นกันเอง คุยเพลิน ๆ", "verbs": ["แซว", "เม้าท์", "เล่า"]},
    "HOT": {"tone": "บรรยากาศคึกคัก", "verbs": ["กระตุ้น", "ปั่น"]},
    "QUIET": {"tone": "คุยสบาย ๆ เลือกคำอิสระ", "verbs": ["พูดคุย", "วิเคราะห์"]},
}


@dataclass(frozen=True)
class Config:
    """No tunable rejection — validation is guidance-only."""


def to_abs_sec(hh: str, mm: str, ss: str) -> int:
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


@dataclass
class Timestamp:
    """A parsed timestamp line."""
    abs_sec: int
    desc: str
    raw: str


def load_chunk_windows(livechat_dir: str, index_path: str = "") -> Dict[str, Tuple[int, int]]:
    """chunk -> (start_sec_abs, end_sec_abs).

    Prefer livechat_index.json (aligned chunk boundaries); fall back to
    first/last [HH:MM:SS] seen in each chunk's livechat log."""
    windows: Dict[str, Tuple[int, int]] = {}
    if index_path and Path(index_path).exists():
        idx = json.load(open(index_path, encoding="utf-8"))
        for chunk, info in idx.items():
            if isinstance(info, dict) and isinstance(info.get("start"), int) \
                    and isinstance(info.get("end"), int):
                windows[chunk] = (info["start"], info["end"])
        return windows
    for p in sorted(Path(livechat_dir).glob("livechat_chunk_*.txt")):
        times = []
        for line in open(p, encoding="utf-8"):
            m = TS_RE.search(line)
            if m:
                times.append(to_abs_sec(*m.groups()))
        if not times:
            continue
        cnum = p.stem.replace("livechat_chunk_", "chunk_")
        windows[cnum] = (min(times), max(times) + 1)
    return windows


def parse_timestamps(path: Path) -> List[Timestamp]:
    """Extract (time, description) records from the timestamp file."""
    stamps: List[Timestamp] = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = TS_RE.match(line)
        if not m or "]" not in line:
            continue
        desc = line.split("] ")[-1] if "] " in line else line
        stamps.append(Timestamp(
            abs_sec=to_abs_sec(*m.groups()),
            desc=desc,
            raw=line,
        ))
    return stamps


class Validator:
    """Resolves timestamps to chunks and annotates them with mood + tone."""

    def __init__(self, mood: dict, windows: Dict[str, Tuple[int, int]],
                 cfg: Optional[Config] = None):
        self.mood = mood
        self.windows = windows
        self.cfg = cfg or Config()

    def chunk_for(self, abs_sec: int) -> Optional[str]:
        for c, (s, e) in self.windows.items():
            if s <= abs_sec < e:
                return c
        return None

    def _seg_secs(self, seg_time: str) -> int:
        h, m, s = seg_time.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    def in_mood_segment(self, chunk: str, abs_sec: int) -> bool:
        """True if the timestamp lands in a non-natural (pulse) segment of chunk.

        Falls back to True (whole chunk counts) when segments are absent so old
        mood files keep the current behavior."""
        segs = self.mood.get(chunk, {}).get("segments")
        if not segs:
            return True
        for s in segs:
            if self._seg_secs(s["start"]) <= abs_sec < self._seg_secs(s["end"]):
                return s["mood"] != "natural"
        return False

    def annotate(self, stamp: Timestamp) -> Optional[dict]:
        """Return {chunk, verdict, tone, verbs, in_pulse} for a stamp, else None
        when the timestamp can't be resolved to a known chunk."""
        chunk = self.chunk_for(stamp.abs_sec)
        if not chunk or chunk not in self.mood:
            return None
        rec = self.mood[chunk]
        verdict = rec.get("verdict", "")
        return {
            "chunk": chunk,
            "verdict": verdict,
            "tone": self._tone_for(chunk, verdict),
            "in_pulse": self.in_mood_segment(chunk, stamp.abs_sec),
        }

    def _tone_for(self, chunk: str, verdict: str) -> dict:
        """Tone guidance for a chunk: prefer the per-chunk tone field, fall back
        to a verdict-keyed hint for old mood files, else generic."""
        rec = self.mood.get(chunk, {})
        tone = rec.get("tone")
        if isinstance(tone, dict) and tone.get("tone"):
            return {"tone": tone["tone"], "verbs": tone.get("verbs", [])}
        hint = _OLD_FALLBACK.get(verdict)
        if hint:
            return {"tone": hint["tone"], "verbs": hint["verbs"]}
        return {"tone": _FALLBACK_TONE["tone"], "verbs": _FALLBACK_TONE["verbs"]}


def report(timestamps: List[Timestamp], validator: Validator) -> List[dict]:
    """Annotate every timestamp; pulse-span ones get a mood + tone hint."""
    rows = []
    for st in timestamps:
        info = validator.annotate(st)
        if not info:
            continue
        rows.append({"stamp": st, "info": info})
    return rows


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
        print(f"  [chunk {info['chunk']}] {info['verdict']}: {info['tone']['tone']} "
              f"— verbs: {verbs}")
        print(f"    {r['stamp'].raw}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timestamps", required=True)
    ap.add_argument("--mood", required=True)
    ap.add_argument("--livechat", default="")
    ap.add_argument("--index", default="")
    a = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    mood = json.load(open(a.mood, encoding="utf-8"))
    windows = load_chunk_windows(a.livechat, a.index) if a.livechat else {}

    validator = Validator(mood, windows)
    stamps = parse_timestamps(Path(a.timestamps))
    rows = report(stamps, validator)
    print_report(rows)
    return 0


if __name__ == "__main__":
    main()