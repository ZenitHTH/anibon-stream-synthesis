"""Pure-stdlib PCM s16le audio RMS envelope and sudden silence-drop detector."""
from __future__ import annotations

import math
import statistics
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

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


def _decode_mono_pcm(source: Path | str, bounds: WindowBounds) -> bytes:
    """Decode bounded audio window as 8kHz mono s16le via ffmpeg."""
    src = str(source)
    if not src.startswith(("http://", "https://")) and not Path(src).is_file():
        return b""
    dur = max(0.5, bounds.end_sec - bounds.start_sec)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, bounds.start_sec):.3f}", "-i", src,
           "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=45)
        return res.stdout if res.returncode == 0 else b""
    except (OSError, subprocess.SubprocessError):
        return b""


def extract_raw_rms_bins(
    source: Path | str, bounds: WindowBounds, bin_sec: float = 1.0
) -> List[Tuple[int, float]]:
    """Decode window audio and return (abs_sec, rms) pairs."""
    pcm = _decode_mono_pcm(source, bounds)
    bins = _pcm_rms_bins(pcm, 8000, bin_sec)
    if not bins:
        return []
    base = int(round(max(0.0, bounds.start_sec)))
    return [(base + int(round(i * bin_sec)), val) for i, val in enumerate(bins)]


def _sustained_silence_starts(raw_bins: List[Tuple[int, float]], bin_sec: float) -> List[int]:
    """Return start seconds for continuous near-silence runs >= 6 seconds."""
    min_bins = max(2, int(round(6.0 / max(bin_sec, 0.1))))
    starts: List[int] = []
    run_start: Optional[int] = None
    run_len = 0
    for sec, val in raw_bins:
        if val <= 0.012:
            run_start = sec if run_len == 0 else run_start
            run_len += 1
            if run_len == min_bins and run_start is not None:
                starts.append(run_start)
        else:
            run_start, run_len = None, 0
    return starts


def _loud_peak_events(
    raw_bins: List[Tuple[int, float]], z_thresh: float
) -> List[Tuple[int, str, float]]:
    """Detect loud RMS Z-score bursts across (abs_sec, rms) bins."""
    vals = [v for _, v in raw_bins]
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    sigma = max(1.4826 * mad, 0.005)
    return [
        (sec, "loud_peak", round((val - med) / sigma, 3))
        for sec, val in raw_bins
        if (val - med) / sigma >= z_thresh
    ]


def detect_audio_cue_events(
    raw_bins: List[Tuple[int, float]], bin_sec: float = 1.0, z_thresh: float = 2.5
) -> List[Tuple[int, str, float]]:
    """Emit (abs_sec, event_type, score) for loud peaks, silence drops, and sustained silence."""
    if len(raw_bins) < 3:
        return []
    events = _loud_peak_events(raw_bins, z_thresh)
    drop_rel = _find_silence_drop([v for _, v in raw_bins], bin_sec)
    if drop_rel is not None:
        drop_idx = min(len(raw_bins) - 1, max(0, int(round(drop_rel / max(bin_sec, 0.1)))))
        events.append((raw_bins[drop_idx][0], "silence_drop", 3.0))
    for sec in _sustained_silence_starts(raw_bins, bin_sec):
        events.append((sec, "sustained_silence", 2.5))
    events.sort(key=lambda item: (item[0], -item[2]))
    return events


def extract_chunk_rms_bins(
    source: Path | str, bounds: WindowBounds, bin_sec: float = 1.0
) -> List[Tuple[int, float, float]]:
    """Return (abs_sec, rms_z_score, onset_jump_z) across bounds for peak finding."""
    pcm = _decode_mono_pcm(source, bounds)
    bins = _pcm_rms_bins(pcm, 8000, bin_sec)
    if len(bins) < 3:
        return []
    med = statistics.median(bins)
    mad = statistics.median([abs(v - med) for v in bins])
    sigma = max(1.4826 * mad, 0.005)
    base = int(round(max(0.0, bounds.start_sec)))
    return [
        (
            base + int(round(i * bin_sec)),
            (val - med) / sigma,
            max(0.0, val - (bins[i - 1] if i > 0 else val)) / sigma,
        )
        for i, val in enumerate(bins)
    ]


def extract_audio_burst_metrics(
    source: Path | str, bounds: WindowBounds, z_thresh: float = 2.5
) -> AudioBurstMetrics:
    """Decode window audio as 8kHz mono s16le via ffmpeg and score RMS bursts."""
    pcm = _decode_mono_pcm(source, bounds)
    if not pcm:
        return AudioBurstMetrics(0.0, None, None, False)
    return _score_rms_bins(_pcm_rms_bins(pcm, 8000, 0.5), 0.5, z_thresh)
