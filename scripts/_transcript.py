# scripts/_transcript.py
import sys, subprocess, json
from pathlib import Path

def _fmt(s: float) -> str:
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

def _flatten_json3(raw: dict) -> list:
    """Convert yt-dlp json3 format to flat [{text, start, duration}] list."""
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
                "timestamp": _fmt(e.get("tStartMs", 0) / 1000.0),
            })
    items.sort(key=lambda x: x["start"])
    return items

def download(url: str, workspace: Path) -> None:
    """Download transcript via yt-dlp. Skip if raw_transcript.json already exists."""
    out = workspace / "raw_transcript.json"
    if out.exists():
        print(f"[*] Transcript already exists, skipping download.", file=sys.stderr)
        return

    print(f"[*] Downloading transcript via yt-dlp...", file=sys.stderr)
    subprocess.run([
        sys.executable, "-m", "yt_dlp", "-P", str(workspace),
        "--write-auto-subs", "--sub-lang", "th-orig,th",
        "--sub-format", "json3", "--skip-download",
        "--ignore-no-formats-error", "-o", "raw_transcript", url
    ], check=False)

    # Rename yt-dlp output (e.g. raw_transcript.th.json3) to raw_transcript.json
    for f in workspace.glob("raw_transcript*.json3"):
        f.rename(out)
        break

    if not out.exists():
        print("[!] Error: Failed to download transcript.", file=sys.stderr)
        sys.exit(1)

def load(workspace: Path) -> list:
    """Load and return flat transcript list from workspace."""
    path = workspace / "raw_transcript.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "events" in raw:
        return _flatten_json3(raw)
    return raw
