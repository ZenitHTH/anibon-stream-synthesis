"""Workspace I/O, co-trigger collection, source resolution, and timestamp sync."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.config import AUDIO_RMS_Z_THRESHOLD, DEFAULT_MODEL, ONSET_SNAP_POST_SEC, ONSET_SNAP_PRE_SEC
from common.log import log_info, log_ok, log_warn
from common.time import parse_ts
from download.ytdlp import ytdlp_cmd
from process.multimodal_situations import score_item_situations
from process.reaction_prompt import CoTriggerSignals, ReactionVerifyResult
from process.vision_verify import stamp_seconds
from video.audio_envelope import AudioBurstMetrics, extract_audio_burst_metrics
from video.motion_types import WindowBounds
from video.webcam_storyboard import format_webcam_count


@dataclass(frozen=True)
class CoTriggerContext:
    """Inputs for collecting multi-modal co-triggers around a candidate timestamp."""

    transcript_ctx: str = ""
    source: Optional[Path | str] = None
    audio_fn: Optional[Callable[[Path | str, WindowBounds], AudioBurstMetrics]] = None


@dataclass(frozen=True)
class ReactionRunConfig:
    """Bundled CLI args and resolved model for apply_reaction_verify."""

    args: Any
    model: str = ""


def _window_overlaps(win: dict, sec: int) -> bool:
    """Return True when a mood_555 peak window overlaps [sec-35, sec+35]."""
    lo = parse_ts(str(win.get("start") or ""))
    hi = parse_ts(str(win.get("end") or ""))
    return lo is not None and hi is not None and (lo - 35) <= sec <= (hi + 35)


def _read_meme_pulse_window(workspace: Path, sec: int) -> Tuple[str, bool]:
    """Read mood_555.json and detect MEME_PULSE peak overlap at sec."""
    mood_path = Path(workspace) / "mood_555.json"
    if not mood_path.is_file():
        return ("QUIET", False)
    try:
        data = json.loads(mood_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ("QUIET", False)
    for info in data.values() if isinstance(data, dict) else ():
        if isinstance(info, dict) and info.get("verdict") == "MEME_PULSE":
            if any(_window_overlaps(w, sec) for w in info.get("peak_windows", ()) if isinstance(w, dict)):
                return ("MEME_PULSE", True)
    return ("QUIET", False)


def collect_co_triggers(
    workspace: Path, sec: int, ctx: Optional[CoTriggerContext] = None
) -> CoTriggerSignals:
    """Aggregate transcript situation score, mood_555 peak, and audio RMS burst."""
    c = ctx or CoTriggerContext()
    sit_score = score_item_situations(c.transcript_ctx)
    verdict, peak_hit = _read_meme_pulse_window(workspace, sec)
    audio_metrics: Optional[AudioBurstMetrics] = None
    if c.source:
        bounds = WindowBounds(max(0.0, sec - ONSET_SNAP_PRE_SEC), sec + ONSET_SNAP_POST_SEC)
        fn = c.audio_fn or (lambda src, b: extract_audio_burst_metrics(src, b, AUDIO_RMS_Z_THRESHOLD))
        audio_metrics = fn(c.source, bounds)
    return CoTriggerSignals(sit_score, verdict, peak_hit, audio_metrics)


def load_chunk_context(workspace: Path, sec: int) -> str:
    """Return full transcript window within +-25s of sec from workspace/chunks."""
    chunks_dir = Path(workspace) / "chunks"
    if not chunks_dir.is_dir():
        return ""
    matched: List[str] = []
    for cf in sorted(chunks_dir.glob("chunk_*.txt")):
        for line in cf.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"[\[(](\d{2}):(\d{2}):(\d{2})[\])]", line)
            if m and abs((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))) - sec) <= 25:
                matched.append(line.strip())
    return " | ".join(matched)[:600]


def _resolve_remote_url(workspace: Path, args: Any) -> Optional[str]:
    """Resolve direct stream URL via yt-dlp -g when --remote-snap is set."""
    url = getattr(args, "video_url", None)
    if not url and (workspace / ".video_url").is_file():
        url = (workspace / ".video_url").read_text(encoding="utf-8").strip()
    if not url:
        return None
    cmd = [*ytdlp_cmd(), "-f", "best[height<=480][ext=mp4]/best[height<=720]/best", "-g", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.stdout.strip().splitlines()[0] if (res.returncode == 0 and res.stdout.strip()) else None
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_reaction_source(workspace: Path, args: Any) -> Optional[Path | str]:
    """Locate local video file or remote stream URL for reaction verification."""
    vf = getattr(args, "video_file", None)
    if vf and Path(vf).is_file():
        return Path(vf)
    for name in ("video_360p.mp4", "video.mp4"):
        cand = Path(workspace) / name
        if cand.is_file():
            return cand
    if getattr(args, "remote_snap", False):
        return _resolve_remote_url(Path(workspace), args)
    return None


def load_reaction_log(log_path: Path) -> Dict[str, dict]:
    """Load cached reaction verification entries from disk."""
    if not log_path.is_file():
        return {}
    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_reaction_log(log_path: Path, cache: Dict[str, dict]) -> None:
    """Persist reaction verification cache cleanly to disk."""
    try:
        log_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def result_from_cache(stamp: str, entry: dict) -> ReactionVerifyResult:
    """Reconstruct ReactionVerifyResult from persisted cache entry."""
    return ReactionVerifyResult(
        stamp, str(entry.get("updated", stamp)), int(entry.get("snapped_sec", stamp_seconds(stamp))),
        str(entry.get("emotion_class", "")), str(entry.get("face_cue", "")),
        float(entry.get("peak_motion", 0.0)), float(entry.get("confidence", 0.0)),
        bool(entry.get("accepted", False)),
    )


def result_to_cache(res: ReactionVerifyResult) -> dict:
    """Serialize ReactionVerifyResult to JSON-friendly dictionary."""
    return {
        "updated": res.updated, "snapped_sec": res.snapped_sec, "emotion_class": res.emotion_class,
        "face_cue": res.face_cue, "peak_motion": res.peak_motion, "confidence": res.confidence,
        "accepted": res.accepted,
    }


def sync_raw_timestamps(workspace: Path, mapping: Dict[str, str]) -> None:
    """Sync {orig: updated} replacements back into workspace/all_timestamps.txt."""
    if not mapping:
        return
    raw_ts = Path(workspace) / "all_timestamps.txt"
    if not raw_ts.is_file():
        return
    lines = raw_ts.read_text(encoding="utf-8").splitlines()
    updated = [mapping.get(line.strip(), line) for line in lines]
    raw_ts.write_text("\n".join(updated) + "\n", encoding="utf-8")


def log_reaction_dispatch(header: str, wb_items: list, sb_exported: dict) -> None:
    """Log separated webcam and storyboard image counts dispatched to the VLM."""
    sb_count = len(sb_exported.get("frames") or ())
    log_info("reaction", f"{header} | webcam={format_webcam_count(wb_items)} storyboard={sb_count} -> VLM")


def log_reaction_result(idx: int, stamp: str, res: ReactionVerifyResult) -> None:
    """Emit aligned reaction verification outcome for a candidate stamp."""
    prefix = f"[{idx + 1:02d}] {stamp[:8]}"
    if res.accepted:
        delta = res.snapped_sec - stamp_seconds(stamp)
        log_ok("reaction", f"{prefix} -> {res.updated[:8]} ({delta:+d}s) | {res.emotion_class} (conf={res.confidence:.2f})")
        return
    reason = res.emotion_class or "unchanged"
    log_warn("reaction", f"{prefix} | rejected ({reason}, conf={res.confidence:.2f}) -> kept original")
