#!/usr/bin/env python3
"""
enrich_uncertain_with_vision.py

Scans recovered_transcript_bfs.json for items marked [?] uncertain,
extracts video frames at their exact timestamps using ffmpeg, and creates
a visual inspection index report for human/vision-model review.
"""

import json
import argparse
import subprocess
from pathlib import Path

def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

from concurrent.futures import ThreadPoolExecutor

def _extract_single_frame(args_tuple):
    idx, item, video_path, out_dir = args_tuple
    start_s = item.get("start", 0.0)
    ts_str = item.get("timestamp", _fmt_ts(start_s))
    safe_ts = ts_str.replace(":", "-")
    frame_name = f"frame_{idx:03d}_{safe_ts}.jpg"
    frame_path = out_dir / frame_name

    if not frame_path.exists() and video_path.exists():
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(frame_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    item_copy = dict(item)
    item_copy["frame_path"] = str(frame_path)
    item_copy["frame_name"] = frame_name
    return item_copy

def extract_frames(json_path: Path, video_path: Path, out_dir: Path, workers: int = 4) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    uncertain_items = [x for x in data if x.get("uncertain") or "[?]" in x.get("text", "")]
    print(f"[vision] Found {len(uncertain_items)} uncertain [?] items. Extracting frames using {workers} workers...")

    tasks = [(idx, item, video_path, out_dir) for idx, item in enumerate(uncertain_items)]
    if tasks:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            extracted = list(executor.map(_extract_single_frame, tasks))
    else:
        extracted = []

    print(f"[vision] Extracted {len(extracted)} frames to {out_dir}")
    return extracted


def generate_report(extracted: list, report_path: Path):
    lines = [
        "# Uncertain [?] Visual Context Inspection Report\n",
        f"Total uncertain items: **{len(extracted)}**\n\n",
        "| # | Timestamp | Audio Text Attempt | Frame Preview |\n",
        "|---|---|---|---|\n"
    ]
    for idx, item in enumerate(extracted):
        ts = item.get("timestamp", "00:00:00")
        text = item.get("text", "").replace("|", "\\|")
        frame_name = item.get("frame_name", "")
        lines.append(f"| {idx+1} | `{ts}` | {text} | ![{frame_name}]({frame_name}) |\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"[vision] Report generated: {report_path}")

def main():
    ap = argparse.ArgumentParser(description="Extract video frames for [?] uncertain transcript items.")
    ap.add_argument("transcript_json", help="Path to recovered_transcript_bfs.json")
    ap.add_argument("video_file", help="Path to input MP4/MKV video file")
    ap.add_argument("-o", "--output-dir", default="frames_uncertain", help="Directory to save extracted frames")
    args = ap.parse_args()

    json_path = Path(args.transcript_json)
    video_path = Path(args.video_file)
    out_dir = Path(args.output_dir)

    extracted = extract_frames(json_path, video_path, out_dir)
    generate_report(extracted, out_dir / "README.md")

if __name__ == "__main__":
    main()
