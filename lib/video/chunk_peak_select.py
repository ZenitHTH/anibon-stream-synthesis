"""Multi-modal algorithmic reaction-peak detection for dynamic webcam frame sampling."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from video.audio_envelope import extract_chunk_rms_bins
from video.motion_types import WindowBounds

_CHAT_TS_RE = re.compile(r"^\[(\d+):(\d{2}):(\d{2})\]")
_BIN_SEC: int = 10
_MIN_AUDIO_Z: float = 1.8
_PROMOTE_AUDIO_Z: float = 2.5
_MIN_PEAK_GAP: int = 15


@dataclass(frozen=True)
class PeakSearchInput:
    """Inputs for locating multi-modal reaction peaks within a single transcript chunk."""

    workspace: Path
    items: Sequence[dict]
    audio_source: Optional[Path | str]
    sb_spikes: Tuple[int, ...] = ()


def _chunk_bounds(items: Sequence[dict]) -> Optional[Tuple[int, int]]:
    """Compute inclusive (lo, hi) second range from chunk transcript items."""
    if not items:
        return None
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + 5
    return (lo, max(lo + 5, hi))


def _load_livechat_bins(workspace: Path, bounds: Tuple[int, int]) -> Dict[int, int]:
    """Count livechat messages in 10s bins overlapping chunk bounds."""
    lc_dir = Path(workspace) / "livechat"
    if not lc_dir.is_dir():
        return {}
    lo, hi = bounds
    bins: Dict[int, int] = {}
    for lc_file in sorted(lc_dir.glob("livechat_chunk_*.txt")):
        for line in lc_file.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _CHAT_TS_RE.match(line)
            if not m:
                continue
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            if (lo - 10) <= sec <= (hi + 30):
                b = (sec // _BIN_SEC) * _BIN_SEC
                bins[b] = bins.get(b, 0) + 1
    return bins


def _chat_echo_bonus(bins: Dict[int, int], sec: int) -> float:
    """Measure lagged viewer chat burst ratio in [sec+3 .. sec+25] over chunk median."""
    if not bins:
        return 0.0
    counts = sorted(bins.values())
    med = max(1, counts[len(counts) // 2])
    post = sum(bins.get(b, 0) for b in range(((sec + 3) // _BIN_SEC) * _BIN_SEC, sec + 26, _BIN_SEC))
    ratio = (post / 2.0) / float(med)
    return min(3.0, max(0.0, ratio - 1.2))


def _collect_audio_candidates(
    audio_source: Optional[Path | str], bounds: Tuple[int, int], chat_bins: Dict[int, int]
) -> Tuple[List[Tuple[float, int]], float]:
    """Score 1s audio shout-onset candidates plus delayed livechat reaction echoes."""
    if not audio_source:
        return [], 0.0
    bins = extract_chunk_rms_bins(audio_source, WindowBounds(bounds[0], bounds[1]), bin_sec=1.0)
    if not bins:
        return [], 0.0
    max_z = max(z for _, z, _ in bins)
    cands: List[Tuple[float, int]] = []
    for sec, z, onset in bins:
        if z < _MIN_AUDIO_Z:
            continue
        score = z + 0.5 * onset + 0.8 * _chat_echo_bonus(chat_bins, sec)
        cands.append((score, sec))
    return cands, max_z


def _pick_spaced(
    candidates: Sequence[Tuple[float, int]],
    existing: Sequence[int],
    min_spacing: int,
    max_count: int,
) -> List[int]:
    """Select high-priority seconds respecting minimum spacing up to max_count."""
    chosen = list(existing)
    for _, sec in candidates:
        if len(chosen) >= max_count:
            break
        if all(abs(sec - prev) >= min_spacing for prev in chosen):
            chosen.append(sec)
    return chosen


def detect_chunk_reaction_peaks(
    query: PeakSearchInput, max_peaks: int = 4
) -> Tuple[Tuple[int, ...], float, bool]:
    """Fuse audio RMS onsets, storyboard spikes, and livechat echoes into spaced peaks."""
    bounds = _chunk_bounds(query.items)
    if bounds is None:
        return query.sb_spikes, 0.0, False
    chat_bins = _load_livechat_bins(query.workspace, bounds)
    cands, max_audio_z = _collect_audio_candidates(query.audio_source, bounds, chat_bins)
    for sec in query.sb_spikes:
        cands.append((3.5 + 0.8 * _chat_echo_bonus(chat_bins, sec), sec))
    cands.sort(key=lambda item: (-item[0], item[1]))
    chosen = _pick_spaced(cands, [], min_spacing=_MIN_PEAK_GAP, max_count=max_peaks)
    has_chat_corroborated = any(_chat_echo_bonus(chat_bins, s) >= 0.8 for s_score, s in cands if s_score >= 2.0)
    should_promote = max_audio_z >= _PROMOTE_AUDIO_Z or (max_audio_z >= 2.0 and has_chat_corroborated)
    return tuple(sorted(chosen)), max_audio_z, should_promote


def _fill_even_gaps(chosen: List[int], bounds: Tuple[int, int], max_frames: int) -> List[int]:
    """Top up remaining sample slots evenly across the chunk span."""
    lo, hi = bounds
    step = (hi - lo) / float(max_frames + 1)
    for idx in range(max_frames):
        if len(chosen) >= max_frames:
            break
        sec = lo + int(round((idx + 1) * step))
        if all(abs(sec - prev) >= 8 for prev in chosen):
            chosen.append(sec)
    return chosen


def _seed_spike_slots(
    spikes: Tuple[int, ...], bounds: Tuple[int, int], max_frames: int
) -> List[int]:
    """Place spaced burst offsets around peak reaction seconds within bounds."""
    lo, hi = bounds
    seeds: List[int] = []
    offsets = (0, 2, -2) if max_frames >= 10 else (0, 2)
    for spike in spikes:
        for offset in offsets:
            sec = max(lo, min(hi, spike + offset))
            if all(abs(sec - prev) >= 2 for prev in seeds) and len(seeds) < max_frames:
                seeds.append(sec)
    return seeds


def expand_peak_timestamps(
    spikes: Tuple[int, ...],
    items: Sequence[dict],
    max_frames: int,
    extra_cands: Sequence[Tuple[float, int]] = (),
) -> Tuple[int, ...]:
    """Sample peak onset + immediate follow-through, then fill with cues and even slots."""
    bounds = _chunk_bounds(items)
    if bounds is None or max_frames <= 0:
        return ()
    seeds = _seed_spike_slots(spikes, bounds, max_frames)
    chosen = _pick_spaced(extra_cands, seeds, min_spacing=10, max_count=max_frames)
    if len(chosen) < max_frames:
        chosen = _fill_even_gaps(chosen, bounds, max_frames)
    return tuple(sorted(chosen))


__all__ = [
    "PeakSearchInput",
    "detect_chunk_reaction_peaks",
    "expand_peak_timestamps",
]
