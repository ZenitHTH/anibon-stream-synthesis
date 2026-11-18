"""Mid-chunk webcam layout drift detection and selective segment re-probing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

from video.dynamic_balance import decode_tile_box
from video.face_motion_metrics import compute_frame_delta
from video.live_corner_score import is_suspect_tight_crop, tight_crop_live_quality
from video.motion_types import FaceBox, WindowBounds
from video.obs_layout import detect_obs_layout
from video.pixel_tones import green_chat_fraction

_FULL_CROP_BOX = FaceBox(0.22, 0.05, 0.56, 0.65, "tight")
_SPLIT_JUMP_FLOOR = 0.125
_DEAD_MOTION_CEIL = 0.006
_BLANK_FACE_TONE_CEIL = 0.095
_CHAT_GREEN_MEAN_FLOOR = 0.05
_CHAT_GREEN_MAX_FLOOR = 0.06
_MAX_RUN_REPROBES = 6


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
    return all(abs(getattr(a, k) - getattr(b, k)) < 0.02 for k in ("x", "y", "w", "h"))


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
    """Partition [0..N) into visual runs split at MAD jumps or livechat/UI transitions."""
    bad = [is_suspect_tight_crop(b, _BLANK_FACE_TONE_CEIL) for b in bufs]
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
    if not bounds or bounds[1] - bounds[0] < 2:
        return False
    span_deltas = deltas[bounds[0] : bounds[1] - 1]
    return bool(span_deltas) and max(span_deltas) < _DEAD_MOTION_CEIL


@dataclass(frozen=True)
class _RerenderTarget:
    """Target slice and replacement filter for overwriting cached webcam frames."""

    frame_secs: Sequence[int]
    bounds: Tuple[int, int]
    new_vf: str


def _swap_if_better(
    old_path: Path, bak_path: Path, fresh: Optional[Tuple[str, Path, str, str]], old_rgb: Optional[bytes]
) -> Optional[Tuple[str, Path, str, str]]:
    """Keep fresh crop only when it is valid and clearly cleaner than previous crop."""
    if fresh is None:
        if bak_path.is_file():
            bak_path.replace(old_path)
        return None
    fresh_path = Path(fresh[1])
    if old_rgb and fresh_path.is_file() and fresh_path.read_bytes()[:2] == b"\xff\xd8":
        new_rgb = decode_tile_box(fresh_path, _FULL_CROP_BOX)
        if new_rgb and tight_crop_live_quality(new_rgb) <= tight_crop_live_quality(old_rgb) + 0.02:
            if green_chat_fraction(old_rgb) < _CHAT_GREEN_MAX_FLOOR or green_chat_fraction(new_rgb) >= _CHAT_GREEN_MAX_FLOOR:
                bak_path.replace(old_path)
                return None
    bak_path.unlink(missing_ok=True)
    return fresh


def _rerender_segment(
    req: Any,
    updated: List[Tuple[str, Path, str, str]],
    target: _RerenderTarget,
    plan_and_bufs: Tuple[ReprobePlan, Sequence[bytes]],
) -> None:
    """Safely overwrite cached webcam JPEGs across target.bounds when quality improves."""
    plan, bufs = plan_and_bufs
    lo, hi = target.bounds
    for i in range(lo, hi):
        old_path = Path(updated[i][1])
        old_rgb = bufs[i] if i < len(bufs) else None
        bak_path = old_path.with_suffix(".bak")
        if old_path.is_file():
            old_path.replace(bak_path)
        fresh = plan.render_wc_fn(req, target.frame_secs[i], target.new_vf)
        accepted = _swap_if_better(old_path, bak_path, fresh, old_rgb)
        if accepted is not None:
            updated[i] = accepted


def _is_chat_run(bufs: Sequence[bytes], bounds: Tuple[int, int]) -> bool:
    """Return True when rendered crop appears to frame green YouTube LiveChat bars."""
    lo, hi = bounds
    greens = [green_chat_fraction(b) for b in bufs[lo:hi]]
    return bool(greens) and (sum(greens) / len(greens) >= _CHAT_GREEN_MEAN_FLOOR or max(greens) >= _CHAT_GREEN_MAX_FLOOR)


def _run_needs_reprobe(bufs: Sequence[bytes], deltas: Sequence[float], bounds: Tuple[int, int]) -> bool:
    """Return True when rendered frames look dead, blank-face, UI-covered, or LiveChat-barred."""
    lo, hi = bounds
    return _is_dead_run(deltas, bounds) or _is_chat_run(bufs, bounds) or any(is_suspect_tight_crop(b, _BLANK_FACE_TONE_CEIL) for b in bufs[lo:hi])


def _select_runs_to_check(
    runs: Sequence[Tuple[int, int]],
    deltas: Sequence[float],
    bufs: Sequence[bytes],
) -> List[Tuple[int, int]]:
    """Pick broken runs plus isolated 1-frame islands next to them."""
    bad_idx = {i for i, r in enumerate(runs) if _run_needs_reprobe(bufs, deltas, r)}
    if not bad_idx:
        return []
    keep = set(bad_idx) | {i for i, r in enumerate(runs) if r[1] - r[0] == 1 and ((i - 1) in bad_idx or (i + 1) in bad_idx)}
    ranked = sorted((runs[i] for i in keep), key=lambda r: (-(r[1] - r[0]), r[0]))
    return sorted(ranked[:_MAX_RUN_REPROBES], key=lambda r: r[0])


def _apply_segment_reprobes(
    req: Any,
    updated: List[Tuple[str, Path, str, str]],
    to_check: Sequence[Tuple[int, int]],
    plan_and_bufs: Tuple[ReprobePlan, Sequence[bytes]],
) -> List[Tuple[str, Path, str, str]]:
    """Re-probe each flagged slice and overwrite only frames whose box changed."""
    plan, bufs = plan_and_bufs
    frame_secs = [_frame_sec(f, plan.secs[min(i, len(plan.secs) - 1)]) for i, f in enumerate(updated)]
    layout_fn = getattr(req, "layout_fn", None) or detect_obs_layout
    for lo, hi in to_check:
        mid_sec = float(frame_secs[(lo + hi) // 2])
        layout = layout_fn(req.source, WindowBounds(max(0.0, mid_sec - 2.0), mid_sec + 4.0), preferred="auto")
        new_box = layout.webcam_box if layout else None
        if new_box is not None and not _same_box(new_box, plan.initial_box):
            _rerender_segment(req, updated, _RerenderTarget(frame_secs, (lo, hi), plan.vf_fn(new_box)), (plan, bufs))
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
    return _apply_segment_reprobes(req, list(frames), to_check, (plan, bufs))
