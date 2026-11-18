"""Dynamic screen-storyboard vs webcam-storyboard allocation from storyboard corner motion."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from common.time import parse_ts
from video.face_motion_metrics import compute_frame_delta
from video.motion_types import FaceBox

_HIGH_MAD_FLOOR: float = 0.135
_MED_MAD_FLOOR: float = 0.095
_SPIKE_DELTA_FLOOR: float = 0.240


@dataclass(frozen=True)
class DynamicPlan:
    """Allocated image budget split between screen storyboard and webcam sheets."""

    tier: str
    sb_keep: int
    wc_frames: int
    mean_mad: float
    spike_secs: Tuple[int, ...] = ()


def decode_tile_box(tile_path: Path, box: FaceBox, size: int = 48) -> Optional[bytes]:
    """Crop inner face/webcam box at native tile resolution and scale to RGB24."""
    if not tile_path.is_file():
        return None
    crop = box.to_ffmpeg_crop()
    vf = f"{crop},scale={size}:{size}:flags=area" if crop else f"scale={size}:{size}:flags=area"
    cmd = ["ffmpeg", "-v", "error", "-i", str(tile_path), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        return res.stdout if (res.returncode == 0 and len(res.stdout) == size * size * 3) else None
    except (OSError, subprocess.SubprocessError):
        return None


_decode_tile_corner = decode_tile_box


def plan_dynamic_allocation(
    mean_mad: float, has_emotion_cue: bool = False, avail_slots: int = 16
) -> DynamicPlan:
    """Choose dynamic (storyboard, webcam) frame budget from measured corner motion."""
    if mean_mad >= _HIGH_MAD_FLOOR:
        sb_keep = min(6, max(4, avail_slots // 3))
        return DynamicPlan("high", sb_keep, 12, round(mean_mad, 4), ())
    if mean_mad >= _MED_MAD_FLOOR:
        return DynamicPlan("medium", min(10, avail_slots), 6, round(mean_mad, 4), ())
    wc_target = 4 if has_emotion_cue else 0
    return DynamicPlan("low", min(avail_slots, 16), wc_target, round(mean_mad, 4), ())


def assess_storyboard_webcam_motion(
    sb_frames: Sequence[tuple], webcam_box: Optional[FaceBox], has_emotion_cue: bool = False
) -> DynamicPlan:
    """Measure tight inner-face motion across storyboard tiles and return DynamicPlan."""
    if webcam_box is None or len(sb_frames) < 2:
        fallback = (_MED_MAD_FLOOR + 0.005) if has_emotion_cue else 0.0
        return plan_dynamic_allocation(fallback, has_emotion_cue, max(len(sb_frames), 16))
    face_box = webcam_box.derive_tight_face()
    pairs = [(parse_ts(str(item[0])), decode_tile_box(Path(item[1]), face_box)) for item in sb_frames]
    valid = [(sec, raw) for sec, raw in pairs if sec is not None and raw]
    if len(valid) < 2:
        fallback = (_MED_MAD_FLOOR + 0.005) if has_emotion_cue else 0.0
        return plan_dynamic_allocation(fallback, has_emotion_cue, max(len(sb_frames), 16))
    deltas = [(valid[i][0], compute_frame_delta(valid[i - 1][1], valid[i][1])[0]) for i in range(1, len(valid))]
    mean_mad = sum(d for _, d in deltas) / len(deltas)
    spikes = tuple(s for s, d in sorted(deltas, key=lambda x: x[1], reverse=True) if d >= _SPIKE_DELTA_FLOOR)
    base = plan_dynamic_allocation(mean_mad, has_emotion_cue, avail_slots=max(len(sb_frames), 16))
    return DynamicPlan(base.tier, base.sb_keep, base.wc_frames, base.mean_mad, spikes)


def trim_storyboard_frames(sb_frames: List[tuple], keep_count: int) -> List[tuple]:
    """Subsample screen storyboard frames evenly while preserving first and last."""
    if len(sb_frames) <= max(1, keep_count):
        return list(sb_frames)
    if keep_count <= 1:
        return [sb_frames[0]]
    step = (len(sb_frames) - 1) / float(keep_count - 1)
    idxs = sorted({int(round(i * step)) for i in range(keep_count)})
    return [sb_frames[i] for i in idxs]


__all__ = [
    "DynamicPlan",
    "assess_storyboard_webcam_motion",
    "decode_tile_box",
    "plan_dynamic_allocation",
    "trim_storyboard_frames",
]
