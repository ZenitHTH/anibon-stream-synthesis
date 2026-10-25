"""yt-dlp wrappers for transcript/video download and metadata probing.

Consumers (before extraction):
  download_transcript   — _transcript.py:25
  flatten_json3         — _transcript.py:8
  load_transcript       — _transcript.py:49
  download_video        — _vision.py:11, cut_highlight.py (direct subprocess)
  probe_metadata        — plan_highlight.py:147
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from common.time import fmt_ts


def ytdlp_cmd() -> list[str]:
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]


def download_transcript(url: str, workspace: Path) -> None:
    """Download YouTube transcript via yt-dlp.

    Skips if raw_transcript.json already exists in workspace.
    Downloads auto-subs (Thai), saves as raw_transcript.json.
    """
    out = workspace / "raw_transcript.json"
    if out.exists():
        print("[*] Transcript already exists, skipping download.", file=sys.stderr)
        return

    print("[*] Downloading transcript via yt-dlp...", file=sys.stderr)
    subprocess.run(
        [
            *ytdlp_cmd(), "-P", str(workspace),
            "--write-auto-subs", "--sub-lang", "th-orig,th",
            "--sub-format", "json3", "--skip-download",
            "--ignore-no-formats-error", "-o", "raw_transcript", url,
        ],
        check=False,
    )

    # Rename yt-dlp output (e.g. raw_transcript.th.json3) → raw_transcript.json
    for f in workspace.glob("raw_transcript*.json3"):
        f.rename(out)
        break

    if not out.exists():
        print("[!] Error: Failed to download transcript.", file=sys.stderr)
        sys.exit(1)


def _download_144p_video(url: str, video_path: Path) -> bool:
    """Download 144p video stream for local storyboard synthesis."""
    if video_path.is_file() and video_path.stat().st_size > 0:
        return True
    fmt = "160/bestvideo[height<=240][ext=mp4]/worst[ext=mp4]"
    cmd = [*ytdlp_cmd(), "-f", fmt, "-o", str(video_path), url]
    res = subprocess.run(cmd, capture_output=True, check=False)
    return res.returncode == 0 and video_path.is_file()


def _tile_video_to_slides(video_path: Path, clean_dir: Path) -> Path | None:
    """Tile video frames using ffmpeg into 3x3 storyboard slides."""
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(clean_dir / "slide_%04d.jpg")
    vf = "fps=1/10,scale=320:180,tile=3x3"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video_path), "-vf", vf, "-q:v", "3", out_pattern]
    res = subprocess.run(cmd, capture_output=True, check=False)
    has_slides = any(clean_dir.glob("slide_*.jpg"))
    return clean_dir if res.returncode == 0 and has_slides else None


def _synthesize_slides_from_144p(url: str, frames_dir: Path) -> Path | None:
    """Synthesize 3x3 storyboard slides from 144p video as fallback when sb is missing."""
    video_path = frames_dir / "video_144p.mp4"
    clean_dir = frames_dir / "slides_clean"
    try:
        if not _download_144p_video(url, video_path):
            return None
        return _tile_video_to_slides(video_path, clean_dir)
    except Exception as e:
        print(f"[!] Failed to synthesize 144p storyboard: {e}", file=sys.stderr)
        return None


def download_storyboard(url: str, workspace: Path) -> Path | None:
    """Download storyboard images/mhtml via yt-dlp into workspace/frames/.

    Skips if storyboard file or unpacked slides already exist.
    Falls back to 144p video 3x3 tiling when sb0-sb3 formats are missing.
    """
    frames_dir = Path(workspace) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    for p in [frames_dir / "storyboard.mhtml", frames_dir / "sb0.mhtml"]:
        if p.is_file():
            return p
    clean_dir = frames_dir / "slides_clean"
    if clean_dir.is_dir() and any(clean_dir.glob("slide_*.jpg")):
        return clean_dir

    print("[*] Downloading storyboard via yt-dlp...", file=sys.stderr)
    try:
        subprocess.run(
            [
                *ytdlp_cmd(), "-P", str(frames_dir),
                "-f", "sb0/sb1/sb2/sb3",
                "--ignore-no-formats-error", "-o", "storyboard.%(ext)s", url,
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )

        for m in [frames_dir / "storyboard.mhtml", frames_dir / "sb0.mhtml", frames_dir / "sb1.mhtml"]:
            if m.is_file():
                return m
        found = list(frames_dir.glob("*.mhtml"))
        return found[0] if found else _synthesize_slides_from_144p(url, frames_dir)
    except Exception as e:
        print(f"[!] Failed to download storyboard: {e}", file=sys.stderr)
        return None


def download_video(url: str, output: Path, format_spec: str = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best") -> Path | None:
    """Download a video (or section) via yt-dlp.

    If output already exists, skips download.
    Returns output path on success, None on failure.
    """
    output = Path(output)
    if output.exists():
        print(f"[*] Video already exists at {output}", file=sys.stderr)
        return output

    print(f"[*] Downloading video via yt-dlp...", file=sys.stderr)
    try:
        subprocess.run(
            [*ytdlp_cmd(), "-f", format_spec, "-o", str(output), url],
            capture_output=False,
            check=True,
        )
        return output
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to download video: {e}", file=sys.stderr)
        return None


def flatten_json3(raw: dict) -> list:
    """Convert yt-dlp json3 format to flat [{text, start, duration, timestamp}] list."""
    items = []
    for e in raw.get("events", []):
        if "segs" not in e:
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).strip()
        if text:
            items.append({
                "text": text,
                "start": e.get("tStartMs", 0) / 1000.0,
                "duration": e.get("dDurationMs", 0) / 1000.0,
                "timestamp": fmt_ts(e.get("tStartMs", 0) / 1000.0),
            })
    items.sort(key=lambda x: x["start"])
    return items


def load_transcript(workspace: Path) -> list:
    """Load and return flat transcript list from workspace raw_transcript.json.

    Handles both yt-dlp json3 format and simple JSON array format.
    """
    path = workspace / "raw_transcript.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "events" in raw:
        return flatten_json3(raw)
    return raw


def probe_metadata(url: str) -> dict | None:
    """Fetch video metadata via yt-dlp --dump-json.

    Returns parsed dict or None on failure.
    """
    try:
        res = subprocess.run(
            [*ytdlp_cmd(), "--dump-json", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return json.loads(res.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"[!] Failed to probe metadata: {e}", file=sys.stderr)
        return None
