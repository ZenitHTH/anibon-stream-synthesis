#!/usr/bin/env python3
# scripts/plan_highlight.py
# Parses a livestream-scene-selection markdown file and writes a JSON cut plan.
# AI passes only file paths — never reads the JSON output.
#
# Usage:
#   python3 plan_highlight.py scene_selection.md --video-id abc123 --source URL
#   python3 plan_highlight.py scene_selection.md --video-id abc123  # source optional

import sys
import re
import json
import argparse
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Business logic — no argparse here, easy to unit-test
# ---------------------------------------------------------------------------

_TS_RE = re.compile(
    r"\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]"  # [HH:MM:SS - HH:MM:SS]
    r"`?"                                                          # optional closing backtick
    r"(?:\s*-\s*([^\n]+))?"                                       # optional " - <anything on same line>"
)
_BOLD_RE = re.compile(r"\*{1,2}([^\*]+)\*{1,2}")


def _to_seconds(ts: str) -> int:
    parts = ts.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        raise ValueError(f"Unrecognised timestamp: {ts!r}")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _to_hhmmss(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_scenes(text: str) -> list[dict]:
    """Extract scenes from scene-selection markdown. Returns list of scene dicts."""
    scenes = []
    for i, m in enumerate(_TS_RE.finditer(text), start=1):
        start, end, raw_label = m.group(1), m.group(2), m.group(3)
        if raw_label:
            # Strip bold (**text**) or italic (*text*) markers, then backticks and whitespace
            bold_m = _BOLD_RE.search(raw_label)
            label = bold_m.group(1).strip() if bold_m else raw_label.strip("`* \t")
        else:
            label = f"Scene {i}"
        start_s = _to_seconds(start)
        end_s = _to_seconds(end)
        scenes.append({
            "scene": i,
            "start": _to_hhmmss(start_s),
            "end": _to_hhmmss(end_s),
            "duration_seconds": end_s - start_s,
            "label": label,
        })
    return scenes


def validate_scenes(scenes: list[dict]) -> list[str]:
    """Return list of error strings. Empty = valid."""
    errors = []
    for sc in scenes:
        s, e = _to_seconds(sc["start"]), _to_seconds(sc["end"])
        if e <= s:
            errors.append(f"Scene {sc['scene']}: end ({sc['end']}) <= start ({sc['start']})")
    # Check overlaps (scenes are in document order, not necessarily time order)
    sorted_sc = sorted(scenes, key=lambda x: _to_seconds(x["start"]))
    for a, b in zip(sorted_sc, sorted_sc[1:]):
        a_end = _to_seconds(a["end"])
        b_start = _to_seconds(b["start"])
        if a_end > b_start:
            errors.append(
                f"Overlap: scene {a['scene']} ({a['start']}-{a['end']}) "
                f"overlaps scene {b['scene']} ({b['start']}-{b['end']})"
            )
    return errors


def build_plan(scenes: list[dict], video_id: str, source_url: str | None) -> dict:
    total = sum(sc["duration_seconds"] for sc in scenes)
    return {
        "video_id": video_id,
        "source_url": source_url,
        "total_expected_duration_seconds": total,
        "scenes": scenes,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Parse a scene-selection markdown file and write a JSON highlight plan."
    )
    ap.add_argument("markdown", help="Path to the livestream-scene-selection .md file")
    ap.add_argument("--video-id", required=True, help="YouTube video ID (e.g. abc123XYZ)")
    ap.add_argument("--source", default=None, help="YouTube URL or local file path (optional)")
    ap.add_argument("--output-dir", default=None,
                    help="Directory to write JSON plan (default: same dir as markdown file)")
    args = ap.parse_args()

    md_path = Path(args.markdown)
    if not md_path.exists():
        print(f"ERROR: markdown file not found: {md_path}", file=sys.stderr)
        return 64

    text = md_path.read_text(encoding="utf-8")
    scenes = parse_scenes(text)

    if not scenes:
        print("ERROR: no timestamp ranges found in markdown. "
              "Expected format: [HH:MM:SS - HH:MM:SS]", file=sys.stderr)
        return 64

    errors = validate_scenes(scenes)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 64

    plan = build_plan(scenes, args.video_id, args.source)

    out_dir = Path(args.output_dir) if args.output_dir else md_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"highlight_plan_{args.video_id}.json"
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    total_s = plan["total_expected_duration_seconds"]

    # Estimate download time if source is a URL
    if args.source and args.source.startswith("http"):
        print("Fetching video metadata from YouTube to estimate download size...", file=sys.stderr)
        try:
            res = subprocess.run(["yt-dlp", "--dump-json", args.source], capture_output=True, text=True, check=True)
            meta = json.loads(res.stdout)
            video_duration = meta.get("duration")
            filesize = meta.get("filesize") or meta.get("filesize_approx")
            if video_duration and filesize:
                ratio = total_s / video_duration
                est_bytes = filesize * ratio
                est_mb = est_bytes / (1024 * 1024)
                est_seconds = est_mb / 5.0  # Assume conservative 5 MB/s download speed

                print(f"---", file=sys.stderr)
                print(f"Estimated Highlight Size: {est_mb:.1f} MB", file=sys.stderr)
                print(f"Estimated Download Time (at 5 MB/s): {est_seconds:.1f} seconds", file=sys.stderr)
                if est_seconds > 1800:
                    print("WARNING: Estimated download time is over 30 minutes! Consider lowering the resolution.", file=sys.stderr)
                print(f"---", file=sys.stderr)
        except Exception as e:
            print(f"Note: Could not estimate filesize from YouTube ({e})", file=sys.stderr)

    print(
        f"OK: {len(scenes)} scenes | "
        f"total {_to_hhmmss(total_s)} ({total_s}s) | "
        f"plan written to {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
