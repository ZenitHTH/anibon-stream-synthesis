#!/usr/bin/env python3
"""
Extract On-Screen Burned-In LiveChat via Vision Proxy (Gemini 3.6 Flash).

Crops the burned-in chat region from video slices, runs vision OCR with channel
emote mapping via `agy`, deduplicates scrolling messages, and outputs raw event feeds.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat

# Resilient imports for module or standalone script execution
try:
    from skills.anibon_livechat_analysis.scripts.visual_chat_crop import (
        get_chat_roi,
        build_crop_filter,
    )
    from skills.anibon_livechat_analysis.scripts.visual_chat_dedup import (
        deduplicate_frames_messages,
        sec_to_hhmmss,
    )
except (ImportError, ModuleNotFoundError):
    try:
        from visual_chat_crop import get_chat_roi, build_crop_filter
        from visual_chat_dedup import deduplicate_frames_messages, sec_to_hhmmss
    except (ImportError, ModuleNotFoundError):
        _scripts_dir = Path(__file__).resolve().parent
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))
        from visual_chat_crop import get_chat_roi, build_crop_filter
        from visual_chat_dedup import deduplicate_frames_messages, sec_to_hhmmss


VISION_PROMPT = """You are an expert OCR and YouTube livestream chat transcript parser.
Analyze the cropped live chat images from an Anibon stream in this directory.

1. Extract all visible chat messages from top to bottom.
2. For each message, extract:
   - Author username (e.g. @user)
   - Message text exactly as written in Thai/English.
   - Any SuperChat donation amount if highlighted as a paid message.
3. Map rendered picture emotes to standard channel emote tags using this reference:
   - Yellow crying face with glasses: :_CunnyBoat:
   - Monkey pose Boat: :_MonkeyBoat:
   - Pushing glasses finger up nerd face: :_Nerd:
   - Grinning mischievous face: :_Grind:
   - Standing fish meme: :_Ripfish:
   - Plush doll on bed: :_noname:
   - Squinting confused face: :_What:
   - Wide eyes Poggers: :_WOW:
   - Head back bliss face: :_Ahh:
   - Deadpan flat face: :_Meh:
   - Holding orange: :_BoatSOM:
   - Camo military uniform: :_Tahaan:
   - Yellow shirt polite smile: :_KonDee:
   - Sipping tea cup: :_Tea:
   - Blue smiling face: :face-blue-smiling:
   - Pink waving hand: :hand-pink_waving:

Output JSON format:
[
  {
    "frame": "chat_000.jpg",
    "messages": [
      {"author": "@username", "text": "message content with :_Emote: tags", "superchat": null}
    ]
  }
]
Or if only a single image or direct list:
[
  {"author": "@username", "text": "message content with :_Emote: tags", "superchat": null}
]
"""


def parse_timestamp_str(ts: str) -> int:
    """Parse HH:MM:SS, MM:SS, or SS string to total seconds."""
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 1:
        return int(parts[0])
    raise ValueError(f"Invalid timestamp format: {ts}")


def parse_time_range(range_str: str) -> tuple[int, int]:
    """Parse a time range string like '00:10:00-00:12:30' into (start_sec, end_sec)."""
    if "-" not in range_str:
        raise ValueError(f"Time range must contain '-': {range_str}")
    start_str, end_str = range_str.split("-", 1)
    start_sec = parse_timestamp_str(start_str)
    end_sec = parse_timestamp_str(end_str)
    if start_sec > end_sec:
        raise ValueError(f"Start time ({start_sec}s) cannot be greater than end time ({end_sec}s)")
    return start_sec, end_sec


def parse_gemini_chat_json(raw_text: str) -> list[dict]:
    """Extract and parse JSON array or object from Gemini response text."""
    cleaned = raw_text.strip()
    if not cleaned:
        return []

    # Check for markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    candidate = fence_match.group(1).strip() if fence_match else cleaned

    try:
        data = json.loads(candidate)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if "messages" in data and isinstance(data["messages"], list):
                return data["messages"]
            return [data]
    except Exception:
        pass

    # Fallback: search for first [ ... ] array
    array_match = re.search(r"(\[[\s\S]*\])", candidate)
    if array_match:
        try:
            data = json.loads(array_match.group(1))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    return []


def probe_chat_layout_from_image(image: Image.Image) -> str:
    """Analyze a PIL Image to determine whether chat is in bottom-right or left ROI."""
    w, h = image.size
    roi_br = get_chat_roi("bottom-right", w, h)
    roi_left = get_chat_roi("left", w, h)

    crop_br = image.crop((roi_br["x"], roi_br["y"], roi_br["x"] + roi_br["w"], roi_br["y"] + roi_br["h"]))
    crop_left = image.crop((roi_left["x"], roi_left["y"], roi_left["x"] + roi_left["w"], roi_left["y"] + roi_left["h"]))

    def edge_score(crop: Image.Image) -> float:
        gray = crop.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        return float(stat.mean[0])

    score_br = edge_score(crop_br)
    score_left = edge_score(crop_left)

    if score_left > score_br * 1.2 and score_left > 5.0:
        return "left"
    return "bottom-right"


def probe_chat_layout(video_path: str | Path, sample_sec: int = 0) -> str:
    """Probe candidate chat overlay layout from video at sample_sec."""
    path = Path(video_path)
    if not path.exists():
        return "bottom-right"

    temp_frame = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_frame = Path(f.name)

        cmd = [
            "ffmpeg",
            "-ss", str(sample_sec),
            "-i", str(path),
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            str(temp_frame),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if res.returncode == 0 and temp_frame.exists() and temp_frame.stat().st_size > 0:
            with Image.open(temp_frame) as img:
                return probe_chat_layout_from_image(img)
    except Exception:
        pass
    finally:
        if temp_frame and temp_frame.exists():
            try:
                temp_frame.unlink()
            except Exception:
                pass

    return "bottom-right"


def detect_chat_layout(video_path: str | Path, sample_sec: int = 0, force_pos: str = "auto") -> str:
    """Detect or return forced chat overlay layout ('bottom-right' or 'left')."""
    if force_pos in ("bottom-right", "left"):
        return force_pos
    if force_pos != "auto":
        raise ValueError(f"Unknown force_pos: {force_pos}. Valid options: 'auto', 'bottom-right', 'left'")
    return probe_chat_layout(video_path, sample_sec=sample_sec)


def acquire_video_slice(
    video_path: str | Path | None,
    video_id: str | None,
    time_range: str,
    output_dir: Path | str,
) -> Path:
    """Ensure a video slice is available, either from local video_path or via yt-dlp section download."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if video_path:
        p = Path(video_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified video_path does not exist: {video_path}")

    if not video_id:
        raise ValueError("Either video_path or video_id must be provided")

    out_template = str(out_dir / f"slice_{video_id}.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "--download-sections", f"*{time_range}",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "-o", out_template,
        url,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    candidates = sorted(out_dir.glob(f"slice_{video_id}.*")) + sorted(out_dir.glob(f"slice_{video_id}_*.*"))
    if candidates:
        return candidates[0]

    if res.returncode != 0:
        raise RuntimeError(f"yt-dlp failed with code {res.returncode}: {res.stderr}")
    raise FileNotFoundError(f"Downloaded slice for {video_id} not found in {out_dir}")


def get_video_resolution(video_path: Path | str) -> tuple[int, int]:
    """Retrieve video width and height using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(video_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0 and "x" in res.stdout:
            w_str, h_str = res.stdout.strip().split("x", 1)
            return int(w_str), int(h_str)
    except Exception:
        pass
    return (1280, 720)


def get_video_duration(video_path: Path | str) -> float:
    """Retrieve video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def extract_chat_frames(
    video_path: Path | str,
    start_sec: int,
    end_sec: int,
    layout: str,
    interval: float,
    frames_dir: Path,
) -> list[tuple[int, Path]]:
    """Extract and crop live chat frames from video_path into frames_dir at given interval."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    w, h = get_video_resolution(video_path)
    roi = get_chat_roi(layout, w, h)
    crop_str = build_crop_filter(roi)
    duration = get_video_duration(video_path)

    # If duration is shorter than end_sec, video is already sliced to target range
    is_pre_sliced = 0 < duration < end_sec

    out_pattern = str(frames_dir / "chat_%03d.jpg")
    if is_pre_sliced:
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval},{crop_str}",
            "-q:v", "2",
            "-y",
            out_pattern,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-ss", sec_to_hhmmss(start_sec),
            "-to", sec_to_hhmmss(end_sec),
            "-i", str(video_path),
            "-vf", f"fps=1/{interval},{crop_str}",
            "-q:v", "2",
            "-y",
            out_pattern,
        ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if res.returncode != 0:
        print(f"Warning: ffmpeg frame extraction returned {res.returncode}", file=sys.stderr)

    frame_files = sorted(frames_dir.glob("chat_*.jpg"))
    result: list[tuple[int, Path]] = []
    for i, fp in enumerate(frame_files):
        sec = min(start_sec + int(i * interval), end_sec)
        result.append((sec, fp))

    return result


def run_agy_vision_ocr(frames_dir: Path) -> str:
    """Invoke agy with Gemini 3.6 Flash (Medium) to extract live chat messages from frames."""
    cmd = [
        "agy",
        "--model", "Gemini 3.6 Flash (Medium)",
        "--dangerously-skip-permissions",
        "--print", VISION_PROMPT,
        "--add-dir", str(frames_dir),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if res.returncode != 0:
        print(f"Warning: agy exited with code {res.returncode}: {res.stderr}", file=sys.stderr)
    return res.stdout


def convert_to_frames_data(
    parsed: list[dict],
    frame_files: list[tuple[int, Path]],
) -> list[dict]:
    """Convert parsed Gemini JSON list into standard frames_data format for deduplication."""
    if not parsed:
        return []

    # Check if items contain per-frame structures
    has_frame_key = any("frame" in item or "messages" in item for item in parsed)
    if has_frame_key:
        file_sec_map = {f[1].name: f[0] for f in frame_files}
        frames_data = []
        for i, item in enumerate(parsed):
            frame_name = item.get("frame", "")
            sec = file_sec_map.get(frame_name)
            if sec is None and i < len(frame_files):
                sec = frame_files[i][0]
            elif sec is None and frame_files:
                sec = frame_files[0][0]
            elif sec is None:
                sec = 0
            frames_data.append({
                "sec": sec,
                "messages": item.get("messages", []),
            })
        return frames_data

    # Otherwise parsed is a flat list of message dicts
    start_sec = frame_files[0][0] if frame_files else 0
    return [{"sec": start_sec, "messages": parsed}]


def build_arg_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract on-screen livechat messages via Gemini vision proxy."
    )
    parser.add_argument("--video-id", help="YouTube Video ID")
    parser.add_argument("--video-path", help="Path to local video file")
    parser.add_argument("--range", required=True, help="Target time range: START-END (e.g. 00:10:00-00:12:30)")
    parser.add_argument("-o", "--output", help="Output file path for raw event lines")
    parser.add_argument(
        "--force-pos",
        choices=["auto", "bottom-right", "left"],
        default="auto",
        help="Force chat overlay position or 'auto' detect (default: auto)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=0.25,
        help="Sampling rate in frames per second (default: 0.25, i.e. 1 frame every 4s)",
    )
    parser.add_argument(
        "--workdir",
        help="Directory to save temporary video slices and frame crops (cleaned up if omitted)",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    start_sec, end_sec = parse_time_range(args.range)
    interval = 1.0 / args.fps if args.fps > 0 else 4.0

    temp_dir_obj = None
    if args.workdir:
        workdir = Path(args.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="visual_livechat_")
        workdir = Path(temp_dir_obj.name)

    try:
        # 1. Acquire video slice
        print(f"Acquiring video slice for range {args.range}...")
        video_file = acquire_video_slice(
            video_path=args.video_path,
            video_id=args.video_id,
            time_range=args.range,
            output_dir=workdir,
        )
        print(f"Using video: {video_file}")

        # 2. Detect layout
        layout = detect_chat_layout(video_file, sample_sec=start_sec, force_pos=args.force_pos)
        print(f"Chat overlay layout: {layout}")

        # 3. Extract and crop frames
        frames_dir = workdir / "frames"
        print(f"Extracting cropped chat frames at {interval}s interval...")
        frame_files = extract_chat_frames(
            video_path=video_file,
            start_sec=start_sec,
            end_sec=end_sec,
            layout=layout,
            interval=interval,
            frames_dir=frames_dir,
        )
        print(f"Extracted {len(frame_files)} frames into {frames_dir}")

        if not frame_files:
            print("Warning: No frames extracted.", file=sys.stderr)
            return 1

        # 4. Vision OCR via agy
        print("Invoking agy Gemini Vision OCR...")
        raw_vision_output = run_agy_vision_ocr(frames_dir)

        # 5. Parse and deduplicate
        parsed_json = parse_gemini_chat_json(raw_vision_output)
        frames_data = convert_to_frames_data(parsed_json, frame_files)
        events = deduplicate_frames_messages(frames_data)
        print(f"Extracted {len(events)} deduplicated chat events.")

        # 6. Output formatted events
        output_lines = [formatted for _, formatted in events]
        output_text = "\n".join(output_lines) + ("\n" if output_lines else "")

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Saved {len(events)} events to {out_path}")
        else:
            print(output_text, end="")

        return 0
    finally:
        if temp_dir_obj:
            temp_dir_obj.cleanup()


if __name__ == "__main__":
    sys.exit(main())
