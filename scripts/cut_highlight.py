#!/usr/bin/env python3
# scripts/cut_highlight.py
import sys
import json
import argparse
import subprocess
from pathlib import Path

def run_cmd(cmd: list, desc: str):
    print(f"[*] {desc}", file=sys.stderr)
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan_json", help="Path to highlight_plan_abc123.json")
    ap.add_argument("--source", required=True, help="YouTube URL or local MP4 path")
    ap.add_argument("--output", help="Output MP4 file path (default: highlight_<video_id>.mp4)")
    ap.add_argument("--format", default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", help="yt-dlp format string")
    args = ap.parse_args()

    plan_path = Path(args.plan_json)
    if not plan_path.exists():
        print(f"ERROR: Plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(64)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    vid = plan["video_id"]
    scenes = plan["scenes"]
    if len(scenes) == 0:
        print("ERROR: No scenes found in plan", file=sys.stderr)
        sys.exit(1)
    out_path = Path(args.output) if args.output else plan_path.parent / f"highlight_{vid}.mp4"

    is_local = Path(args.source).exists()
    source_url = args.source

    tmp_files = []
    try:
        for sc in scenes:
            start = str(sc["start"])
            end = str(sc["end"])
            tmp_out = f"tmp_{vid}_scene_{sc['scene']}.mp4"
            tmp_files.append(tmp_out)
    
            if is_local:
                # Cut from local file
                cmd = ["ffmpeg", "-y", "-ss", start, "-to", end, "-i", source_url, "-c", "copy", tmp_out]
                run_cmd(cmd, f"Cutting scene {sc['scene']} from local file...")
            else:
                # Download section
                cmd = [
                    "yt-dlp",
                    "--download-sections", f"*{start}-{end}",
                    "-f", args.format,
                    "--merge-output-format", "mp4",
                    source_url,
                    "-o", tmp_out
                ]
                run_cmd(cmd, f"Downloading scene {sc['scene']}...")
    
        # Build concat filter
        # e.g., [0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]
        filter_str = "".join([f"[{i}:v][{i}:a]" for i in range(len(scenes))])
        filter_str += f"concat=n={len(scenes)}:v=1:a=1[outv][outa]"
    
        concat_cmd = ["ffmpeg", "-y"]
        for tmp in tmp_files:
            concat_cmd.extend(["-i", tmp])
        
        concat_cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart",
            str(out_path)
        ])
    
        run_cmd(concat_cmd, "Merging and re-encoding scenes...")
    
    finally:
        # Cleanup
        for tmp in tmp_files:
            p = Path(tmp)
            if p.exists():
                p.unlink()

    print(f"OK: Saved {out_path}")
    print(str(out_path)) # Just output the path to stdout for the AI
    sys.exit(0)

if __name__ == "__main__":
    main()
