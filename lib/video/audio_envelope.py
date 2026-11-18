"""Pure-stdlib PCM s16le audio RMS envelope and sudden silence-drop detector."""
from __future__ import annotations

import math
import statistics
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from video.motion_types import WindowBounds


@dataclass(frozen=True)
class AudioBurstMetrics:
    """Audio RMS shout spike and silence-drop telemetry for co-triggering."""

    rms_z_max: float
    shout_sec: Optional[float]
    silence_drop_sec: Optional[float]
    has_audio_trigger: bool


def _pcm_rms_bins(pcm_s16le: bytes, sample_rate: int, bin_sec: float) -> List[float]:
    """Compute normalized [0..1] RMS amplitude per time bin from s16le mono PCM."""
    usable = (len(pcm_s16le) // 2) * 2
    if usable < 2:
        return []
    samples = [v[0] for v in struct.iter_unpack("<h", pcm_s16le[:usable])]
    step = max(1, int(round(sample_rate * bin_sec)))
    bins: List[float] = []
    for start in range(0, len(samples), step):
        chunk = samples[start : start + step]
        if len(chunk) < max(1, step // 2) and bins:
            continue
        rms = math.sqrt(sum(v * v for v in chunk) / len(chunk)) / 32768.0
        bins.append(rms)
    return bins


def _find_silence_drop(rms_bins: List[float], bin_sec: float) -> Optional[float]:
    """Detect sudden drop from active speech into sustained near-silence."""
    win = max(2, int(round(2.0 / max(bin_sec, 0.1))))
    if len(rms_bins) < win + 2:
        return None
    for i in range(win, len(rms_bins) - 1):
        pre_mean = sum(rms_bins[i - win : i]) / win
        if pre_mean >= 0.025 and rms_bins[i] <= 0.25 * pre_mean and rms_bins[i] <= 0.012:
            if rms_bins[i + 1] <= 0.25 * pre_mean and rms_bins[i + 1] <= 0.012:
                return round(i * bin_sec, 3)
    return None


def _score_rms_bins(rms_bins: List[float], bin_sec: float, z_thresh: float) -> AudioBurstMetrics:
    """Compute modified Z-scores and silence-drop timing over RMS bins."""
    if len(rms_bins) < 3:
        return AudioBurstMetrics(0.0, None, None, False)
    med = statistics.median(rms_bins)
    mad = statistics.median([abs(v - med) for v in rms_bins])
    sigma = max(1.4826 * mad, 0.005)
    z_scores = [(v - med) / sigma for v in rms_bins]
    z_max = round(max(z_scores), 3)
    shout_idx = next((i for i, z in enumerate(z_scores) if z >= z_thresh), None)
    shout_sec = round(shout_idx * bin_sec, 3) if shout_idx is not None else None
    silence_drop = _find_silence_drop(rms_bins, bin_sec)
    return AudioBurstMetrics(
        rms_z_max=z_max, shout_sec=shout_sec, silence_drop_sec=silence_drop,
        has_audio_trigger=(z_max >= z_thresh or silence_drop is not None),
    )


def compute_audio_envelope_from_pcm(
    pcm_s16le: bytes, sample_rate: int = 8000, bin_sec: float = 0.5
) -> AudioBurstMetrics:
    """Analyze pure-stdlib s16le PCM bytes into shout and silence-drop metrics."""
    bins = _pcm_rms_bins(pcm_s16le, sample_rate, bin_sec)
    return _score_rms_bins(bins, bin_sec, z_thresh=2.5)


def extract_audio_burst_metrics(
    source: Path | str, bounds: WindowBounds, z_thresh: float = 2.5
) -> AudioBurstMetrics:
    """Decode window audio as 8kHz mono s16le via ffmpeg and score RMS bursts."""
    src = str(source)
    if not src.startswith(("http://", "https://")) and not Path(src).is_file():
        return AudioBurstMetrics(0.0, None, None, False)
    dur = max(0.5, bounds.end_sec - bounds.start_sec)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, bounds.start_sec):.3f}", "-i", src,
           "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=45)
    except (OSError, subprocess.SubprocessError):
        return AudioBurstMetrics(0.0, None, None, False)
    if res.returncode != 0 or not res.stdout:
        return AudioBurstMetrics(0.0, None, None, False)
    return _score_rms_bins(_pcm_rms_bins(res.stdout, 8000, 0.5), 0.5, z_thresh)
