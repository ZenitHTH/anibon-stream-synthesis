"""Dynamic Pass 1 storyboard-vs-webcam allocation runner helpers."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from common.config import WEBCAM_CORNER
from common.log import log_warn
from process.multimodal_situations import (
    EMOTION_REACTION_CUES,
    collect_situational_candidates,
    select_spaced_seconds,
)
from process.runners.corner_consensus import make_segment_layout_fn, pick_consensus_corner
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
from video.dynamic_balance import DynamicPlan, assess_storyboard_webcam_motion, decode_tile_box, trim_storyboard_frames
from video.face_motion_metrics import compute_frame_delta
from video.motion_types import FaceBox, WEBCAM_BOX_PRESETS, WindowBounds
from video.obs_layout import _CORNER_KEYS, _probe_full_frames, _region_mad, detect_layout_cuts, detect_obs_layout, split_around_cuts

_LAYOUT_CACHE: Dict[Tuple[str, str, str, int], Optional[FaceBox]] = {}


def _fill_even_slots(chosen: list[int], bounds: Tuple[int, int], target: int) -> list[int]:
    """Top up chosen timestamps evenly across chunk bounds when below target count."""
    lo, hi = bounds
    span = max(1, hi - lo)
    step = max(4, span // (target + 1))
    for i in range(1, target + 2):
        if len(chosen) >= target:
            break
        cand = lo + step * i
        if cand < hi and all(abs(cand - s) >= 4 for s in chosen):
            chosen.append(cand)
    return sorted(chosen[:target])


def _expand_around_spikes(spikes: Tuple[int, ...], items: list, max_frames: int) -> Tuple[int, ...]:
    """Expand high-motion spikes into dense +-3s bursts and top up across chunk."""
    if not items or max_frames <= 0:
        return ()
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + 5
    seeds: list[int] = []
    for spike in spikes:
        for offset in (-3, 0, 3):
            sec = max(lo, min(hi, spike + offset))
            if all(abs(sec - prev) >= 2 for prev in seeds) and len(seeds) < max_frames:
                seeds.append(sec)
    cands = collect_situational_candidates(items, lo, hi, pinned_only=False)
    chosen = select_spaced_seconds(cands, seeds, min_spacing=10, max_count=max_frames)
    if len(chosen) < max_frames:
        chosen = _fill_even_slots(chosen, (lo, hi), max_frames)
    return tuple(sorted(chosen))


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


def _sb_face_mad(sb_frames: Sequence[tuple], face: FaceBox) -> float:
    """Measure 5-minute storyboard churn across up to 16 chunk tiles."""
    raws = [r for x in sb_frames[:16] if (r := decode_tile_box(Path(x[1]), face))]
    if len(raws) < 2:
        return 1.0
    return sum(compute_frame_delta(raws[i - 1], raws[i])[0] for i in range(1, len(raws))) / (len(raws) - 1)


def _rank_active_corners(clean: list[bytes], sb_frames: Sequence[tuple]) -> list[tuple[bool, float, FaceBox]]:
    """Score active preset corners by 1s motion vs 5m scene-churn persistence."""
    scored = []
    for k in _CORNER_KEYS:
        face = WEBCAM_BOX_PRESETS[k].derive_tight_face()
        m1s = _region_mad(clean, 48, face)
        if m1s < 0.012:
            continue
        m5m = _sb_face_mad(sb_frames, face)
        scored.append((m1s < 0.18 and m5m < 0.28, m1s / max(m5m, 0.03), WEBCAM_BOX_PRESETS[k]))
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
) -> Optional[FaceBox]:
    """Resolve per-chunk OBS webcam box using 1s-vs-5m persistence when tiles exist."""
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    key = (pref or "auto").strip().lower()
    if key == "none" or (key != "auto" and key in WEBCAM_BOX_PRESETS):
        return WEBCAM_BOX_PRESETS[key]
    lo = int(float(items[0].get("start", 0) or 0)) if items else 0
    hi = int(float(items[-1].get("start", lo) or lo)) + 5 if items else lo + 60
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


def _balance_dynamic_chunk_frames(
    workspace: Path,
    chunk: dict,
    sb_frames: list,
    source: Optional[Path | str],
    args: Optional[argparse.Namespace],
) -> Tuple[list, list, str]:
    """Dynamically allocate screen vs webcam storyboard frames from corner motion."""
    if not source:
        return sb_frames, [], "static"
    items = chunk.get("items", [])
    box = _resolve_chunk_webcam_box(workspace, source, items, args, sb_frames=sb_frames)
    has_cue = any(cue in (it.get("text") or "") for it in items for cue in EMOTION_REACTION_CUES)
    plan = assess_storyboard_webcam_motion(sb_frames, box, has_emotion_cue=has_cue)
    layout_fn = make_segment_layout_fn(sb_frames, _rank_active_corners) if len(sb_frames) >= 2 else None
    wc_frames = _extract_dynamic_webcam(workspace, chunk, source, (box, plan, layout_fn), args)
    sb_balanced = trim_storyboard_frames(sb_frames, plan.sb_keep) if wc_frames else sb_frames
    return sb_balanced, wc_frames, f"{plan.tier}(mad={plan.mean_mad:.3f})"


__all__ = ["_balance_dynamic_chunk_frames", "_expand_around_spikes", "_resolve_chunk_webcam_box"]
