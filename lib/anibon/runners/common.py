"""
anibon.runners.common — Shared utilities for chunk inference and multimodal frame grounding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from anibon.config import (
    EVAL_BATCH_SIZE,
    MAX_CHUNK_FRAMES,
    MULTIMODAL_TIMEOUT_SEC,
    SCENE_DELTA_THRESHOLD,
)
from anibon.lmstudio import call_local
from anibon.multimodal import (
    build_multimodal_content,
    call_multimodal,
    prepare_storyboard_slides,
    sample_chunk_keyframes,
)


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
            print(f"\n[multimodal] fallback to text-only for {chunk_idx}: {ex}", flush=True)

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
            print(f"[multimodal] Enabled: Grounding chunks with Storyboard keyframes from {slides_dir.name}")
        else:
            print("[multimodal] Warning: No storyboard slides found in workspace/frames, falling back to text-only mode.")
            is_multimodal = False

    return is_multimodal, slides_dir, tiles_dir
