"""Pass 2 local summarizer and YouTube comment block assembly.

Partitions linear timestamp output into cohesive macro-thematic parts
(typically 4–6 parts) based on overarching topic categories.
Viewer navigation and topic cohesion take precedence over artificial byte-cap splitting.
Supports local LLM summarizer pass with heuristic fallback and double-border formatting.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from common.config import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_TEMPERATURE,
    SUMMARIZER_MAX_TOKENS,
    SUMMARIZER_TIMEOUT_SEC,
)
from common.lmstudio import call_local
from common.time import parse_ts
from common.timestamps import deduplicate_consecutive_timestamps
from process.byte_cap import (
    TRANSITION_PATTERNS,
    enforce_byte_cap,
    find_best_boundary,
    generate_part_summary,
)
from process.caveman import clean_caveman_text
from process.prune import fill_pruned_gaps, prune_essential
from process.summarizer_prompt import build_summarizer_prompt, parse_summarizer_matches


def _compute_target_parts(n: int) -> int:
    """Determine target number of macro parts based on total timestamps."""
    if n <= 10:
        return 1
    if n <= 24:
        return 2
    if n <= 60:
        return 3
    if n <= 120:
        return 4
    return 5


def _partition_blocks(stamps: List[str], target_parts: int) -> List[List[str]]:
    """Partition timestamps into blocks snapping to topic transitions."""
    n = len(stamps)
    target_size = max(1, n // target_parts)
    window = max(4, min(15, target_size // 3))
    blocks: List[List[str]] = []
    curr = 0
    while curr < n:
        raw_next = curr + target_size
        if raw_next >= n or (n - raw_next) < (target_size // 2):
            blocks.append(stamps[curr:])
            break
        next_boundary = find_best_boundary(stamps, raw_next, window=window)
        curr_boundary = raw_next if next_boundary <= curr else next_boundary
        blocks.append(stamps[curr:curr_boundary])
        curr = curr_boundary
    return blocks


def _format_part_section(part_num: int, block: List[str], border: str) -> str:
    """Format single part with double borders and clean summary header."""
    cleaned_block = [clean_caveman_text(s) for s in block]
    summary = clean_caveman_text(generate_part_summary(cleaned_block))
    header = f" ส่วนที่ {part_num}: {summary} (⏱ เริ่ม: {cleaned_block[0][:8]})"
    return f"{border}\n{header}\n{border}\n" + "\n".join(cleaned_block)


def assemble_parts(
    all_stamps: List[str],
    workspace: Optional[Path] = None,
    block_size: int = DEFAULT_BLOCK_SIZE,
    deduplicate: bool = True,
    enforce_byte_limit: bool = False,
) -> str:
    """Group timestamps into sequential integer parts with double borders and topic boundary snapping."""
    if not all_stamps:
        return ""
    stamps = (
        deduplicate_consecutive_timestamps(all_stamps, ensure_no_gaps=True)
        if deduplicate
        else sorted(list(dict.fromkeys(all_stamps)), key=lambda l: parse_ts(l[:8]))
    )
    if not stamps:
        return ""

    target_parts = _compute_target_parts(len(stamps))
    blocks = _partition_blocks(stamps, target_parts)
    border = "═" * 57
    parts = [_format_part_section(i, b, border) for i, b in enumerate(blocks, 1)]
    assembled = "\n\n".join(parts)
    return enforce_byte_cap(assembled) if enforce_byte_limit else assembled


def _render_summarized_parts(matches: list, stamps: List[str]) -> Optional[str]:
    """Assemble formatted markdown parts with cleaned Caveman headers and timestamps."""
    if len(matches) < 2:
        return None
    border, rendered, curr_num = "═" * 57, [], 1
    for idx, (p_num, p_start, p_summary) in enumerate(matches):
        start_sec = parse_ts(p_start)
        next_sec = parse_ts(matches[idx + 1][1]) if idx + 1 < len(matches) else 999999
        part_stamps = [s for s in stamps if start_sec <= parse_ts(s[:8]) < next_sec]
        if not part_stamps:
            continue
        header = f" ส่วนที่ {curr_num}: {clean_caveman_text(p_summary)} (⏱ เริ่ม: {p_start})"
        cleaned_stamps = [clean_caveman_text(s) for s in part_stamps]
        rendered.append(f"{border}\n{header}\n{border}\n" + "\n".join(cleaned_stamps))
        curr_num += 1
    return "\n\n".join(rendered) if rendered else None


def run_local_summarizer_pass(
    endpoint: str,
    model: str,
    all_stamps: List[str],
    workspace: Optional[Path] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = SUMMARIZER_MAX_TOKENS,
) -> Optional[str]:
    """Call local LLM to partition timestamps into macro-thematic Parts with Caveman summaries."""
    if not all_stamps:
        return None
    stamps = deduplicate_consecutive_timestamps(all_stamps, ensure_no_gaps=True)
    if not stamps:
        return None

    prompt = build_summarizer_prompt(stamps)
    print("[summarizer] Calling local model for part division & Caveman summaries...")
    try:
        content = call_local(endpoint, model, prompt, max_tokens, temperature, SUMMARIZER_TIMEOUT_SEC)
        matches = parse_summarizer_matches(content)
        return _render_summarized_parts(matches, stamps)
    except Exception as e:
        print(f"[summarizer] Warning: local summarizer call failed ({e}). Falling back to heuristic assembly.")
        return None


__all__ = [
    "clean_caveman_text",
    "generate_part_summary",
    "find_best_boundary",
    "assemble_parts",
    "run_local_summarizer_pass",
    "enforce_byte_cap",
    "prune_essential",
    "fill_pruned_gaps",
    "TRANSITION_PATTERNS",
]
