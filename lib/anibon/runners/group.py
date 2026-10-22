"""
anibon.runners.group — Fixed-window batched group processing runner.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
from pathlib import Path
from typing import List, Optional, Tuple

from anibon.assembly import finalize_and_assemble_timestamps
from anibon.lmstudio import call_local
from anibon.prompts import build_group_prompt
from anibon.runners.common import _get_runtime_hook
from anibon.state import (
    load_chunk_activity,
    load_chunk_file,
    load_chunk_livechat,
    load_chunk_mood,
    load_state,
    save_state,
)
from anibon.time import fmt_ts as _fmt_ts
from anibon.timestamps import is_continuation, parse_timestamps, validate_timestamps


def _load_group_chunks(g_files: List[Path], mappings: Optional[list]) -> List[dict]:
    """Load and index all chunk objects belonging to a group."""
    g_chunks = []
    for cf in g_files:
        try:
            ch = load_chunk_file(cf, mappings=mappings)
            m = re.search(r"chunk_(\d+)", cf.stem)
            ch["_idx"] = int(m.group(1)) if m else 0
            g_chunks.append(ch)
        except Exception as e:
            print(f"[warn] failed to load {cf.name}: {e}", file=sys.stderr)
    return g_chunks


def _execute_group_inference(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    g_start_sec: int,
    g_end_sec: int,
) -> Tuple[List[str], str]:
    """Execute model call for group window and parse/validate timestamps."""
    call_local_fn = _get_runtime_hook("call_local", call_local)
    raw = call_local_fn(endpoint, model, prompt, max_tokens, temperature)
    if is_continuation(raw):
        return [], "CONTINUATION"

    stamps = parse_timestamps(raw, max_stamps=4)
    stamps = validate_timestamps(stamps, g_start_sec, g_end_sec)
    label = f"{len(stamps)} stamp(s)" if stamps else "0 stamps (continuity)"
    return stamps, label


def _extract_group_tail(out_path: Path) -> Optional[str]:
    """Extract trailing timestamp line from previous group markdown output."""
    for line in reversed(out_path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if re.match(r"\d{2}:\d{2}:\d{2}\s*-\s*\[", line):
            return line
    return None


def _format_group_output(
    group_idx: str,
    g_start_sec: int,
    g_end_sec: int,
    stamps: List[str],
) -> str:
    """Format markdown content for group output file."""
    if stamps:
        return f"<!-- {group_idx} | {_fmt_ts(g_start_sec)} – {_fmt_ts(g_end_sec)} -->\n\n" + "\n".join(stamps)
    return f"<!-- {group_idx} | {_fmt_ts(g_start_sec)} – {_fmt_ts(g_end_sec)} | CONTINUATION -->"


def _save_group_loop_state(
    workspace: Path,
    current_group: int,
    total_groups: int,
    all_timestamps: List[str],
    prev_tail: str,
) -> None:
    """Save progress state after processing a single group window."""
    save_state(workspace, {
        "current_group": current_group, "total_groups": total_groups, "all_timestamps": all_timestamps,
        "prev_tail": prev_tail, "phase": "group_loop",
    })


def _persist_group_output(
    out_path: Path,
    group_idx: str,
    g_start_sec: int,
    g_end_sec: int,
    stamps: List[str],
    prev_tail: str,
    all_timestamps: List[str],
    g: int,
    num_groups: int,
    workspace: Path,
) -> str:
    """Save group markdown output and update loop state."""
    if stamps:
        prev_tail = stamps[-1]
        all_timestamps.extend(stamps)

    out_path.write_text(_format_group_output(group_idx, g_start_sec, g_end_sec, stamps) + "\n", encoding="utf-8")
    _save_group_loop_state(workspace, g + 1, num_groups, all_timestamps, prev_tail)
    return prev_tail


def _process_single_group(
    g: int,
    num_groups: int,
    group_size: int,
    chunk_files: List[Path],
    output_dir: Path,
    workspace: Path,
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    signals_map: dict,
    mappings: Optional[list],
    world_identity_dir: Optional[Path],
    glossary: Optional[dict],
    prev_tail: str,
    all_timestamps: List[str],
) -> Tuple[str, bool]:
    """Execute group prompt, inference, and state update for a single group."""
    group_idx = f"group_{g:02d}"
    out_path = output_dir / f"{group_idx}_output.md"

    g_chunks = _load_group_chunks(chunk_files[g * group_size : (g + 1) * group_size], mappings)
    if not g_chunks:
        return prev_tail, False

    g_start_sec = g_chunks[0].get("start_sec", 0)
    g_end_sec = g_chunks[-1].get("end_sec", 0)
    prompt = build_group_prompt(
        g_chunks, g, prev_tail, lang, signals_map, workspace, world_identity_dir,
        livechat_loader=load_chunk_livechat, activity_loader=load_chunk_activity, mood_loader=load_chunk_mood,
        glossary=glossary,
    )
    prompt_tokens = len(prompt) // 4
    print(f"[{group_idx}/{num_groups-1}] chunks {g_chunks[0]['_idx']:02d}..{g_chunks[-1]['_idx']:02d} ~{prompt_tokens} tokens → calling model ...", end=" ", flush=True)

    try:
        stamps, result_label = _execute_group_inference(
            endpoint, model, prompt, max_tokens, temperature, g_start_sec, g_end_sec
        )
        print(result_label)
    except urllib.error.URLError as e:
        print(f"\n[error] endpoint unreachable: {e}", file=sys.stderr)
        _save_group_loop_state(workspace, g, num_groups, all_timestamps, prev_tail)
        sys.exit(1)
    except Exception as e:
        print(f"\n[error] {group_idx}: {e}", file=sys.stderr)
        return prev_tail, False

    prev_tail = _persist_group_output(
        out_path, group_idx, g_start_sec, g_end_sec, stamps, prev_tail,
        all_timestamps, g, num_groups, workspace
    )
    return prev_tail, True


def run_group_mode(
    workspace: Path,
    chunk_files: List[Path],
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    group_size: int,
    signals_map: dict,
    mappings: Optional[list],
    no_resume: bool,
    max_groups: Optional[int],
    no_summarizer_pass: bool,
    block_size: int,
    world_identity_dir: Optional[Path] = None,
    args: Optional[argparse.Namespace] = None,
    glossary: Optional[dict] = None,
) -> None:
    """Group-based execution across fixed windows of chunks."""
    output_dir = workspace / "group_outputs"
    output_dir.mkdir(exist_ok=True)
    if no_resume:
        for stale in output_dir.glob("group_*_output.md"):
            stale.unlink(missing_ok=True)
        (workspace / "anibon_timestamper_state.json").unlink(missing_ok=True)

    state = load_state(workspace)
    all_timestamps: List[str] = state.get("all_timestamps", []) if not no_resume else []
    prev_tail: str = state.get("prev_tail", "") if not no_resume else ""

    total_chunks = len(chunk_files)
    num_groups = (total_chunks + group_size - 1) // group_size

    if args and getattr(args, "multimodal_chunks", False):
        print("[group] Note: Multimodal storyboard chunk analysis is optimized for --mode recursive; running group mode with text context.")
    if not no_resume and all_timestamps:
        print(f"[resume] {len(all_timestamps)} timestamps already recorded")

    groups_processed = 0
    for g in range(num_groups):
        group_idx = f"group_{g:02d}"
        out_path = output_dir / f"{group_idx}_output.md"

        if not no_resume and out_path.exists():
            tail = _extract_group_tail(out_path)
            if tail:
                prev_tail = tail
            print(f"[skip] {group_idx} (output exists)")
            continue

        prev_tail, ok = _process_single_group(
            g=g, num_groups=num_groups, group_size=group_size, chunk_files=chunk_files,
            output_dir=output_dir, workspace=workspace, endpoint=endpoint, model=model, lang=lang,
            max_tokens=max_tokens, temperature=temperature, signals_map=signals_map, mappings=mappings,
            world_identity_dir=world_identity_dir, glossary=glossary, prev_tail=prev_tail,
            all_timestamps=all_timestamps,
        )
        if ok:
            groups_processed += 1
            if max_groups and groups_processed >= max_groups:
                print(f"[pause] Reached --max-groups {max_groups}.")
                break

    print(f"\n[assemble] {len(all_timestamps)} total timestamps collected.")
    finalize_fn = _get_runtime_hook("finalize_and_assemble_timestamps", finalize_and_assemble_timestamps)
    out_md, deduped = finalize_fn(
        workspace=workspace, all_timestamps=all_timestamps, endpoint=endpoint, model=model,
        temperature=temperature, block_size=block_size, no_summarizer_pass=no_summarizer_pass,
        args=args, glossary=glossary,
    )
    save_state(workspace, {"current_group": num_groups, "total_groups": num_groups, "all_timestamps": deduped, "prev_tail": prev_tail, "phase": "complete"})
    print(f"\n✅ Group run complete: {out_md}")
