"""Mid-chunk webcam layout drift detection and selective segment re-probing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

from video.dynamic_balance import decode_tile_box
from video.face_motion_metrics import compute_frame_delta
from video.motion_types import FaceBox, WindowBounds
from video.obs_layout import detect_obs_layout
from video.pixel_tones import face_tone_fraction, green_chat_fraction

_FULL_CROP_BOX = FaceBox(0.0, 0.0, 1.0, 1.0, "full")
_SPLIT_JUMP_FLOOR = 0.125
_DEAD_MOTION_CEIL = 0.006
_BLANK_FACE_TONE_CEIL = 0.020
_CHAT_GREEN_MEAN_FLOOR = 0.05
_CHAT_GREEN_MAX_FLOOR = 0.06
_MAX_RUN_REPROBES = 4


@dataclass(frozen=True)
class ReprobePlan:
    """Parameters and callbacks needed to verify and re-render switched webcam segments."""

    secs: Sequence[int]
    initial_box: FaceBox
    vf_fn: Callable[[FaceBox], str]
    render_wc_fn: Callable[[Any, int, str], Optional[Tuple[str, Path, str, str]]]


def _same_box(a: Optional[FaceBox], b: Optional[FaceBox]) -> bool:
    """Return True when two FaceBox regions match within 2% tolerance."""
    if a is None or b is None:
        return a is b
    return (
        abs(a.x - b.x) < 0.02
        and abs(a.y - b.y) < 0.02
        and abs(a.w - b.w) < 0.02
        and abs(a.h - b.h) < 0.02
    )


def _frame_sec(frame: Tuple[str, Path, str, str], fallback: int) -> int:
    """Extract second offset encoded in wc_XXXXXX.jpg path, falling back gracefully."""
    stem = Path(frame[1]).stem
    if stem.startswith("wc_") and stem[3:].isdigit():
        return int(stem[3:])
    return fallback


def _decode_rendered_buffers(frames: Sequence[Tuple[str, Path, str, str]]) -> Optional[List[bytes]]:
    """Decode each rendered webcam JPEG to small RGB bytes; return None if any fails."""
    bufs: List[bytes] = []
    for _, img_path, _, _ in frames:
        rgb = decode_tile_box(Path(img_path), _FULL_CROP_BOX)
        if not rgb:
            return None
        bufs.append(rgb)
    return bufs


def _compute_consecutive_deltas(bufs: Sequence[bytes]) -> List[float]:
    """Compute pairwise MAD between adjacent rendered webcam frames."""
    return [compute_frame_delta(bufs[i - 1], bufs[i])[0] for i in range(1, len(bufs))]


def _partition_runs(deltas: Sequence[float], bufs: Sequence[bytes]) -> List[Tuple[int, int]]:
    """Partition [0..N) into visual runs split at MAD jumps or livechat/blank transitions."""
    bad = [green_chat_fraction(b) >= _CHAT_GREEN_MAX_FLOOR or face_tone_fraction(b) < _BLANK_FACE_TONE_CEIL for b in bufs]
    runs: List[Tuple[int, int]] = []
    start = 0
    for idx, delta in enumerate(deltas, start=1):
        if delta >= _SPLIT_JUMP_FLOOR or bad[idx] != bad[idx - 1]:
            runs.append((start, idx))
            start = idx
    runs.append((start, len(bufs)))
    return runs


def _is_dead_run(deltas: Sequence[float], bounds: Tuple[int, int]) -> bool:
    """Return True when a multi-frame run has near-zero visual movement."""
    lo, hi = bounds
    if hi - lo < 2:
        return False
    span_deltas = deltas[lo : hi - 1]
    return bool(span_deltas) and max(span_deltas) < _DEAD_MOTION_CEIL


@dataclass(frozen=True)
class _RerenderTarget:
    """Target slice and replacement filter for overwriting cached webcam frames."""

    frame_secs: Sequence[int]
    bounds: Tuple[int, int]
    new_vf: str


def _rerender_segment(
    req: Any,
    updated: List[Tuple[str, Path, str, str]],
    target: _RerenderTarget,
    render_wc_fn: Callable[[Any, int, str], Optional[Tuple[str, Path, str, str]]],
) -> None:
    """Safely overwrite cached webcam JPEGs across target.bounds using target.new_vf."""
    lo, hi = target.bounds
    for i in range(lo, hi):
        old_path = Path(updated[i][1])
        bak_path = old_path.with_suffix(".bak")
        had_old = old_path.is_file()
        if had_old:
            old_path.replace(bak_path)
        fresh = render_wc_fn(req, target.frame_secs[i], target.new_vf)
        if fresh is not None:
            bak_path.unlink(missing_ok=True)
            updated[i] = fresh
        elif had_old and bak_path.is_file():
            bak_path.replace(old_path)


def _is_chat_run(bufs: Sequence[bytes], bounds: Tuple[int, int]) -> bool:
    """Return True when rendered crop appears to frame green YouTube LiveChat bars."""
    lo, hi = bounds
    greens = [green_chat_fraction(b) for b in bufs[lo:hi]]
    return bool(greens) and (sum(greens) / len(greens) >= _CHAT_GREEN_MEAN_FLOOR or max(greens) >= _CHAT_GREEN_MAX_FLOOR)


def _run_needs_reprobe(bufs: Sequence[bytes], deltas: Sequence[float], bounds: Tuple[int, int]) -> bool:
    """Return True when rendered frames look dead, blank-face, or LiveChat-covered."""
    lo, hi = bounds
    span = bufs[lo:hi]
    if _is_dead_run(deltas, bounds) or _is_chat_run(bufs, bounds):
        return True
    return bool(span) and min(face_tone_fraction(b) for b in span) < _BLANK_FACE_TONE_CEIL


def _select_runs_to_check(
    runs: Sequence[Tuple[int, int]],
    deltas: Sequence[float],
    bufs: Sequence[bytes],
) -> List[Tuple[int, int]]:
    """Pick only broken, dead, or chat-covered runs so valid webcam segments stay intact."""
    bad = [r for r in runs if _run_needs_reprobe(bufs, deltas, r)]
    ranked = sorted(bad, key=lambda r: (-(r[1] - r[0]), r[0]))
    return sorted(ranked[:_MAX_RUN_REPROBES], key=lambda r: r[0])


def _apply_segment_reprobes(
    req: Any,
    updated: List[Tuple[str, Path, str, str]],
    to_check: Sequence[Tuple[int, int]],
    plan: ReprobePlan,
) -> List[Tuple[str, Path, str, str]]:
    """Re-probe each flagged slice and overwrite only frames whose box changed."""
    frame_secs = [_frame_sec(f, plan.secs[min(i, len(plan.secs) - 1)]) for i, f in enumerate(updated)]
    layout_fn = getattr(req, "layout_fn", None) or detect_obs_layout
    for lo, hi in to_check:
        mid_sec = float(frame_secs[(lo + hi) // 2])
        layout = layout_fn(req.source, WindowBounds(max(0.0, mid_sec - 2.0), mid_sec + 4.0), preferred="auto")
        new_box = layout.webcam_box if layout else None
        if new_box is not None and not _same_box(new_box, plan.initial_box):
            _rerender_segment(req, updated, _RerenderTarget(frame_secs, (lo, hi), plan.vf_fn(new_box)), plan.render_wc_fn)
    return updated


def reprobe_switched_frames(
    req: Any,
    frames: List[Tuple[str, Path, str, str]],
    plan: ReprobePlan,
) -> List[Tuple[str, Path, str, str]]:
    """Detect mid-chunk camera moves or dead crops and re-render switched runs."""
    if getattr(req, "preferred", "auto") != "auto" or len(frames) < 2:
        return frames
    bufs = _decode_rendered_buffers(frames)
    if not bufs:
        return frames
    deltas = _compute_consecutive_deltas(bufs)
    to_check = _select_runs_to_check(_partition_runs(deltas, bufs), deltas, bufs)
    if not to_check:
        return frames
    return _apply_segment_reprobes(req, list(frames), to_check, plan)
