#!/usr/bin/env python3
"""Detect Thai-laugh / meme pulses from aligned LiveChat logs.

Thai watchers mark laughter with "555..." (and the "5" family), "xD", "haha",
"ฮา", "ขำ", "555555...". A pulse = clustered burst of these markers within a
short window. This is the only reliable laugh proxy when the autotranscript
cannot hear the streamer actually laughing (audio unclear / no laugh glyph).

This script is downstream of align_live_chat.py: it reads per-chunk LiveChat
logs (the same files the timestamper subagents read) and emits a JSON verdict
that the subagent prompt must weight when writing mood-bearing descriptions.

Input:   --livechat  dir of per-chunk chat logs (livechat/livechat_chunk_*.txt)
         --index     livechat_index.json  (chunk name -> file), optional
         --out       output json path
Output:  JSON dict chunk -> {density, n_markers, n_messages, peak_windows,
                             mood, verdict}

Heuristic verdicts:
  - QUIET        low chat, no burst            -> neutral mood, normal sampling
  - MEME_PULSE   strong burst (count >= pulse) -> funny/meme mood: laugh firstverb
  - WARM         some markers, no burst        -> light banter, optional laugh verb

Peak windows are computed by sliding a W seconds bucket over the sorted message
timestamps and finding buckets with the most laugh markers.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LAUGH_RE = re.compile(r"(5{3,}|[xX][dD]{1,}|haha+|ฮา+|ขำ+|\blol\b|\bhaha\b)", re.IGNORECASE)
TS_RE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")

# markers needed in one bucket to call a MEME_PULSE
PULSE_THRESHOLD = 12
# per-chunk minimum markers for the "hot" flag regardless of bucket
HOT_MIN = 14
# for low-message chunks (< LOW_MSG) absolute counts understate bursts:
# use marker density >= LOW_MSG_DENSITY as the pulse signal instead
LOW_MSG = 100
LOW_MSG_DENSITY = 0.20
# bucket width for peak-window detection (seconds)
BUCKET = 90
# how many high buckets can be reported
MAX_PEAKS = 4


def to_sec(hh, mm, ss):
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


def parse_chat(path: Path):
    """Return ([sec,...] marker message times, [sec,...] all message times)."""
    marker_secs, all_secs = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = TS_RE.search(line)
            if not m:
                continue
            sec = to_sec(*m.groups())
            all_secs.append(sec)
            if LAUGH_RE.search(line):
                marker_secs.append(sec)
    return marker_secs, all_secs


def find_peaks(marker_secs, bucket=BUCKET):
    """Return [(window_start_sec, window_end_sec, count), ...] descending count."""
    if not marker_secs:
        return []
    # bucket keyed by floor(sec/bucket)
    buckets = defaultdict(list)
    for s in marker_secs:
        buckets[s // bucket].append(s)
    rows = []
    for k, times in buckets.items():
        rows.append((k * bucket, k * bucket + bucket, len(times)))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:MAX_PEAKS]


def fmt_ts(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def analyze(livechat_dir, index_path, out_path):
    index = {}
    if index_path and Path(index_path).exists():
        index = json.load(open(index_path, encoding="utf-8"))
    files = sorted(Path(livechat_dir).glob("livechat_chunk_*.txt"))
    result = {}
    for f in files:
        chunk = None
        for name, info in index.items():
            rel = info["file"] if isinstance(info, dict) else info
            if Path(rel).name == f.name:
                chunk = name
                break
        if chunk is None:
            chunk = f.stem.replace("livechat_chunk_", "chunk_")
        marker_secs, all_secs = parse_chat(f)
        n_markers = len(marker_secs)
        n_msgs = len(all_secs)
        density = n_markers / n_msgs if n_msgs else 0.0
        peaks = find_peaks(marker_secs)
        peak_thresh = peaks[0][2] if peaks else 0
        low_msg_pulse = n_msgs < LOW_MSG and density >= LOW_MSG_DENSITY
        has_peak_burst = peak_thresh >= PULSE_THRESHOLD or low_msg_pulse
        if has_peak_burst:
            mood = "funny"
            verdict = "MEME_PULSE"
        elif n_markers >= HOT_MIN:
            mood = "warm"
            verdict = "HOT"
        elif n_markers >= 1:
            mood = "warm"
            verdict = "WARM"
        else:
            mood = "neutral"
            verdict = "QUIET"
        result[chunk] = {
            "density": round(density, 3),
            "n_markers": n_markers,
            "n_messages": n_msgs,
            "pulse": bool(has_peak_burst),
            "verdict": verdict,
            "mood": mood,
            "peak_windows": [{"start": fmt_ts(a), "end": fmt_ts(b), "count": c}
                             for a, b, c in peaks if c >= PULSE_THRESHOLD],
        }
    json.dump(result, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # report
    print(f"chunks analyzed: {len(result)}")
    memes = [k for k, v in result.items() if v["verdict"] == "MEME_PULSE"]
    print(f"MEME_PULSE chunks ({len(memes)}): {sorted(memes, key=lambda c:int(c.split('_')[1]))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--livechat", required=True)
    ap.add_argument("--index", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    analyze(a.livechat, a.index, a.out)