"""
anibon.runners.common — Shared utilities for chunk inference and multimodal frame grounding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from common.config import (
    EVAL_BATCH_SIZE,
    MAX_CHUNK_FRAMES,
    MULTIMODAL_TIMEOUT_SEC,
    PASS1_WEBCAM_FRAMES,
    SCENE_DELTA_THRESHOLD,
    WEBCAM_CORNER,
)
from common.lmstudio import call_local
from common.log import log_info, log_warn
from process.multimodal import (
    build_multimodal_content,
    call_multimodal,
    prepare_storyboard_slides,
    sample_chunk_keyframes,
)
from process.multimodal_situations import collect_situational_candidates, select_spaced_seconds
from process.reaction_io import resolve_reaction_source
from process.runners.dynamic_chunk import _balance_dynamic_chunk_frames
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames


def _get_runtime_hook(hook_name: str, fallback: any) -> any:
    """Retrieve runtime hook from process_chunks_local if monkeypatched in tests."""
    pcl = sys.modules.get("process_chunks_local")
    return getattr(pcl, hook_name, fallback) if pcl else fallback


def _compute_chunk_time_window(chunk: dict, ch_num: int) -> Tuple[int, int]:
    """Calculate starting and ending second offsets for a chunk."""
    items = chunk.get("items", [])
    st_sec = items[0].get("start", 0) if items else ch_num * 270
    en_sec = items[-1].get("start", 0) + items[-1].get("duration", 5) if items else st_sec + 270
    return int(st_sec), int(en_sec)


def _sample_chunk_multimodal_frames(
    chunk: dict,
    ch_num: int,
    slides_dir: Optional[Path],
    tiles_dir: Path,
    rolling_summary: str,
    args: Optional[argparse.Namespace],
) -> list:
    """Extract storyboard keyframe image buffers for chunk grounding."""
    if not slides_dir:
        return []

    st_sec, en_sec = _compute_chunk_time_window(chunk, ch_num)
    items = chunk.get("items", [])
    est_text_tokens = (len(rolling_summary) + len(chunk.get("text", ""))) // 4 + 800

    scene_dedup = not getattr(args, "no_scene_dedup", False) if args else True
    delta_threshold = getattr(args, "scene_delta_threshold", SCENE_DELTA_THRESHOLD) if args else SCENE_DELTA_THRESHOLD
    max_chunk_frames = getattr(args, "max_chunk_frames", None) if args else None
    eval_batch_size = getattr(args, "eval_batch_size", EVAL_BATCH_SIZE) if args else EVAL_BATCH_SIZE

    sample_fn = _get_runtime_hook("sample_chunk_keyframes", sample_chunk_keyframes)
    return sample_fn(
        st_sec,
        en_sec,
        slides_dir,
        tiles_dir,
        items=items,
        num_frames=max_chunk_frames,
        scene_dedup=scene_dedup,
        delta_threshold=delta_threshold,
        text_tokens=est_text_tokens,
        eval_batch_size=eval_batch_size,
    )


def _call_chunk_model(
    endpoint: str,
    model: str,
    prompt: str,
    keyframes: list,
    max_tokens: int,
    temperature: float,
    chunk_idx: str,
    args: Optional[argparse.Namespace],
) -> str:
    """Execute model text or vision inference with graceful text fallback."""
    api_key = getattr(args, "api_key", None) if args else None
    call_multi_fn = _get_runtime_hook("call_multimodal", call_multimodal)
    call_local_fn = _get_runtime_hook("call_local", call_local)

    if keyframes:
        try:
            content_list = build_multimodal_content(prompt, keyframes)
            return call_multi_fn(
                endpoint, model, content_list, max_tokens, temperature,
                timeout=MULTIMODAL_TIMEOUT_SEC, api_key=api_key,
            )
        except Exception as ex:
            log_warn("multimodal", f"{chunk_idx} fallback to text-only ({ex})")

    return call_local_fn(endpoint, model, prompt, max_tokens, temperature, api_key=api_key)


def _init_multimodal_grounding(
    workspace: Path,
    args: Optional[argparse.Namespace],
) -> Tuple[bool, Optional[Path], Path]:
    """Initialize storyboard keyframes directory if multimodal mode is enabled."""
    is_multimodal = bool(args and (getattr(args, "multimodal_chunks", False) or getattr(args, "multimodal", False)))
    slides_dir = None
    tiles_dir = workspace / "frames" / "chunk_tiles"

    if is_multimodal:
        video_url = getattr(args, "video_url", None) if args else None
        prep_slides_fn = _get_runtime_hook("prepare_storyboard_slides", prepare_storyboard_slides)
        slides_dir = prep_slides_fn(workspace, video_url=video_url)
        if slides_dir:
            tiles_dir.mkdir(parents=True, exist_ok=True)
            log_info("multimodal", f"grounding enabled from {slides_dir.name}")
        else:
            log_warn("multimodal", "no storyboard slides found; falling back to text-only")
            is_multimodal = False

    return is_multimodal, slides_dir, tiles_dir


def _init_webcam_source(
    workspace: Path,
    args: Optional[argparse.Namespace],
) -> Optional[Path | str]:
    """Resolve optional video source once for Pass 1 webcam closeup grounding."""
    if not args or not getattr(args, "reaction_verify", False):
        return None
    src = resolve_reaction_source(workspace, args)
    if src:
        log_info("webcam", "Pass 1 webcam closeups enabled alongside storyboard frames")
    return src


def _pick_chunk_webcam_secs(chunk: dict, max_frames: int) -> Tuple[int, ...]:
    """Select spaced situational/emotion timestamps inside chunk for webcam sampling."""
    items = chunk.get("items", [])
    if not items or max_frames <= 0:
        return ()
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + 5
    cands = collect_situational_candidates(items, lo, hi, pinned_only=False)
    return tuple(sorted(select_spaced_seconds(cands, [], min_spacing=15, max_count=max_frames)))


def _sample_chunk_webcam_grounding(
    workspace: Path,
    chunk: dict,
    source: Optional[Path | str],
    args: Optional[argparse.Namespace],
) -> list:
    """Extract Pass 1 webcam closeups for chunk when video source is available."""
    if not source:
        return []
    pref = getattr(args, "webcam_corner", WEBCAM_CORNER) if args else WEBCAM_CORNER
    secs = _pick_chunk_webcam_secs(chunk, PASS1_WEBCAM_FRAMES)
    req = ChunkWebcamRequest(workspace=workspace, source=source, chunk=chunk, target_secs=secs, preferred=pref, max_frames=PASS1_WEBCAM_FRAMES)
    try:
        return sample_chunk_webcam_frames(req)
    except Exception as ex:
        log_warn("webcam", f"Pass 1 webcam sample skipped ({ex})")
        return []
