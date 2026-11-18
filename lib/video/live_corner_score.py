"""Live webcam corner classification and UI false-positive rejection on 48x48 probes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox
from video.obs_layout import _CORNER_KEYS, _crop_rgb_box, _region_mad
from video.pixel_tones import face_tone_fraction, green_chat_fraction

_MIN_LIVE_TONE: float = 0.13
_MAX_CHAT_GREEN: float = 0.06
_MAX_BRIGHT_UI: float = 0.25
_MAX_BLUE_UI: float = 0.22
_MIN_LIVE_MAD: float = 0.004
_CENTER_CAM_BOX = FaceBox(0.22, 0.0, 0.56, 0.68, "fullscreen")
_CENTER_MIN_TONE: float = 0.25
_CENTER_MIN_MAD: float = 0.008


@dataclass(frozen=True)
class CornerStats:
    """Measured skin, UI, green-chat, and motion metrics for one candidate box."""

    box: FaceBox
    mad: float
    tone: float
    green: float
    bright: float
    blue_ui: float


def clipped_bright_fraction(rgb: bytes) -> float:
    """Estimate bright white/neon UI or anime card ratio (max channel > 220)."""
    total = len(rgb) // 3
    if total <= 0:
        return 0.0
    hits = sum(
        1 for i in range(0, total * 3, 3)
        if max(rgb[i], rgb[i + 1], rgb[i + 2]) > 220
    )
    return hits / total


def blue_ui_fraction(rgb: bytes) -> float:
    """Estimate blue/cyan game HUD pixel ratio (b > r + 25 and g > 100)."""
    total = len(rgb) // 3
    if total <= 0:
        return 0.0
    hits = sum(
        1 for i in range(0, total * 3, 3)
        if rgb[i + 2] > rgb[i] + 25 and rgb[i + 1] > 100
    )
    return hits / total


def measure_corner_stats(clean: Sequence[bytes], box: FaceBox, size: int = 48) -> CornerStats:
    """Measure tight-crop motion, skin tone, livechat green, and game UI fractions."""
    tight = box.derive_tight_face()
    crops = [_crop_rgb_box(frame, size, tight) for frame in clean]
    n = max(1, len(crops))
    mad = _region_mad(list(clean), size, tight) if len(clean) >= 2 else 0.0
    tone = sum(face_tone_fraction(c) for c in crops) / n
    green = sum(green_chat_fraction(c) for c in crops) / n
    bright = sum(clipped_bright_fraction(c) for c in crops) / n
    blue_ui = sum(blue_ui_fraction(c) for c in crops) / n
    return CornerStats(box, mad, tone, green, bright, blue_ui)


def is_live_webcam_stats(st: CornerStats) -> bool:
    """Return True when stats match a live talking-head webcam rather than game UI."""
    return (
        st.green < _MAX_CHAT_GREEN
        and st.bright < _MAX_BRIGHT_UI
        and st.blue_ui < _MAX_BLUE_UI
        and st.tone >= _MIN_LIVE_TONE
        and st.mad >= _MIN_LIVE_MAD
    )


def score_live_corner(st: CornerStats) -> float:
    """Score candidate live corner favoring skin purity without letting UI/motion blow up."""
    purity = max(0.0, 1.0 - 2.0 * st.bright - 2.0 * st.blue_ui)
    return min(st.tone, 0.30) * purity + min(st.mad, 0.04) * 0.3


def is_fullscreen_live(clean: Sequence[bytes], size: int = 48) -> bool:
    """Check whether centered fullscreen facecam occupies the frame center."""
    if len(clean) < 2:
        return False
    st = measure_corner_stats(clean, _CENTER_CAM_BOX, size=size)
    return (
        st.tone >= _CENTER_MIN_TONE
        and st.mad >= _CENTER_MIN_MAD
        and st.green < _MAX_CHAT_GREEN
        and st.bright < _MAX_BRIGHT_UI
        and st.blue_ui < _MAX_BLUE_UI
    )


def is_suspect_tight_crop(rgb: bytes, min_tone: float = 0.095) -> bool:
    """Return True when rendered tight-face crop looks blank, UI-covered, or LiveChat-barred."""
    return (
        green_chat_fraction(rgb) >= _MAX_CHAT_GREEN
        or face_tone_fraction(rgb) < min_tone
        or clipped_bright_fraction(rgb) >= _MAX_BRIGHT_UI
        or blue_ui_fraction(rgb) >= _MAX_BLUE_UI
    )


def tight_crop_live_quality(rgb: bytes) -> float:
    """Score rendered crop face clarity minus chat green and game UI leakage."""
    return (
        face_tone_fraction(rgb)
        - 1.2 * green_chat_fraction(rgb)
        - 0.6 * clipped_bright_fraction(rgb)
        - 0.6 * blue_ui_fraction(rgb)
    )


def pick_best_live_corner(
    clean: Sequence[bytes], preferred: Optional[FaceBox] = None
) -> Optional[Tuple[int, float, FaceBox]]:
    """Pick highest-scoring live preset corner in clean frames, respecting continuity."""
    if len(clean) < 2:
        return None
    stats = [measure_corner_stats(clean, WEBCAM_BOX_PRESETS[k]) for k in _CORNER_KEYS]
    live = [(score_live_corner(st), st.box) for st in stats if is_live_webcam_stats(st)]
    if not live:
        return None
    if preferred is not None and preferred.name in WEBCAM_BOX_PRESETS:
        pref_st = measure_corner_stats(clean, preferred)
        if is_live_webcam_stats(pref_st):
            return (len(live), score_live_corner(pref_st), preferred)
    best_sc, best_box = max(live, key=lambda item: item[0])
    return (len(live), best_sc, best_box)


__all__ = [
    "CornerStats",
    "blue_ui_fraction",
    "clipped_bright_fraction",
    "is_fullscreen_live",
    "is_live_webcam_stats",
    "is_suspect_tight_crop",
    "measure_corner_stats",
    "pick_best_live_corner",
    "score_live_corner",
    "tight_crop_live_quality",
]
