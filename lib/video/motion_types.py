"""Shared immutable dataclasses and OBS webcam presets for reaction kinematics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

REGIME_NAMES: Tuple[str, ...] = (
    "calm_news", "stunned_freeze", "playful_tease",
    "angry", "joy_flex", "shock_burst", "posture_act",
)


@dataclass(frozen=True)
class WindowBounds:
    """Extraction time window and sampling parameters."""

    start_sec: float
    end_sec: float
    fps: float = 2.0
    sample_size: int = 32


@dataclass(frozen=True)
class FaceBox:
    """Normalized [0..1] crop region (x, y, w, h) relative to video frame."""

    x: float
    y: float
    w: float
    h: float
    name: str = "custom"

    def clamped(self) -> FaceBox:
        """Clamp normalized coordinates safely within [0, 1]."""
        x = max(0.0, min(0.98, float(self.x)))
        y = max(0.0, min(0.98, float(self.y)))
        w = max(0.02, min(1.0 - x, float(self.w)))
        h = max(0.02, min(1.0 - y, float(self.h)))
        return FaceBox(x=x, y=y, w=w, h=h, name=self.name)

    def to_ffmpeg_crop(self) -> Optional[str]:
        """Build ffmpeg crop filter string, or None for uncropped full frame."""
        b = self.clamped()
        if b.x <= 0.001 and b.y <= 0.001 and b.w >= 0.998 and b.h >= 0.998:
            return None
        return f"crop=iw*{b.w:.4f}:ih*{b.h:.4f}:iw*{b.x:.4f}:ih*{b.y:.4f}"

    def derive_tight_face(self) -> FaceBox:
        """Map full webcam box W to inner head/face box F."""
        wb = self.clamped()
        return FaceBox(
            wb.x + wb.w * 0.290, wb.y + wb.h * 0.020,
            wb.w * 0.385, wb.h * 0.635, f"inner_{wb.name}",
        ).clamped()


WEBCAM_BOX_PRESETS: Dict[str, Optional[FaceBox]] = {
    "top-right": FaceBox(0.76, 0.00, 0.24, 0.30, "top-right"),
    "mid-right": FaceBox(0.75, 0.33, 0.25, 0.32, "mid-right"),
    "mid-left": FaceBox(0.00, 0.38, 0.22, 0.24, "mid-left"),
    "bottom-right": FaceBox(0.75, 0.70, 0.25, 0.30, "bottom-right"),
    "bottom-left": FaceBox(0.00, 0.70, 0.25, 0.30, "bottom-left"),
    "top-left": FaceBox(0.00, 0.00, 0.24, 0.30, "top-left"),
    "fullscreen": FaceBox(0.00, 0.00, 1.00, 1.00, "fullscreen"),
    "none": None,
}


@dataclass(frozen=True)
class LayoutSegment:
    """Detected OBS webcam layout and cut boundaries for a segment."""

    layout: str
    webcam_box: Optional[FaceBox]
    face_box: Optional[FaceBox]
    cut_secs: Tuple[float, ...] = ()
    clean_start_sec: Optional[float] = None
    clean_end_sec: Optional[float] = None


@dataclass(frozen=True)
class RegimeThresholds:
    """Calibrated 2.0 fps kinematic thresholds ported from verified probe metrics."""

    motion_threshold: float = 0.060
    spike_ratio: float = 2.2
    pose_threshold: float = 0.075
    freeze_vel_ceiling: float = 0.016
    freeze_pose_floor: float = 0.038
    min_freeze_sec: float = 2.0
    angry_mean_vel: float = 0.055
    angry_rms_vel: float = 0.068
    angry_duty_cycle: float = 0.42
    joy_post_vel_floor: float = 0.020
    joy_post_pose_floor: float = 0.055
    posture_w_pose_floor: float = 0.14
    posture_w_peak_floor: float = 0.12
    fps: float = 2.0


@dataclass(frozen=True)
class FaceMotionSample:
    """Per-frame kinematic measurements."""

    idx: int
    rel_sec: float
    abs_sec: float
    ts: str
    vel_step: float
    vel_1s: float
    upper_mad: float
    lower_mad: float
    pose_shift: float
    z_score: float
    motion_score: float


@dataclass(frozen=True)
class KeyframePick:
    """Dynamically chosen keyframe anchored to a motion transition."""

    role: str
    idx: int
    rel_sec: float
    abs_sec: float
    ts: str
    vel_1s: float
    pose_shift: float
    z_score: float


@dataclass(frozen=True)
class MotionRegime:
    """Dual-box classified reaction regime, telemetry, and 4 dynamic keyframes."""

    regime: str
    trigger_vlm: bool
    confidence: float
    onset_rel_sec: float
    onset_abs_sec: float
    onset_ts: str
    peak_rel_sec: float
    peak_abs_sec: float
    peak_ts: str
    webcam_z_max: float
    w_pose_shift: float
    freeze_duration_sec: float
    freeze_drop_ratio: float
    burst_width_sec: float
    keyframes: Tuple[KeyframePick, ...]
    scores: Dict[str, float]
    features: Dict[str, float]
