#!/usr/bin/env python3
"""
Extract continuous activity and webcam timeline from storyboard frames.
Merges frame-by-frame visual classifications into activity_timeline.json.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys


def format_timestamp(seconds: int | float) -> str:
    """Format seconds into HH:MM:SS string."""
    sec = int(seconds)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_timestamp_to_sec(ts: str) -> int:
    """Parse HH:MM:SS or MM:SS to total seconds."""
    parts = [int(p) for p in ts.strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return int(parts[0])


def parse_vision_response_json(text: str) -> list[dict]:
    """Extract and parse JSON array from model response text with or without code fences."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "frames" in data:
            return data["frames"]
        return [data]
    except Exception as e:
        print(f"Warning: Failed to parse vision JSON: {e}", file=sys.stderr)
        return []


def merge_frame_classifications(frames: list[dict], step_sec: int = 60) -> list[dict]:
    """
    Merge raw sequential frame classifications into continuous activity intervals.
    Splits when app/game changes, category changes, or speaker presence changes (AFK).
    """
    if not frames:
        return []

    # Sort by second/timestamp if available
    sorted_frames = []
    for f in frames:
        sec = f.get("sec")
        if sec is None and "timestamp" in f:
            sec = parse_timestamp_to_sec(f["timestamp"])
        sorted_frames.append({**f, "sec": sec if sec is not None else 0})
    sorted_frames.sort(key=lambda x: x["sec"])

    intervals = []
    current = None

    for f in sorted_frames:
        sec = f["sec"]
        app = f.get("app_or_game", "Unknown")
        cat = f.get("category", "Other")
        state = f.get("state", "")
        wb = f.get("webcam", {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"})
        speaker_present = wb.get("speaker_present", True)

        # Check if current interval continues
        if (
            current is not None
            and current["app_or_game"] == app
            and current["category"] == cat
            and current["webcam"]["speaker_present"] == speaker_present
        ):
            current["end_sec"] = sec + step_sec
            current["end"] = format_timestamp(current["end_sec"])
            if state and state not in current["states"]:
                current["states"].append(state)
        else:
            if current is not None:
                intervals.append(
                    {
                        "start": current["start"],
                        "end": current["end"],
                        "start_sec": current["start_sec"],
                        "end_sec": current["end_sec"],
                        "app_or_game": current["app_or_game"],
                        "category": current["category"],
                        "details": "; ".join(current["states"]) or current["app_or_game"],
                        "webcam": current["webcam"],
                    }
                )
            current = {
                "start": format_timestamp(sec),
                "end": format_timestamp(sec + step_sec),
                "start_sec": sec,
                "end_sec": sec + step_sec,
                "app_or_game": app,
                "category": cat,
                "states": [state] if state else [],
                "webcam": wb,
            }

    if current is not None:
        intervals.append(
            {
                "start": current["start"],
                "end": current["end"],
                "start_sec": current["start_sec"],
                "end_sec": current["end_sec"],
                "app_or_game": current["app_or_game"],
                "category": current["category"],
                "details": "; ".join(current["states"]) or current["app_or_game"],
                "webcam": current["webcam"],
            }
        )

    return intervals


def main():
    parser = argparse.ArgumentParser(description="Extract activity and webcam timeline from storyboard frames")
    parser.add_argument("--raw-json", help="Path to raw frame classifications JSON file")
    parser.add_argument("--slides-dir", help="Directory containing unpacked storyboard slides")
    parser.add_argument("--step-sec", type=int, default=60, help="Sampling interval in seconds (default 60)")
    parser.add_argument("--duration", type=float, default=0.0, help="Total stream duration in seconds")
    parser.add_argument("-o", "--output", default="activity_timeline.json", help="Output JSON path")

    args = parser.parse_args()

    raw_frames = []
    if args.raw_json and os.path.exists(args.raw_json):
        with open(args.raw_json, "r", encoding="utf-8") as f:
            raw_frames = json.load(f)

    merged = merge_frame_classifications(raw_frames, step_sec=args.step_sec)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(merged)} activity intervals -> {args.output}")


if __name__ == "__main__":
    main()
