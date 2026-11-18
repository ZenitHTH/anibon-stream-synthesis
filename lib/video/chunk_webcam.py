"""Per-chunk Pass 1 webcam closeup sampler reusing OBS layout and ffmpeg helpers."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from common.config import PASS1_WEBCAM_FRAMES, WEBCAM_CORNER
from common.time import fmt_ts
from video.face_motion import _export_vf, _render_single_jpeg
from video.motion_types import FaceBox, LayoutSegment, WindowBounds
from video.obs_layout import detect_obs_layout
from video.webcam_storyboard import assemble_webcam_storyboard

_WC_EXPORT_SIZE = 320


@dataclass(frozen=True)
class ChunkWebcamRequest:
    """Bundled inputs for sampling Pass 1 cropped webcam keyframes per chunk."""

    workspace: Path
    source: Optional[Path | str]
    chunk: dict
    target_secs: Tuple[int, ...] = ()
    preferred: str = WEBCAM_CORNER
    max_frames: int = PASS1_WEBCAM_FRAMES
    webcam_box: Optional[FaceBox] = None
    layout_fn: Optional[Callable[..., LayoutSegment]] = None
    render_fn: Optional[Callable[..., bool]] = None


def _is_valid_media(source: Optional[Path | str]) -> bool:
    """Check whether video source is a remote URL or existing file."""
    return bool(source) and (str(source).startswith(("http://", "https://")) or Path(str(source)).is_file())


def _select_fallback_seconds(items: list, max_frames: int) -> List[int]:
    """Select evenly spaced fallback timestamps across chunk items."""
    if not items or max_frames <= 0:
        return []
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + 5
    if max_frames == 1 or (hi - lo) < 20:
        return [(lo + hi) // 2]
    step = max(15, (hi - lo) // (max_frames + 1))
    return [lo + step * (i + 1) for i in range(max_frames) if (lo + step * (i + 1)) < hi][:max_frames]


def _load_or_render_wc(req: ChunkWebcamRequest, sec: int, vf: str) -> Optional[Tuple[str, Path, str, str]]:
    """Return cached or freshly rendered 256x256 webcam frame 4-tuple."""
    out_jpg = Path(req.workspace) / "frames" / "webcam_chunk" / f"wc_{sec:06d}.jpg"
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    if not out_jpg.is_file() or out_jpg.stat().st_size == 0:
        ok = (req.render_fn or _render_single_jpeg)((str(req.source), vf), out_jpg, float(sec))
        if not ok or not out_jpg.is_file():
            return None
    b64 = base64.b64encode(out_jpg.read_bytes()).decode("ascii")
    return (fmt_ts(sec), out_jpg, b64, "WEBCAM CLOSEUP")


def _chunked_sheets(frames: list, ws: Path, ch_idx: int) -> List[Tuple[str, Path, str, str]]:
    """Pack webcam frames into 1 or 2 tiled storyboard sheets (<= 9 frames per sheet)."""
    if len(frames) < 2:
        return frames
    sheets: List[Tuple[str, Path, str, str]] = []
    for part, start in enumerate(range(0, len(frames), 9)):
        batch = frames[start : start + 9]
        sheet_path = ws / "frames" / "webcam_chunk" / f"wc_sheet_{ch_idx:02d}_{part}.jpg"
        sheet = assemble_webcam_storyboard(batch, sheet_path)
        if sheet is None:
            return frames
        sheets.append(sheet)
    return sheets


def sample_chunk_webcam_frames(req: ChunkWebcamRequest) -> List[Tuple[str, Path, str, str]]:
    """Sample cropped HD webcam closeup JPEGs and pack as storyboard sheet(s) for Pass 1."""
    if not _is_valid_media(req.source) or req.max_frames <= 0:
        return []
    secs = sorted(req.target_secs[:req.max_frames]) if req.target_secs else _select_fallback_seconds(req.chunk.get("items", []), req.max_frames)
    if not secs:
        return []
    box = req.webcam_box
    if box is None:
        layout = (req.layout_fn or detect_obs_layout)(req.source, WindowBounds(max(0.0, secs[0] - 3.0), secs[0] + 5.0), preferred=req.preferred)
        box = layout.webcam_box
    if box is None:
        return []
    vf = _export_vf(box, _WC_EXPORT_SIZE)
    frames = [f for sec in secs if (f := _load_or_render_wc(req, sec, vf)) is not None]
    return _chunked_sheets(frames, Path(req.workspace), int(req.chunk.get("_idx", 0) or 0))


__all__ = ["ChunkWebcamRequest", "sample_chunk_webcam_frames"]
