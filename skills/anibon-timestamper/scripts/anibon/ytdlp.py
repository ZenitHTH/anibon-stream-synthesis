"""yt-dlp wrappers for transcript/video download and metadata probing.

Consumers (before extraction):
  download_transcript   — _transcript.py:25
  flatten_json3         — _transcript.py:8
  load_transcript       — _transcript.py:49
  download_video        — _vision.py:11, cut_highlight.py (direct subprocess)
  probe_metadata        — plan_highlight.py:147
"""
import sys
import subprocess
import json
from pathlib import Path
from anibon.time import fmt_ts


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
            sys.executable, "-m", "yt_dlp", "-P", str(workspace),
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
            [sys.executable, "-m", "yt_dlp", "-f", format_spec, "-o", str(output), url],
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
            ["yt-dlp", "--dump-json", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return json.loads(res.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"[!] Failed to probe metadata: {e}", file=sys.stderr)
        return None
