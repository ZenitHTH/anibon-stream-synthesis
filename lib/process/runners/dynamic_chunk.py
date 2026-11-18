"""Dynamic Pass 1 storyboard-vs-webcam allocation runner helpers."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple

from common.config import WEBCAM_CORNER
from common.log import log_warn
from process.multimodal_situations import (
    EMOTION_REACTION_CUES,
    collect_situational_candidates,
    select_spaced_seconds,
)
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
from video.dynamic_balance import DynamicPlan, assess_storyboard_webcam_motion, trim_storyboard_frames
from video.motion_types import FaceBox, WEBCAM_BOX_PRESETS, WindowBounds
from video.obs_layout import detect_obs_layout

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


def _resolve_chunk_webcam_box(
    workspace: Path, source: Path | str, items: list, args: Optional[argparse.Namespace]
) -> Optional[FaceBox]:
    """Resolve and cache OBS webcam box for evaluating storyboard corner motion."""
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    key = (pref or "auto").strip().lower()
    if key == "none":
        return None
    if key != "auto" and key in WEBCAM_BOX_PRESETS:
        return WEBCAM_BOX_PRESETS[key]
    lo = int(float(items[0].get("start", 0) or 0)) if items else 0
    cache_key = (str(workspace), str(source), key, lo // 1800)
    if cache_key in _LAYOUT_CACHE:
        return _LAYOUT_CACHE[cache_key]
    try:
        box = detect_obs_layout(source, WindowBounds(max(0.0, lo - 3.0), lo + 5.0), preferred=key).webcam_box
    except Exception:
        box = None
    _LAYOUT_CACHE[cache_key] = box
    return box


def _extract_dynamic_webcam(
    workspace: Path, chunk: dict, source: Path | str, plan: DynamicPlan, args: Optional[argparse.Namespace]
) -> list:
    """Sample packed webcam storyboard sheets when dynamic plan allocates webcam frames."""
    if plan.wc_frames <= 0:
        return []
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    secs = _expand_around_spikes(plan.spike_secs, chunk.get("items", []), plan.wc_frames)
    req = ChunkWebcamRequest(
        workspace=workspace, source=source, chunk=chunk,
        target_secs=secs, preferred=pref, max_frames=plan.wc_frames,
    )
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
    box = _resolve_chunk_webcam_box(workspace, source, items, args)
    has_cue = any(cue in (it.get("text") or "") for it in items for cue in EMOTION_REACTION_CUES)
    plan = assess_storyboard_webcam_motion(sb_frames, box, has_emotion_cue=has_cue)
    wc_frames = _extract_dynamic_webcam(workspace, chunk, source, plan, args)
    sb_balanced = trim_storyboard_frames(sb_frames, plan.sb_keep) if wc_frames else sb_frames
    return sb_balanced, wc_frames, f"{plan.tier}(mad={plan.mean_mad:.3f})"


__all__ = ["_balance_dynamic_chunk_frames", "_expand_around_spikes", "_resolve_chunk_webcam_box"]
