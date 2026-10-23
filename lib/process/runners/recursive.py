"""
anibon.runners.recursive — Dynamic rolling summary topic state-machine runner.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from process.assembly import finalize_and_assemble_timestamps
from common.config import STAMP_COLLISION_SEC
from process.prompts import build_recursive_prompt, load_world_identity_context
from process.runners.common import (
    _call_chunk_model,
    _get_runtime_hook,
    _init_multimodal_grounding,
    _sample_chunk_multimodal_frames,
)
from chunk.state import (
    load_chunk_activity,
    load_chunk_file,
    load_chunk_livechat,
    load_chunk_mood,
    load_state,
    save_state,
)
from common.time import fmt_ts as _fmt_ts, parse_ts as ts_to_sec
from common.timestamps import sanitize_timestamp_line, validate_timestamps


def _reset_recursive_state(workspace: Path, output_dir: Path, no_resume: bool) -> Tuple[List[str], str, str]:
    """Initialize or reset rolling state and cached chunk outputs."""
    output_dir.mkdir(exist_ok=True)
    if no_resume:
        for stale in output_dir.glob("chunk_*.json"):
            stale.unlink(missing_ok=True)
        (workspace / "anibon_timestamper_state.json").unlink(missing_ok=True)

    state = load_state(workspace)
    all_timestamps = state.get("all_timestamps", []) if not no_resume else []
    topic_title = state.get("current_topic_title", "") if not no_resume else ""
    summary = state.get("rolling_summary", "") if not no_resume else ""
    return all_timestamps, topic_title, summary


def _load_cached_chunk_output(out_path: Path, all_timestamps: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Load previously processed chunk results to avoid redundant model inference."""
    try:
        saved_res = json.loads(out_path.read_text(encoding="utf-8"))
        topic = saved_res.get("current_topic_title")
        summary = saved_res.get("rolling_summary")
        stamps = saved_res.get("timestamps") or ([saved_res.get("timestamp")] if saved_res.get("timestamp") else [])
        for st in stamps:
            if st and st not in all_timestamps:
                all_timestamps.append(st)
        return topic, summary
    except Exception:
        return None, None


def _should_skip_cached_chunk(
    out_path: Path,
    no_resume: bool,
    all_timestamps: List[str],
    chunk_idx: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Determine whether a chunk has already been processed and can be skipped."""
    if no_resume or not out_path.exists():
        return False, None, None
    c_topic, c_summary = _load_cached_chunk_output(out_path, all_timestamps)
    if c_topic or c_summary:
        print(f"[skip] {chunk_idx} (already processed)", flush=True)
        return True, c_topic, c_summary
    return False, None, None


def _collect_candidate_stamps(raw_ts: any) -> List[str]:
    """Clean and filter raw timestamp fields from model output."""
    candidates = []
    if isinstance(raw_ts, list):
        for st in raw_ts:
            if st and isinstance(st, str):
                san = sanitize_timestamp_line(st)
                if san:
                    candidates.append(san)
    elif isinstance(raw_ts, str) and raw_ts.strip():
        san = sanitize_timestamp_line(raw_ts)
        if san:
            candidates.append(san)
    return candidates


def _dedup_sorted_stamps(v_ts: List[str]) -> List[str]:
    """Sort timestamps chronologically and filter colliding stamps."""
    v_ts_sorted: List[str] = []
    prev_s = -1
    for s in sorted(v_ts, key=ts_to_sec):
        sec_val = ts_to_sec(s)
        if prev_s == -1 or (sec_val - prev_s) >= STAMP_COLLISION_SEC:
            v_ts_sorted.append(s)
            prev_s = sec_val
    return v_ts_sorted


def _extract_and_sort_chunk_timestamps(
    raw_ts: any,
    chunk: dict,
    new_title: str,
    ch_sum: str,
    is_cont: bool,
) -> List[str]:
    """Validate, deduplicate, and sort timestamp lines within chunk boundaries."""
    candidate_stamps = _collect_candidate_stamps(raw_ts)
    c_start = chunk.get("start_sec", 0)
    c_end = chunk.get("end_sec", 0)
    v_ts = validate_timestamps(candidate_stamps, c_start, c_end)
    v_ts_sorted = _dedup_sorted_stamps(v_ts)

    if not is_cont and not v_ts_sorted:
        fallback_ts = f"{_fmt_ts(c_start)} - [Talk] {new_title or ch_sum}"
        v_ts_sorted = validate_timestamps([fallback_ts], c_start, c_end)

    return v_ts_sorted


def _format_garbled_line(gn: str, chunk_idx: str) -> Optional[str]:
    """Normalize a single garbled note entry into bullet format."""
    if not (isinstance(gn, str) and gn.strip()):
        return None
    val = gn.strip()
    if "@" in val and not val.startswith('"'):
        tok, rest = val.split("@", 1)
        val = f'"{tok.strip()}" @{rest}'
    return f"- {val} ({chunk_idx})"


def _save_chunk_garbled_notes(res: dict, workspace: Path, chunk_idx: str) -> None:
    """Save raw garbled candidate notes for downstream whisper verification."""
    garbled_notes = res.get("garbled_notes", [])
    if not (isinstance(garbled_notes, list) and garbled_notes):
        return

    raw_notes_dir = workspace / "garbled_notes_raw"
    raw_notes_dir.mkdir(exist_ok=True)
    gn_lines = [line for gn in garbled_notes if (line := _format_garbled_line(gn, chunk_idx))]
    if gn_lines:
        (raw_notes_dir / f"{chunk_idx}.txt").write_text(
            "GARBLED_NOTES:\n" + "\n".join(gn_lines) + "\n",
            encoding="utf-8",
        )


def _load_chunk_context(
    chunk_path: Path,
    ch_num: int,
    mappings: Optional[list],
    signals_map: dict,
    workspace: Path,
    world_identity_dir: Optional[Path],
) -> Tuple[Optional[dict], Optional[dict], any, any, any, any]:
    """Load transcript chunk and supplementary contextual feeds."""
    chunk_idx = f"chunk_{ch_num:02d}"
    try:
        chunk = load_chunk_file(chunk_path, mappings=mappings)
    except Exception as e:
        print(f"[warn] failed to load {chunk_path.name}: {e}", file=sys.stderr)
        return None, None, None, None, None, None

    chunk["_idx"] = ch_num
    sig = signals_map.get(chunk_idx)
    lc = load_chunk_livechat(workspace, chunk_idx)
    act = load_chunk_activity(workspace, chunk_idx)
    mood = load_chunk_mood(workspace, chunk_idx)
    wi_ref = load_world_identity_context(sig, world_identity_dir)
    return chunk, sig, lc, act, mood, wi_ref


def _parse_model_chunk_json(raw_text: str) -> Optional[dict]:
    """Extract and parse JSON object from model completion text."""
    jm = re.search(r'(\{[^{}]*"is_continuation"[^{}]*\})', raw_text, re.DOTALL) or re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if not jm:
        print(f"[warn] JSON parse failed, raw: {raw_text[:100]}")
        return None
    try:
        return json.loads(jm.group(1))
    except Exception as e:
        print(f"[warn] JSON decode error: {e}")
        return None


def _update_topic_flow(
    res: dict,
    chunk: dict,
    all_timestamps: List[str],
    current_topic_title: str,
    rolling_summary: str,
) -> Tuple[List[str], bool, str, str]:
    """Update topic state-machine and append sorted timestamps."""
    is_cont = res.get("is_continuation", False)
    ch_sum = res.get("chunk_summary", "")
    up_sum = res.get("updated_summary", "")
    raw_ts = res.get("timestamps") or res.get("timestamp") or res.get("new_timestamp")
    new_title = res.get("new_topic_title", "")

    v_ts_sorted = _extract_and_sort_chunk_timestamps(raw_ts, chunk, new_title, ch_sum, is_cont)

    for stamp in v_ts_sorted:
        all_timestamps.append(stamp)
        label = "📌 SUB-TOPIC:" if is_cont else "👉 MAJOR SHIFT:"
        print(f"{label} {stamp}" + (f" ('{new_title or ch_sum}')" if not is_cont else ""), flush=True)

    if is_cont:
        if not v_ts_sorted:
            print("🔄 CONTINUATION (no stamp)", flush=True)
        rolling_summary = up_sum or ch_sum or rolling_summary
    else:
        if not v_ts_sorted:
            print(f"👉 MAJOR SHIFT (topic: '{new_title or ch_sum}')", flush=True)
        current_topic_title = new_title or ch_sum
        rolling_summary = up_sum or ch_sum

    return v_ts_sorted, is_cont, current_topic_title, rolling_summary


def _persist_chunk_output(
    out_path: Path,
    chunk_idx: str,
    is_cont: bool,
    v_ts_sorted: List[str],
    res: dict,
    rolling_summary: str,
    current_topic_title: str,
    keyframes: list,
) -> None:
    """Save chunk execution output metadata to json file."""
    out_path.write_text(json.dumps({
        "chunk": chunk_idx,
        "is_continuation": is_cont,
        "timestamps": v_ts_sorted,
        "timestamp": (v_ts_sorted[0] if v_ts_sorted else None),
        "garbled_notes": res.get("garbled_notes", []),
        "chunk_summary": res.get("chunk_summary", ""),
        "rolling_summary": rolling_summary,
        "current_topic_title": current_topic_title,
        "keyframe_count": len(keyframes),
        "keyframe_timestamps": [kf[0] for kf in keyframes],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _execute_and_persist_chunk(
    endpoint: str,
    model: str,
    prompt: str,
    keyframes: list,
    max_tokens: int,
    temperature: float,
    chunk_idx: str,
    args: Optional[argparse.Namespace],
    chunk: dict,
    all_timestamps: List[str],
    current_topic_title: str,
    rolling_summary: str,
    workspace: Path,
    out_path: Path,
) -> Tuple[str, str]:
    """Run model inference and persist valid topic and timestamp updates."""
    try:
        raw_text = _call_chunk_model(endpoint, model, prompt, keyframes, max_tokens, temperature, chunk_idx, args)
        res = _parse_model_chunk_json(raw_text)
        if res:
            v_ts_sorted, is_cont, current_topic_title, rolling_summary = _update_topic_flow(
                res, chunk, all_timestamps, current_topic_title, rolling_summary
            )
            _save_chunk_garbled_notes(res, workspace, chunk_idx)
            _persist_chunk_output(
                out_path, chunk_idx, is_cont, v_ts_sorted, res,
                rolling_summary, current_topic_title, keyframes
            )
    except Exception as e:
        print(f"[error] {chunk_idx}: {e}", file=sys.stderr)
    return current_topic_title, rolling_summary


def _process_single_recursive_chunk(
    chunk_path: Path,
    ch_num: int,
    workspace: Path,
    output_dir: Path,
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    signals_map: dict,
    mappings: Optional[list],
    slides_dir: Optional[Path],
    tiles_dir: Path,
    is_multimodal: bool,
    world_identity_dir: Optional[Path],
    glossary: Optional[dict],
    args: Optional[argparse.Namespace],
    all_timestamps: List[str],
    current_topic_title: str,
    rolling_summary: str,
    total_chunks: int,
) -> Tuple[str, str]:
    """Execute inference and topic state-machine update for a single chunk."""
    chunk_idx = f"chunk_{ch_num:02d}"
    out_path = output_dir / f"{chunk_idx}.json"

    chunk, sig, lc, act, mood, wi_ref = _load_chunk_context(
        chunk_path, ch_num, mappings, signals_map, workspace, world_identity_dir
    )
    if not chunk:
        return current_topic_title, rolling_summary

    keyframes = _sample_chunk_multimodal_frames(
        chunk, ch_num, slides_dir if is_multimodal else None, tiles_dir, rolling_summary, args
    )
    prompt = build_recursive_prompt(
        chunk=chunk, current_topic=current_topic_title, rolling_summary=rolling_summary,
        lang=lang, signal=sig, livechat=lc, activity=act, mood=mood,
        world_identity_ref=wi_ref, glossary=glossary, keyframes=keyframes if keyframes else None,
    )

    prompt_tokens = len(prompt) // 4
    kf_info = f" + {len(keyframes)} frames" if keyframes else ""
    print(f"[{chunk_idx}/{total_chunks-1}] ~{prompt_tokens} tokens{kf_info} → calling model ...", end=" ", flush=True)

    return _execute_and_persist_chunk(
        endpoint=endpoint, model=model, prompt=prompt, keyframes=keyframes, max_tokens=max_tokens,
        temperature=temperature, chunk_idx=chunk_idx, args=args, chunk=chunk,
        all_timestamps=all_timestamps, current_topic_title=current_topic_title,
        rolling_summary=rolling_summary, workspace=workspace, out_path=out_path,
    )


def _save_recursive_loop_state(
    workspace: Path,
    chunk_num: int,
    total: int,
    all_timestamps: List[str],
    current_topic_title: str,
    rolling_summary: str,
) -> None:
    """Save progress state after processing a single chunk in recursive loop."""
    save_state(workspace, {
        "current_chunk": chunk_num, "total_chunks": total, "all_timestamps": all_timestamps,
        "current_topic_title": current_topic_title, "rolling_summary": rolling_summary,
        "phase": "recursive_loop",
    })


def _save_recursive_completion_state(
    workspace: Path,
    total: int,
    processed_count: int,
    all_timestamps: List[str],
    current_topic_title: str,
    rolling_summary: str,
    max_chunks: Optional[int],
) -> None:
    """Save final state upon completing or pausing recursive execution."""
    is_finished = (not max_chunks or processed_count >= total)
    save_state(workspace, {
        "current_chunk": total if is_finished else processed_count,
        "total_chunks": total, "all_timestamps": all_timestamps,
        "current_topic_title": current_topic_title, "rolling_summary": rolling_summary,
        "phase": "complete" if is_finished else "paused",
    })


def run_recursive_mode(
    workspace: Path,
    chunk_files: List[Path],
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    signals_map: dict,
    mappings: Optional[list],
    no_resume: bool,
    max_chunks: Optional[int],
    no_summarizer_pass: bool,
    block_size: int,
    world_identity_dir: Optional[Path] = None,
    args: Optional[argparse.Namespace] = None,
    glossary: Optional[dict] = None,
) -> None:
    """Dynamic rolling summary state-machine execution."""
    output_dir = workspace / "recursive_outputs"
    all_timestamps, current_topic_title, rolling_summary = _reset_recursive_state(
        workspace, output_dir, no_resume
    )

    total = len(chunk_files)
    print(f"[recursive] Starting recursive rolling topic state-machine across {total} chunks...")
    if not no_resume and all_timestamps:
        print(f"[resume] Loaded {len(all_timestamps)} timestamps from state (Ongoing Topic: '{current_topic_title}')")

    is_multimodal, slides_dir, tiles_dir = _init_multimodal_grounding(workspace, args)
    processed_count = 0

    for i, chunk_path in enumerate(chunk_files):
        m = re.search(r"chunk_(\d+)", chunk_path.stem)
        ch_num = int(m.group(1)) if m else i
        chunk_idx = f"chunk_{ch_num:02d}"
        out_path = output_dir / f"{chunk_idx}.json"

        skip, c_topic, c_summary = _should_skip_cached_chunk(out_path, no_resume, all_timestamps, chunk_idx)
        if skip:
            current_topic_title = c_topic or current_topic_title
            rolling_summary = c_summary or rolling_summary
            continue

        current_topic_title, rolling_summary = _process_single_recursive_chunk(
            chunk_path=chunk_path, ch_num=ch_num, workspace=workspace, output_dir=output_dir,
            endpoint=endpoint, model=model, lang=lang, max_tokens=max_tokens, temperature=temperature,
            signals_map=signals_map, mappings=mappings, slides_dir=slides_dir, tiles_dir=tiles_dir,
            is_multimodal=is_multimodal, world_identity_dir=world_identity_dir, glossary=glossary,
            args=args, all_timestamps=all_timestamps, current_topic_title=current_topic_title,
            rolling_summary=rolling_summary, total_chunks=total,
        )

        _save_recursive_loop_state(workspace, i + 1, total, all_timestamps, current_topic_title, rolling_summary)
        processed_count += 1
        if max_chunks and processed_count >= max_chunks:
            print(f"[pause] Reached --max-chunks {max_chunks}.")
            break

    print(f"\n[assemble] {len(all_timestamps)} total timestamps collected from topic shifts.")
    finalize_fn = _get_runtime_hook("finalize_and_assemble_timestamps", finalize_and_assemble_timestamps)
    out_md, deduped = finalize_fn(
        workspace=workspace, all_timestamps=all_timestamps, endpoint=endpoint, model=model,
        temperature=temperature, block_size=block_size, no_summarizer_pass=no_summarizer_pass,
        args=args, glossary=glossary,
    )

    _save_recursive_completion_state(
        workspace, total, processed_count, deduped, current_topic_title, rolling_summary, max_chunks
    )
    print(f"\n✅ Recursive run complete: {out_md}")
