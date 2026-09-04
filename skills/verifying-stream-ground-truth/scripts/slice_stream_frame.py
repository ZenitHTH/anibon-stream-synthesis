#!/usr/bin/env python3
"""
slice_stream_frame.py - Extract high-resolution ground-truth video frames from YouTube streams.

Uses yt-dlp's --download-sections to pull ONLY the targeted 1-3 minute window
bypassing full video downloads, then extracts an exact frame via ffmpeg.
"""

import argparse
import glob
import os
import subprocess
import sys


def parse_time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS or MM:SS or integer string to total seconds."""
    time_str = time_str.strip()
    if ":" not in time_str:
        return int(float(time_str))
    parts = [int(p) for p in time_str.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    raise ValueError(f"Invalid timestamp format: {time_str}")


def format_seconds_to_hms(sec: int) -> str:
    """Convert total seconds to HH:MM:SS."""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def slice_frame(
    url: str,
    timestamp: str,
    output_path: str,
    padding_sec: int = 30,
    browser: str = "chrome",
    keep_clip: bool = False,
) -> str:
    target_sec = parse_time_to_seconds(timestamp)
    start_sec = max(0, target_sec - padding_sec)
    end_sec = target_sec + padding_sec
    offset_in_clip = target_sec - start_sec

    start_hms = format_seconds_to_hms(start_sec)
    end_hms = format_seconds_to_hms(end_sec)

    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    clip_prefix = os.path.join(out_dir, f"temp_slice_{target_sec}")

    # 1. Download targeted section
    dl_cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "--download-sections", f"*{start_hms}-{end_hms}",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "-o", f"{clip_prefix}.%(ext)s",
        url,
    ]
    print(f"[*] Downloading targeted section ({start_hms} to {end_hms})...")
    res = subprocess.run(dl_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] yt-dlp error:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)

    # Find the downloaded file
    matches = glob.glob(f"{clip_prefix}*")
    matches = [m for m in matches if not m.endswith(".part")]
    if not matches:
        print(f"[!] No downloaded clip found matching {clip_prefix}*", file=sys.stderr)
        sys.exit(1)
    clip_file = matches[0]

    # 2. Extract frame with ffmpeg
    offset_hms = format_seconds_to_hms(offset_in_clip)
    ff_cmd = [
        "ffmpeg",
        "-ss", offset_hms,
        "-i", clip_file,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
        "-y",
    ]
    print(f"[*] Extracting frame at offset {offset_hms} -> {output_path}...")
    ff_res = subprocess.run(ff_cmd, capture_output=True, text=True)
    if ff_res.returncode != 0:
        print(f"[!] ffmpeg error:\n{ff_res.stderr}", file=sys.stderr)
        sys.exit(ff_res.returncode)

    # 3. Clean up temp clip if not requested
    if not keep_clip:
        for m in matches:
            try:
                os.remove(m)
            except OSError:
                pass

    print(f"[+] Frame successfully extracted: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract targeted high-res video frame from YouTube stream for visual ground-truth verification."
    )
    parser.add_argument("url", help="YouTube video URL or ID")
    parser.add_argument("timestamp", help="Target timestamp (HH:MM:SS or seconds)")
    parser.add_argument(
        "-o", "--output", default="ground_truth_frame.jpg", help="Output frame path"
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=30,
        help="Seconds of padding before/after timestamp (default: 30s)",
    )
    parser.add_argument(
        "--browser",
        default="chrome",
        help="Browser for yt-dlp cookies (default: chrome)",
    )
    parser.add_argument(
        "--keep-clip",
        action="store_true",
        help="Keep the downloaded video section file",
    )
    args = parser.parse_args()

    slice_frame(
        url=args.url,
        timestamp=args.timestamp,
        output_path=args.output,
        padding_sec=args.padding,
        browser=args.browser,
        keep_clip=args.keep_clip,
    )


if __name__ == "__main__":
    main()
