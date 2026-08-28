#!/usr/bin/env python3
"""
Align activity_timeline.json intervals to transcript chunk windows.
Emits per-chunk visual context files (activity_chunk_NN.txt) for subagent prompt injection.
"""

import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET


def align_intervals_to_chunk(
    intervals: list[dict], chunk_start_sec: float, chunk_end_sec: float
) -> str:
    """Format matching activity intervals for a given chunk's time window."""
    matching = []
    for item in intervals:
        i_start = item.get("start_sec", 0)
        i_end = item.get("end_sec", 0)
        # Check overlap
        if max(chunk_start_sec, i_start) < min(chunk_end_sec, i_end):
            matching.append(item)

    if not matching:
        return "No specific visual activity detected for this window."

    lines = []
    for m in matching:
        wb = m.get("webcam", {})
        speaker_present = wb.get("speaker_present", True)
        afk_note = " [⚠️ SPEAKER AWAY/AFK]" if not speaker_present else ""
        expr = wb.get("expression", "")
        expr_note = f" (Expression: {expr})" if expr and expr not in ("neutral", "away") else ""
        details = f" ({m.get('details', '')})" if m.get("details") else ""
        lines.append(
            f"- {m['start']} - {m['end']}: {m['app_or_game']} [{m['category']}]{afk_note}{details}{expr_note}"
        )
    return "\n".join(lines)


def get_chunk_time_bounds(chunk_file: str) -> tuple[float, float]:
    """Extract (start_sec, end_sec) from XML or JSON chunk."""
    if chunk_file.endswith(".xml"):
        try:
            tree = ET.parse(chunk_file)
            root = tree.getroot()
            starts = []
            ends = []
            for elem in root.findall(".//text"):
                s = float(elem.attrib.get("start", 0))
                d = float(elem.attrib.get("dur", 0))
                starts.append(s)
                ends.append(s + d)
            if starts:
                return min(starts), max(ends)
        except Exception:
            pass
    elif chunk_file.endswith(".json"):
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                s = min(float(item.get("start", 0)) for item in data)
                e = max(float(item.get("start", 0)) + float(item.get("duration", 0)) for item in data)
                return s, e
        except Exception:
            pass

    # Fallback from chunk filename index: chunk_01 -> assume 5 min (300s) default
    match = re.search(r"chunk_(\d+)", os.path.basename(chunk_file))
    if match:
        idx = int(match.group(1))
        # 1-indexed
        return (idx - 1) * 300.0, idx * 300.0
    return 0.0, 300.0


def process_all_chunks(timeline_path: str, chunks_dir: str, out_dir: str) -> None:
    """Read activity_timeline.json and generate activity_chunk_NN.txt for all chunks."""
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(timeline_path):
        print(f"Warning: Timeline file {timeline_path} not found.", file=sys.stderr)
        return

    with open(timeline_path, "r", encoding="utf-8") as f:
        intervals = json.load(f)

    chunk_files = sorted(
        glob.glob(os.path.join(chunks_dir, "chunk_*.xml"))
        + glob.glob(os.path.join(chunks_dir, "chunk_*.json"))
    )

    for cf in chunk_files:
        base_name = os.path.splitext(os.path.basename(cf))[0]
        # Normalize to chunk_NN
        m = re.search(r"chunk_\d+", base_name)
        norm_name = m.group(0) if m else base_name
        start_sec, end_sec = get_chunk_time_bounds(cf)
        aligned_text = align_intervals_to_chunk(intervals, start_sec, end_sec)

        out_path = os.path.join(out_dir, f"activity_{norm_name}.txt")
        with open(out_path, "w", encoding="utf-8") as out_f:
            out_f.write(aligned_text + "\n")

    print(f"Aligned {len(chunk_files)} chunks into {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Align activity timeline to transcript chunks")
    parser.add_argument("--timeline", required=True, help="Path to activity_timeline.json")
    parser.add_argument("--chunks", required=True, help="Directory containing transcript chunks")
    parser.add_argument("-o", "--output-dir", required=True, help="Output directory for activity_chunk_NN.txt files")

    args = parser.parse_args()
    process_all_chunks(args.timeline, args.chunks, args.output_dir)


if __name__ == "__main__":
    main()
