#!/usr/bin/env python3
"""Verify mood-bearing timestamps match the live-chat 555 pulse.

Companion to analyze_555.py (Stage 4 of the "Dual-Side Thai Stream & Chat Mood
Detection" design doc). analyze_555.py emits mood_555.json verdicts; this script
checks the generated timestamps actually honour those verdicts.

Catches the original bug: a chunk flagged MEME_PULSE (chat flooding 555) but the
timestamp written for it starts with a flat, factual verb — the streamer was
joking/bantering and the transcription flatlined it.

Thai laugh/banter/meme first-verbs (the verbs Step 5.5 maps to mood=fib);
a description is considered mood-correct if it opens with one of these.

Input:   --timestamps  timestamp list file (HH:MM:SS - [Tag] ...)
         --mood        mood_555.json from analyze_555.py
         --livechat    optional dir of livechat chunk logs with [HH:MM:SS] lines
                       (used to resolve which chunk a timestamp falls in when the
                       mood file alone is ambiguous)
         --index       optional livechat_index.json (preferred chunk boundaries)
Output:  prints flat/mismatched stamps for human review. Exit 0 always
         (report-only, does not auto-fix).

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
# verbs that open a timestamp: presence of any ==> mood-correct in a PULSE chunk
LAUGH_VERBS = [
    "แซว", "ล้อ", "แหย่", "โยก", "ขำ", "หัวเราะ", "ฮา", "เม้าท์", "เอ็นเตอร์เทน",
    "แซะ", "แดกดัน", "เสียดสี", "คอมเมนต์", "ติง", "ประชด", "หยอก",
]
# verbs that are factual -> flag when in a PULSE chunk
FLAT_VERBS = ["วิเคราะห์", "อธิบาย", "สรุป", "เล่า", "พูดถึง", "เปรียบเทียบ",
              "ทดลอง", "อ่าน", "สำรวจ", "เดิน", "เริ่ม", "แนะนำ", "บอก", "ดู", "เห็น"]


@dataclass(frozen=True)
class Config:
    """Tunable validation behaviour."""
    # only treat these verdicts as laughter spans that must open with a laugh verb
    pulse_verdicts: Tuple[str, ...] = ("MEME_PULSE",)


@dataclass
class Timestamp:
    """A parsed timestamp line."""
    abs_sec: int
    desc: str
    raw: str


def to_abs_sec(hh: str, mm: str, ss: str) -> int:
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


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


def verb_head(desc: str) -> Optional[str]:
    """First laugh verb found in the description, else None."""
    for v in LAUGH_VERBS:
        if re.search(re.escape(v), desc):
            return v
    return None


class Validator:
    """Resolves timestamps to chunks and checks them against mood verdicts."""

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

    def in_funny_segment(self, chunk: str, abs_sec: int) -> bool:
        """True if the timestamp lands in a 'funny' segment of the chunk.

        Falls back to True (whole chunk counts) when segments are absent so old
        mood files keep the current behavior."""
        segs = self.mood.get(chunk, {}).get("segments")
        if not segs:
            return True
        for s in segs:
            if self._seg_secs(s["start"]) <= abs_sec < self._seg_secs(s["end"]):
                return s["mood"] == "funny"
        return False

    def check(self, stamp: Timestamp) -> Optional[str]:
        """Return the chunk id if this stamp is mood-mismatched, else None."""
        chunk = self.chunk_for(stamp.abs_sec)
        verdict = self.mood.get(chunk, {}).get("verdict", "") if chunk else ""
        if verdict not in self.cfg.pulse_verdicts:
            return None
        if not self.in_funny_segment(chunk, stamp.abs_sec):
            return None
        if verb_head(stamp.desc):
            return None
        return chunk


def report(timestamps: List[Timestamp], validator: Validator) -> Tuple[int, List[Tuple[str, str]]]:
    """Run the check and collect (chunk, raw_line) for every mismatch."""
    total_pulse = 0
    flagged: List[Tuple[str, str]] = []
    for st in timestamps:
        chunk = validator.chunk_for(st.abs_sec)
        verdict = validator.mood.get(chunk, {}).get("verdict", "") if chunk else ""
        if verdict not in validator.cfg.pulse_verdicts:
            continue
        total_pulse += 1
        bad = validator.check(st)
        if bad:
            flagged.append((bad, st.raw))
    return total_pulse, flagged


def print_report(total_pulse: int, flagged: List[Tuple[str, str]]) -> None:
    print(f"MEME_PULSE spans reviewed: {total_pulse}")
    if not flagged:
        print("OK: every timestamp in a MEME_PULSE chunk opens with a laugh/banter verb.")
        return
    print(f"FLAT in pulse ({len(flagged)}):")
    for chunk, line in flagged:
        print(f"  [chunk {chunk}] {line}")


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
    total_pulse, flagged = report(stamps, validator)
    print_report(total_pulse, flagged)
    return 0


if __name__ == "__main__":
    main()