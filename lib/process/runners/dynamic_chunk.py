"""Dynamic Pass 1 storyboard-vs-webcam allocation runner helpers."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from chunk.state import load_chunk_enrichment
from common.config import WEBCAM_CORNER
from common.log import log_warn
from common.time import fmt_ts
from process.multimodal_situations import EMOTION_REACTION_CUES, collect_situational_candidates
from process.reaction_source import resolve_reaction_audio_source
from process.runners.corner_consensus import make_segment_layout_fn, pick_consensus_corner
from video.chunk_peak_select import (
    PeakSearchInput,
    detect_chunk_reaction_peaks,
    expand_peak_timestamps,
)
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
from video.dynamic_balance import DynamicPlan, assess_storyboard_webcam_motion, trim_storyboard_frames
from video.live_corner_score import is_live_webcam_stats, measure_corner_stats, score_live_corner
from video.motion_types import FaceBox, WEBCAM_BOX_PRESETS, WindowBounds
from video.obs_layout import _CORNER_KEYS, _probe_full_frames, detect_layout_cuts, detect_obs_layout, split_around_cuts

_LAYOUT_CACHE: Dict[Tuple[str, str, str, int], Optional[FaceBox]] = {}
_AUDIO_SOURCE_CACHE: Dict[Tuple[str, bool], Optional[Path | str]] = {}


def _resolve_chunk_audio_source(
    workspace: Path, source: Optional[Path | str], args: Optional[argparse.Namespace]
) -> Optional[Path | str]:
    """Return local or cached audio stream URL for chunk RMS burst scanning."""
    if source and Path(str(source)).is_file():
        return source
    remote = bool(getattr(args, "remote_snap", False)) if args else False
    key = (str(workspace), remote)
    if key not in _AUDIO_SOURCE_CACHE:
        try:
            _AUDIO_SOURCE_CACHE[key] = resolve_reaction_audio_source(workspace, args) if args else None
        except Exception:
            _AUDIO_SOURCE_CACHE[key] = None
    return _AUDIO_SOURCE_CACHE[key]


def _expand_around_spikes(spikes: Tuple[int, ...], items: list, max_frames: int) -> Tuple[int, ...]:
    """Expand high-motion/audio reaction spikes across chunk timestamps cleanly."""
    if not items or max_frames <= 0:
        return ()
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + 5
    cands = collect_situational_candidates(items, lo, hi, pinned_only=False)
    return expand_peak_timestamps(spikes, items, max_frames, extra_cands=cands)


def _probe_window_seg(source: Path | str, sec: float, key: str):
    """Run one short OBS layout probe centered at sec, guarding exceptions."""
    try:
        return detect_obs_layout(source, WindowBounds(max(0.0, sec - 4.0), sec + 6.0), preferred=key)
    except Exception:
        return None


def _probe_chunk_layout_box(source: Path | str, lo: int, hi: int, key: str) -> Optional[FaceBox]:
    """Resolve chunk OBS corner, re-probing clean span when mid-chunk hits cuts/flashes."""
    span = max(20, hi - lo)
    seg = _probe_window_seg(source, lo + span * 0.5, key)
    if seg is not None and not seg.cut_secs and seg.layout not in ("auto-tracked", "fullscreen", "none"):
        return seg.webcam_box
    cands = [s for t in (lo + span * 0.25, lo + span * 0.75) if (s := _probe_window_seg(source, t, key)) is not None]
    for cand in [s for s in cands if not s.cut_secs and s.layout not in ("auto-tracked", "fullscreen", "none")] + cands:
        if cand.webcam_box is not None and (cand.layout != "fullscreen" or lo < 60):
            return cand.webcam_box
    if seg is None or (seg.layout == "fullscreen" and lo >= 60):
        return None
    return seg.webcam_box


def _clean_probe_frames(source: Path | str, sec: float) -> list[bytes]:
    """Extract cut-free 1fps 48x48 frames around sec for persistent corner ranking."""
    try:
        frames = _probe_full_frames(source, WindowBounds(max(0.0, sec - 4.0), sec + 6.0))
    except Exception:
        return []
    if len(frames) < 2:
        return []
    a, b = split_around_cuts(len(frames), detect_layout_cuts(frames, fps=1.0), fps=1.0)
    return frames[a:b]


def _rank_active_corners(clean: list[bytes], sb_frames: Sequence[tuple]) -> list[tuple[bool, float, FaceBox]]:
    """Rank preset corners that pass live-webcam skin/UI/motion checks without game HUD blowup."""
    scored: list[tuple[bool, float, FaceBox]] = []
    for k in _CORNER_KEYS:
        st = measure_corner_stats(clean, WEBCAM_BOX_PRESETS[k])
        if is_live_webcam_stats(st):
            scored.append((True, score_live_corner(st), st.box))
    return scored


def _pick_persistent_corner(
    source: Path | str, bounds: Tuple[int, int], sb_frames: Sequence[tuple]
) -> Optional[FaceBox]:
    """Select active OBS corner maximizing 1s motion vs 5m scene-churn persistence."""
    lo, hi = bounds
    span = max(20, hi - lo)
    clean = _clean_probe_frames(source, lo + span * 0.5)
    if len(clean) < 5:
        extra = [_clean_probe_frames(source, lo + span * f) for f in (0.25, 0.75)]
        clean = max([clean, *extra], key=len)
    if len(clean) < 2:
        return None
    scored = _rank_active_corners(clean, sb_frames)
    if not scored:
        return None
    pool = [row for row in scored if row[0]] or scored
    return max(pool, key=lambda r: r[1])[2]


def _resolve_chunk_webcam_box(
    workspace: Path,
    source: Path | str,
    items: list,
    args: Optional[argparse.Namespace],
    sb_frames: Sequence[tuple] = (),
    chunk_bounds: Optional[Tuple[int, int]] = None,
) -> Optional[FaceBox]:
    """Resolve per-chunk OBS webcam box using 1s-vs-5m persistence when tiles exist."""
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    key = (pref or "auto").strip().lower()
    if key == "none" or (key != "auto" and key in WEBCAM_BOX_PRESETS):
        return WEBCAM_BOX_PRESETS[key]
    if items:
        lo = int(float(items[0].get("start", 0) or 0))
        hi = int(float(items[-1].get("start", lo) or lo)) + 5
    elif chunk_bounds:
        lo, hi = chunk_bounds
    else:
        lo, hi = 0, 60
    cache_key = (str(workspace), str(source), key, lo * 100000 + hi)
    if cache_key not in _LAYOUT_CACHE:
        box = pick_consensus_corner(source, (lo, hi), sb_frames, _rank_active_corners) if len(sb_frames) >= 2 else None
        _LAYOUT_CACHE[cache_key] = box if box is not None else _probe_chunk_layout_box(source, lo, hi, key)
    return _LAYOUT_CACHE[cache_key]


def _extract_dynamic_webcam(
    workspace: Path,
    chunk: dict,
    source: Path | str,
    box_and_plan: Tuple,
    args: Optional[argparse.Namespace],
) -> list:
    """Sample packed HD webcam storyboard sheets when dynamic plan allocates webcam frames."""
    box, plan, *extra = box_and_plan
    if plan.wc_frames <= 0:
        return []
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    secs = _expand_around_spikes(plan.spike_secs, chunk.get("items", []), plan.wc_frames)
    req = ChunkWebcamRequest(workspace, source, chunk, secs, pref, plan.wc_frames, box, layout_fn=extra[0] if extra else None)
    try:
        return sample_chunk_webcam_frames(req)
    except Exception as ex:
        log_warn("webcam", f"Pass 1 dynamic webcam skipped ({ex})")
        return []


def _enrich_plan_with_peaks(
    workspace: Path,
    items: list,
    sb_frames: list,
    plan_and_audio: Tuple[DynamicPlan, Optional[Path | str]],
    chunk_bounds: Optional[Tuple[int, int]] = None,
) -> Tuple[DynamicPlan, float]:
    """Fold audio RMS bursts and livechat echoes into DynamicPlan, promoting quiet hits."""
    plan, audio_src = plan_and_audio
    peaks, max_z, promote = detect_chunk_reaction_peaks(
        PeakSearchInput(workspace, items, audio_src, plan.spike_secs, chunk_bounds=chunk_bounds)
    )
    eff = peaks or plan.spike_secs
    if plan.tier == "low" and promote:
        return DynamicPlan("medium", min(10, max(len(sb_frames), 1)), 6, plan.mean_mad, eff), max_z
    return DynamicPlan(plan.tier, plan.sb_keep, plan.wc_frames, plan.mean_mad, eff), max_z


def _load_cached_storyboard(workspace: Path, chunk: dict) -> list:
    """Load pre-extracted storyboard screen tiles from enrichment/chunk_NN.json."""
    cid = f"chunk_{int(chunk.get('_idx', 0) or 0):02d}"
    enr = load_chunk_enrichment(workspace, cid)
    frames = []
    for item in enr.get("storyboard_frames") or ():
        if not isinstance(item, dict):
            continue
        p = Path(str(item.get("path", "")))
        if not p.is_file():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        frames.append((str(item.get("ts") or "00:00:00"), p, b64, "STORYBOARD SCREEN"))
    return frames


def _load_cached_enrichment_webcam(workspace: Path, chunk: dict) -> list:
    """Load pre-extracted webcam sheets/frames from enrichment/chunk_NN.json."""
    cid = f"chunk_{int(chunk.get('_idx', 0) or 0):02d}"
    enr = load_chunk_enrichment(workspace, cid)
    cues = [c for c in (enr.get("audio_cues") or ()) if isinstance(c, dict)]
    cue_legend = ", ".join(f"{fmt_ts(int(c.get('sec', 0)))}:{c.get('event_type', 'cue')}" for c in cues)
    frames = []
    for idx, raw_path in enumerate(enr.get("webcam_frames") or ()):
        p = Path(raw_path)
        if not p.is_file():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        sec = int(cues[idx]["sec"]) if idx < len(cues) else (int(cues[0]["sec"]) if cues else int(chunk.get("start_sec", 0) or 0))
        label = f"WEBCAM CLOSEUP (PRE-CHUNK: {cue_legend})" if cue_legend else "WEBCAM CLOSEUP (PRE-CHUNK)"
        frames.append((fmt_ts(sec), p, b64, label))
    return frames


def _balance_dynamic_chunk_frames(
    workspace: Path,
    chunk: dict,
    sb_frames: list,
    source: Optional[Path | str],
    args: Optional[argparse.Namespace],
) -> Tuple[list, list, str]:
    """Send all storyboard and webcam frames untrimmed from enrichment cache or live motion."""
    cached_wc = _load_cached_enrichment_webcam(workspace, chunk)
    if cached_wc:
        return sb_frames, cached_wc, "cached-enrichment"
    if not source:
        return sb_frames, [], "static"
    items = chunk.get("items", [])
    s_sec, e_sec = int(chunk.get("start_sec", 0) or 0), int(chunk.get("end_sec", 0) or 0)
    bounds = (s_sec, e_sec) if e_sec > s_sec else None
    box = _resolve_chunk_webcam_box(workspace, source, items, args, sb_frames=sb_frames, chunk_bounds=bounds)
    has_cue = any(cue in (it.get("text") or "") for it in items for cue in EMOTION_REACTION_CUES)
    base_plan = assess_storyboard_webcam_motion(sb_frames, box, has_emotion_cue=has_cue)
    plan, max_z = _enrich_plan_with_peaks(workspace, items, sb_frames, (base_plan, _resolve_chunk_audio_source(workspace, source, args)), chunk_bounds=bounds)
    layout_fn = make_segment_layout_fn(sb_frames, _rank_active_corners, preferred_box=box) if len(sb_frames) >= 2 else None
    wc_frames = _extract_dynamic_webcam(workspace, chunk, source, (box, plan, layout_fn), args)
    suffix = f",peak_z={max_z:.1f}" if max_z >= 2.0 else ""
    return sb_frames, wc_frames, f"{plan.tier}(mad={plan.mean_mad:.3f}{suffix})"


__all__ = ["_balance_dynamic_chunk_frames", "_expand_around_spikes", "_load_cached_storyboard", "_resolve_chunk_webcam_box"]
