"""yt-dlp wrappers for transcript/video download and metadata probing."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from common.time import fmt_ts

DEFAULT_SUB_LANGS = "th-orig,en-orig,th,en"
_SUB_PRIORITY = ("th-orig", "en-orig", "th", "en")
_METADATA_KEYS = ("id", "title", "upload_date", "release_timestamp", "duration", "channel", "uploader", "webpage_url")


def ytdlp_cmd() -> list[str]:
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]


def _select_best_json3(workspace: Path) -> Path | None:
    candidates = sorted(workspace.glob("raw_transcript*.json3"))
    if not candidates:
        return None
    for lang in _SUB_PRIORITY:
        for path in candidates:
            if path.name.endswith(f".{lang}.json3"):
                return path
    return candidates[0]


def download_transcript(url: str, workspace: Path, sub_langs: str = DEFAULT_SUB_LANGS) -> None:
    out = workspace / "raw_transcript.json"
    if out.exists():
        print("[*] Transcript already exists, skipping download.", file=sys.stderr)
        return
    print("[*] Downloading transcript via yt-dlp...", file=sys.stderr)
    cmd = [
        *ytdlp_cmd(), "-P", str(workspace), "--write-auto-subs", "--write-subs",
        "--sub-lang", sub_langs, "--sub-format", "json3", "--skip-download",
        "--ignore-no-formats-error", "-o", "raw_transcript", url,
    ]
    subprocess.run(cmd, check=False)
    best = _select_best_json3(workspace)
    if best:
        best.rename(out)
    if not out.exists():
        print("[!] Error: Failed to download transcript.", file=sys.stderr)
        sys.exit(1)


def save_metadata(url: str, workspace: Path) -> Path | None:
    info_path = Path(workspace) / "info.json"
    if info_path.is_file():
        return info_path
    meta = probe_metadata(url)
    if not meta:
        return None
    compact = {k: meta.get(k) for k in _METADATA_KEYS if meta.get(k) is not None}
    info_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding="utf-8")
    return info_path


def _download_144p_video(url: str, video_path: Path) -> bool:
    if video_path.is_file() and video_path.stat().st_size > 0:
        return True
    fmt = "160/bestvideo[height<=240][ext=mp4]/worst[ext=mp4]"
    cmd = [*ytdlp_cmd(), "-f", fmt, "-o", str(video_path), url]
    res = subprocess.run(cmd, capture_output=True, check=False)
    return res.returncode == 0 and video_path.is_file()


def _tile_video_to_slides(video_path: Path, clean_dir: Path) -> Path | None:
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(clean_dir / "slide_%04d.jpg")
    vf = "fps=1/10,scale=320:180,tile=3x3"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video_path), "-vf", vf, "-q:v", "3", out_pattern]
    res = subprocess.run(cmd, capture_output=True, check=False)
    return clean_dir if res.returncode == 0 and any(clean_dir.glob("slide_*.jpg")) else None


def _synthesize_slides_from_144p(url: str, frames_dir: Path) -> Path | None:
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
            [*ytdlp_cmd(), "-P", str(frames_dir), "-f", "sb0/sb1/sb2/sb3", "--ignore-no-formats-error", "-o", "storyboard.%(ext)s", url],
            capture_output=True, check=False, timeout=120,
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
    output = Path(output)
    if output.exists():
        return output
    print(f"[!] Downloading video via yt-dlp...", file=sys.stderr)
    try:
        subprocess.run([*ytdlp_cmd(), "-f", format_spec, "-o", str(output), url], check=True)
        return output
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to download video: {e}", file=sys.stderr)
        return None


def flatten_json3(raw: dict) -> list:
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
    path = workspace / "raw_transcript.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return flatten_json3(raw) if "events" in raw else raw


def probe_metadata(url: str) -> dict | None:
    try:
        res = subprocess.run([*ytdlp_cmd(), "--dump-json", url], capture_output=True, text=True, check=True, timeout=30)
        return json.loads(res.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"[!] Failed to probe metadata: {e}", file=sys.stderr)
        return None
