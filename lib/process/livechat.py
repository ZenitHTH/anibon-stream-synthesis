"""lib/process/livechat.py — LiveChat replay download, parsing, alignment, and mood pipeline."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_ROOT_DIR = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _ROOT_DIR / "scripts"
_LIVECHAT_SKILL_DIR = _ROOT_DIR / "skills" / "anibon-livechat-analysis"


def find_livechat_file(workspace: Path) -> Optional[Path]:
    """Find downloaded .live_chat.json in workspace."""
    candidates = list(workspace.glob("*.live_chat.json"))
    return candidates[0] if candidates else None


def _resolve_ytdlp_prefix() -> list[str]:
    """Resolve executable prefix for yt-dlp."""
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def download_livechat(url: str, workspace: Path) -> Optional[Path]:
    """Download YouTube live chat replay via yt-dlp."""
    existing = find_livechat_file(workspace)
    if existing:
        return existing
    cmd = [
        *_resolve_ytdlp_prefix(),
        "--sub-langs", "live_chat",
        "--write-sub",
        "--skip-download",
        "-o", f"{workspace}/%(id)s.%(ext)s",
        url,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=False, timeout=180)
    except Exception as e:
        print(f"[livechat] Download failed: {e}", file=sys.stderr)
        return None
    return find_livechat_file(workspace)


def parse_livechat_feed(json_path: Path, raw_events_path: Path) -> bool:
    """Parse .live_chat.json into raw events feed."""
    script = _LIVECHAT_SKILL_DIR / "scripts" / "parse_live_chat.py"
    if not script.is_file():
        return False
    coarse_dir = raw_events_path.parent / "livechat_coarse"
    cmd = [
        sys.executable, "-X", "utf8", str(script),
        str(json_path),
        "--raw-events", str(raw_events_path),
        "-o", str(coarse_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.returncode == 0 and raw_events_path.is_file()


def _resolve_align_script() -> Optional[Path]:
    """Find align_live_chat.py across shared and skill directories."""
    for loc in (_SCRIPTS_DIR, _ROOT_DIR / "skills" / "anibon-timestamper" / "scripts"):
        candidate = loc / "align_live_chat.py"
        if candidate.is_file():
            return candidate
    return None


def align_livechat_feed(events_path: Path, chunks_dir: Path, out_dir: Path) -> bool:
    """Align raw events feed to per-chunk livechat text files."""
    script = _resolve_align_script()
    if not script:
        return False
    cmd = [
        sys.executable, "-X", "utf8", str(script),
        "--events", str(events_path),
        "--chunks", str(chunks_dir),
        "-o", str(out_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.returncode == 0 and (out_dir / "livechat_index.json").is_file()


def has_aligned_livechat(workspace: Path) -> bool:
    """Check if aligned livechat logs exist in workspace."""
    lc_dir = workspace / "livechat"
    idx = lc_dir / "livechat_index.json"
    return lc_dir.is_dir() and idx.is_file()


def _ensure_mood(workspace: Path) -> None:
    """Trigger mood_555 pulse detection if analyze_555 exists."""
    script = _SCRIPTS_DIR / "analyze_555.py"
    out = workspace / "mood_555.json"
    lc_dir = workspace / "livechat"
    if out.exists() or not lc_dir.is_dir() or not script.is_file():
        return
    idx = lc_dir / "livechat_index.json"
    args = ["--livechat", str(lc_dir), "--out", str(out)]
    if idx.is_file():
        args += ["--index", str(idx)]
    subprocess.run([sys.executable, "-X", "utf8", str(script), *args], capture_output=True, check=False)


def prepare_livechat(url: str, workspace: Path) -> bool:
    """End-to-end preparation: download, parse, align, and detect mood pulses."""
    if has_aligned_livechat(workspace):
        _ensure_mood(workspace)
        return True
    json_path = download_livechat(url, workspace)
    if not json_path:
        return False
    events_path = workspace / "livechat_events.txt"
    if not parse_livechat_feed(json_path, events_path):
        return False
    aligned = align_livechat_feed(events_path, workspace / "chunks", workspace / "livechat")
    if aligned:
        _ensure_mood(workspace)
    return aligned
