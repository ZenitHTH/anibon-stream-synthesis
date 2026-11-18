"""Media source resolution (high-res video & separate audio stream) for reaction verify."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from download.ytdlp import ytdlp_cmd

_REMOTE_VIDEO_FMT = (
    "bestvideo[height<=1080][protocol^=m3u8]/bestvideo[vcodec^=avc1][height<=1080]"
    "/bestvideo[height<=1080]/best[height<=1080]/best[height<=720]/best"
)
_REMOTE_AUDIO_FMT = "bestaudio[protocol^=m3u8]/bestaudio/best[height<=480]/best"
_LOCAL_VIDEO_NAMES = ("video.mp4", "video_1080p.mp4", "video_720p.mp4", "video_360p.mp4")


def _resolve_remote_url(workspace: Path, args: Any, fmt: str = _REMOTE_VIDEO_FMT) -> Optional[str]:
    """Resolve direct stream URL via yt-dlp -g when --remote-snap is set."""
    url = getattr(args, "video_url", None)
    if not url and (workspace / ".video_url").is_file():
        url = (workspace / ".video_url").read_text(encoding="utf-8").strip()
    if not url:
        return None
    cmd = [*ytdlp_cmd(), "-f", fmt, "-g", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.stdout.strip().splitlines()[0] if (res.returncode == 0 and res.stdout.strip()) else None
    except (OSError, subprocess.SubprocessError):
        return None


def _find_local_video(workspace: Path, args: Any) -> Optional[Path]:
    """Locate highest-resolution local video file when present in workspace."""
    vf = getattr(args, "video_file", None)
    if vf and Path(vf).is_file():
        return Path(vf)
    for name in _LOCAL_VIDEO_NAMES:
        cand = Path(workspace) / name
        if cand.is_file():
            return cand
    return None


def resolve_reaction_source(workspace: Path, args: Any) -> Optional[Path | str]:
    """Locate high-resolution local video or remote stream URL for webcam cropping."""
    local = _find_local_video(Path(workspace), args)
    if local is not None:
        return local
    if getattr(args, "remote_snap", False):
        return _resolve_remote_url(Path(workspace), args, fmt=_REMOTE_VIDEO_FMT)
    return None


def resolve_reaction_audio_source(workspace: Path, args: Any) -> Optional[Path | str]:
    """Locate local video or playable audio stream URL for RMS burst detection."""
    local = _find_local_video(Path(workspace), args)
    if local is not None:
        return local
    if getattr(args, "remote_snap", False):
        return _resolve_remote_url(Path(workspace), args, fmt=_REMOTE_AUDIO_FMT)
    return None
