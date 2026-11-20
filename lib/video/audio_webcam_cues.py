"""Select spaced webcam inspection timestamps from audio yell and silence cues."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import statistics
from typing import List, Optional, Tuple

from video.audio_envelope import detect_audio_cue_events, extract_raw_rms_bins
from video.motion_types import WindowBounds

_MIN_CUE_GAP: int = 15


def raw_bins_to_z(raw_bins: List[Tuple[int, float]]) -> List[Tuple[int, float, float]]:
    """Convert raw (sec, rms) pairs to (sec, z_score, onset_jump_z)."""
    if len(raw_bins) < 3:
        return []
    vals = [v for _, v in raw_bins]
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    sigma = max(1.4826 * mad, 0.005)
    return [
        (sec, (val - med) / sigma, max(0.0, val - (vals[i - 1] if i > 0 else val)) / sigma)
        for i, (sec, val) in enumerate(raw_bins)
    ]


@dataclass(frozen=True)
class AudioWebcamCue:
    """Audio-triggered webcam inspection moment within a chunk."""

    sec: int
    event_type: str
    score: float
    note: str


def _pick_spaced_cues(
    events: List[Tuple[int, str, float]], max_cues: int
) -> Tuple[AudioWebcamCue, ...]:
    """Sort by descending score and keep cues spaced by at least _MIN_CUE_GAP."""
    ranked = sorted(events, key=lambda item: (-item[2], item[0]))
    chosen: List[AudioWebcamCue] = []
    for sec, kind, score in ranked:
        if len(chosen) >= max_cues:
            break
        if all(abs(sec - c.sec) >= _MIN_CUE_GAP for c in chosen):
            chosen.append(AudioWebcamCue(sec=sec, event_type=kind, score=round(score, 3), note=kind))
    chosen.sort(key=lambda c: c.sec)
    return tuple(chosen)


def select_audio_webcam_cues(
    source: Optional[Path | str], bounds: WindowBounds, max_cues: int = 4
) -> Tuple[AudioWebcamCue, ...]:
    """Detect loud yells, silence drops, and sustained silence to target webcam frames."""
    if not source or max_cues <= 0:
        return ()
    raw_bins = extract_raw_rms_bins(source, bounds, bin_sec=1.0)
    if not raw_bins:
        return ()
    events = detect_audio_cue_events(raw_bins, bin_sec=1.0, z_thresh=2.5)
    return _pick_spaced_cues(events, max_cues)


__all__ = ["AudioWebcamCue", "raw_bins_to_z", "select_audio_webcam_cues"]
