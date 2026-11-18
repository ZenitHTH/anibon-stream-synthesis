"""Per-segment OBS webcam layout classification and full-frame layout-cut splitting."""
from __future__ import annotations

import statistics
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from video.auto_tracker import track_webcam_any_position
from video.face_motion_metrics import compute_frame_delta
from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox, LayoutSegment, WindowBounds

_CORNER_KEYS: Tuple[str, ...] = (
    "top-right", "mid-right", "mid-left", "bottom-right", "bottom-left", "top-left",
)
_CENTER_PROBE = FaceBox(0.28, 0.08, 0.44, 0.65, "center")


def resolve_webcam_and_face_boxes(layout: str) -> Tuple[Optional[FaceBox], Optional[FaceBox]]:
    """Resolve (webcam_box W, tight_face_box F) for a named OBS layout."""
    w_box = WEBCAM_BOX_PRESETS.get(layout)
    f_box = w_box.derive_tight_face() if w_box is not None else None
    return (w_box, f_box)


def detect_layout_cuts(
    full_frames: List[bytes], fps: float = 2.0, cut_mad_floor: float = 0.22
) -> List[int]:
    """Return frame indices where global frame structure jumps across an OBS scene cut."""
    if len(full_frames) < 2:
        return []
    return [
        i for i in range(1, len(full_frames))
        if compute_frame_delta(full_frames[i - 1], full_frames[i])[0] >= cut_mad_floor
    ]


def _longest_clear_span(blocked: List[bool]) -> Tuple[int, int]:
    """Return (start, end) of longest False run in blocked mask."""
    best_lo, best_hi, cur_lo = 0, 0, None
    for i, is_bad in enumerate(blocked + [True]):
        if not is_bad and cur_lo is None:
            cur_lo = i
        elif is_bad and cur_lo is not None:
            if (i - cur_lo) > (best_hi - best_lo):
                best_lo, best_hi = cur_lo, i
            cur_lo = None
    return (best_lo, best_hi)


def split_around_cuts(
    total_frames: int, cut_indices: List[int], fps: float = 2.0
) -> Tuple[int, int]:
    """Suppress +-1.5s around cuts and return (start, end) of largest clean sub-segment."""
    if total_frames <= 0:
        return (0, 0)
    if not cut_indices:
        return (0, total_frames)
    pad = max(1, int(round(1.5 * fps)))
    blocked = [False] * total_frames
    for c in cut_indices:
        for k in range(max(0, c - pad), min(total_frames, c + pad + 1)):
            blocked[k] = True
    lo, hi = _longest_clear_span(blocked)
    return (lo, hi) if (hi - lo) >= 2 else (0, total_frames)


def _crop_rgb_box(frame: bytes, size: int, box: FaceBox) -> bytes:
    """Slice normalized FaceBox pixels out of a square RGB24 buffer."""
    x0, x1 = max(0, min(size - 1, int(box.x * size))), max(1, min(size, int((box.x + box.w) * size)))
    y0, y1 = max(0, min(size - 1, int(box.y * size))), max(1, min(size, int((box.y + box.h) * size)))
    return b"".join(frame[(y * size + x0) * 3 : (y * size + max(x0 + 1, x1)) * 3] for y in range(y0, max(y0 + 1, y1)))


def _region_mad(frames: List[bytes], size: int, box: FaceBox) -> float:
    """Compute mean consecutive MAD inside a normalized box across frames."""
    crops = [_crop_rgb_box(f, size, box) for f in frames]
    if len(crops) < 2:
        return 0.0
    return sum(compute_frame_delta(crops[i - 1], crops[i])[0] for i in range(1, len(crops))) / (len(crops) - 1)


def _has_trackable_face(frames: List[bytes], sample_size: int, box: Optional[FaceBox]) -> bool:
    """Check whether a candidate box contains trackable temporal face/body motion."""
    if box is None or len(frames) < 2:
        return False
    probe = _CENTER_PROBE if box.w >= 0.99 else box
    return _region_mad(frames, sample_size, probe) >= 0.010


def _match_fixed_corner(clean: List[bytes], sample_size: int) -> Optional[str]:
    """Check fixed corner presets first and return dominant corner if trackable."""
    scores: Dict[str, float] = {k: _region_mad(clean, sample_size, WEBCAM_BOX_PRESETS[k]) for k in _CORNER_KEYS}
    best_k, best_mad = max(scores.items(), key=lambda kv: kv[1])
    med_mad = statistics.median(scores.values())
    if _has_trackable_face(clean, sample_size, WEBCAM_BOX_PRESETS[best_k]) and best_mad >= max(0.012, 1.45 * max(med_mad, 0.002)):
        return best_k
    return None


def _resolve_from_clean(
    clean: List[bytes], sample_size: int, preferred: str
) -> Tuple[str, Optional[FaceBox]]:
    """Check fixed position first; fall back to any-position tracker if untrackable."""
    if preferred == "none":
        return ("none", None)
    if preferred != "auto" and preferred in WEBCAM_BOX_PRESETS:
        wb = WEBCAM_BOX_PRESETS[preferred]
        if _has_trackable_face(clean, sample_size, wb):
            return (preferred, wb)
        return track_webcam_any_position(clean, sample_size)
    fixed = _match_fixed_corner(clean, sample_size)
    if fixed is not None:
        return (fixed, WEBCAM_BOX_PRESETS[fixed])
    return track_webcam_any_position(clean, sample_size)


def classify_layout_from_frames(
    full_frames: List[bytes], sample_size: int = 48, fps: float = 1.0
) -> LayoutSegment:
    """Classify OBS webcam layout from sparse full-frame RGB24 probes."""
    cuts = detect_layout_cuts(full_frames, fps=fps)
    cut_secs = tuple(round(c / max(fps, 0.1), 3) for c in cuts)
    lo, hi = split_around_cuts(len(full_frames), cuts, fps=fps)
    clean = full_frames[lo:hi]
    if len(clean) < 2:
        return LayoutSegment("none", None, None, cut_secs)
    layout, wb = _resolve_from_clean(clean, sample_size, "auto")
    fb = wb.derive_tight_face() if wb is not None else None
    return LayoutSegment(layout, wb, fb, cut_secs)


def _probe_full_frames(source: Path | str, bounds: WindowBounds) -> List[bytes]:
    """Extract sparse 48x48 full-frame RGB24 probes via ffmpeg for layout detection."""
    src = str(source)
    if not src.startswith(("http://", "https://")) and not Path(src).is_file():
        return []
    dur = max(2.0, bounds.end_sec - bounds.start_sec)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, bounds.start_sec):.3f}", "-i", src,
           "-t", f"{dur:.3f}", "-vf", "fps=1.0000,scale=48:48:flags=area,format=rgb24",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    res = subprocess.run(cmd, capture_output=True, timeout=45)
    if res.returncode != 0:
        return []
    fb = 48 * 48 * 3
    return [res.stdout[i * fb : (i + 1) * fb] for i in range(len(res.stdout) // fb)]


def detect_obs_layout(
    source: Path | str, bounds: WindowBounds, preferred: str = "auto"
) -> LayoutSegment:
    """Probe frames, check fixed position first, and fall back to any-position tracker."""
    key = (preferred or "auto").strip().lower()
    frames = _probe_full_frames(source, bounds)
    if len(frames) < 2:
        fallback = key if key != "auto" and key in WEBCAM_BOX_PRESETS else "top-right"
        wb, fb = resolve_webcam_and_face_boxes(fallback)
        return LayoutSegment(fallback, wb, fb, ())
    cuts = detect_layout_cuts(frames, fps=1.0)
    cut_secs = tuple(round(c, 3) for c in cuts)
    lo, hi = split_around_cuts(len(frames), cuts, fps=1.0)
    layout, wb = _resolve_from_clean(frames[lo:hi], 48, key)
    fb = wb.derive_tight_face() if wb is not None else None
    return LayoutSegment(layout, wb, fb, cut_secs)
