#!/usr/bin/env python3
"""Verify mood-bearing timestamps match the live-chat 555 pulse.

Catches the original bug: a chunk flagged MEME_PULSE (chat flooding 555) but the
timestamp written for it starts with a flat, factual verb — the streamer was
joking/bantering and the transcription flatlined it.

Thai laugh/banter/meme first-verbs (the verbs Step 5.5 maps to mood=fib);
a description is considered mood-correct if it opens with one of these.

Input:   --timestamps  timestamp list file (HH:MM:SS - [Tag] ...)
         --mood        mood_555.json from analyze_555.py
         --chunks      optional dir of livechat chunk logs with [HH:MM:SS] lines
                       (used to resolve which chunk a timestamp falls in when the
                       mood file alone is ambiguous)
Output:  prints flat/mismatched stamps for human review. Exit 0 always
         (report-only, does not auto-fix).

Usage:
  validate_mood.py --timestamps all_timestamps_redo_wrapped.txt --mood mood_555.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

TS_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})")
LAUGH_VERBS = [
    "แซว", "ล้อ", "แหย่", "โยก", "ขำ", "หัวเราะ", "ฮา", "เม้าท์", "เอ็นเตอร์เทน",
    "แซะ", "แดกดัน", "เสียดสี", "คอมเมนต์", "ติง", "ประชด", "หยอก",
]
# verbs that are factual -> flag when in a PULSE chunk
FLAT_VERBS = ["วิเคราะห์", "อธิบาย", "สรุป", "เล่า", "พูดถึง", "เปรียบเทียบ",
              "ทดลอง", "อ่าน", "สำรวจ", "เดิน", "เริ่ม", "แนะนำ", "บอก", "ดู", "เห็น"]

def to_sec(mm, ss):
    return int(mm) * 60 + int(ss)

def load_chunk_windows(livechat_dir, index_path=""):
    """chunk -> (start_sec_abs, end_sec_abs).

    Prefer livechat_index.json (aligned chunk boundaries); fall back to
    first/last [HH:MM:SS] seen in each chunk's livechat log."""
    windows = {}
    if index_path and Path(index_path).exists():
        idx = json.load(open(index_path, encoding="utf-8"))
        for chunk, info in idx.items():
            s = info["start"] if isinstance(info, dict) else info
            e = info["end"] if isinstance(info, dict) else info
            if isinstance(s, int) and isinstance(e, int):
                windows[chunk] = (s, e)
        return windows
    for p in sorted(Path(livechat_dir).glob("livechat_chunk_*.txt")):
        times = []
        for line in open(p, encoding="utf-8"):
            m = TS_RE.search(line)
            if m:
                h, mi, s = m.groups()
                times.append(int(h) * 3600 + int(mi) * 60 + int(s))
        if not times:
            continue
        cnum = p.stem.replace("livechat_chunk_", "chunk_")
        windows[cnum] = (min(times), max(times) + 1)
    return windows

def verb_head(desc):
    for v in LAUGH_VERBS:
        if re.search(re.escape(v), desc):
            return v
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timestamps", required=True)
    ap.add_argument("--mood", required=True)
    ap.add_argument("--livechat", default="")
    ap.add_argument("--index", default="")
    a = ap.parse_args()

    mood = json.load(open(a.mood, encoding="utf-8"))
    windows = load_chunk_windows(a.livechat, a.index) if a.livechat else {}

    def chunk_for(abs_sec):
        for c, (s, e) in windows.items():
            if s <= abs_sec < e:
                return c
        return None

    flagged = []
    total_pulse = 0
    for line in open(a.timestamps, encoding="utf-8"):
        line = line.strip()
        m = TS_RE.match(line)
        if not m or "]" not in line:
            continue
        h, mi, s = m.groups()
        ts = line.split("] ")[-1] if "] " in line else line
        abs_sec = int(h) * 3600 + int(mi) * 60 + int(s)
        chunk = chunk_for(abs_sec)
        v = mood.get(chunk, {}) if chunk else {}
        verdict = v.get("verdict", "")
        if verdict != "MEME_PULSE":
            continue
        total_pulse += 1
        if not verb_head(ts):
            flagged.append((chunk, line))

    print(f"MEME_PULSE spans reviewed: {total_pulse}")
    if not flagged:
        print("OK: every timestamp in a MEME_PULSE chunk opens with a laugh/banter verb.")
        return
    print(f"FLAT in pulse ({len(flagged)}):")
    for ch, line in flagged:
        print(f"  [chunk {ch}] {line}")

if __name__ == "__main__":
    main()