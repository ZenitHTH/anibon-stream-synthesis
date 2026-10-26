"""Timestamp pruning and gap filling for Pass 2 summarizer."""
from __future__ import annotations

from typing import List, Optional, Tuple

from common.config import (
    DEFAULT_TEMPERATURE,
    PRUNE_MAX_TOKENS,
    PRUNE_MIN_INPUT,
    PRUNE_TARGET_MAX,
    PRUNE_TARGET_MIN,
    PRUNE_TIMEOUT_SEC,
)
from common.lmstudio import call_local
from common.time import parse_ts


def _find_gap_candidate(
    sorted_ts: List[int], all_tuples: List[Tuple[int, str]], selected: dict, max_gap: int
) -> Optional[Tuple[int, str]]:
    """Find the best intermediate timestamp candidate to bridge a gap exceeding max_gap."""
    for i in range(len(sorted_ts) - 1):
        t1, t2 = sorted_ts[i], sorted_ts[i + 1]
        if t2 - t1 > max_gap:
            mid = (t1 + t2) // 2
            cands = [(abs(t - mid), t, s) for t, s in all_tuples if t1 < t < t2 and t not in selected]
            if cands:
                cands.sort(key=lambda x: x[0])
                return cands[0][1], cands[0][2]
    return None


def fill_pruned_gaps(
    kept_stamps: List[str], all_stamps: List[str], max_gap_sec: int = 600
) -> List[str]:
    """Guarantee no gaps > max_gap_sec between consecutive pruned timestamps."""
    if not kept_stamps or not all_stamps:
        return kept_stamps
    kept_tuples = [(parse_ts(s[:8]), s) for s in kept_stamps if parse_ts(s[:8]) is not None]
    all_tuples = [(parse_ts(s[:8]), s) for s in all_stamps if parse_ts(s[:8]) is not None]
    selected = {t: s for t, s in kept_tuples}
    while True:
        candidate = _find_gap_candidate(sorted(selected.keys()), all_tuples, selected, max_gap_sec)
        if not candidate:
            break
        selected[candidate[0]] = candidate[1]
    return [selected[t] for t in sorted(selected.keys())]


def _build_prune_prompt(stamps: List[str], target: int) -> str:
    """Build pruning instruction prompt for local LLM."""
    return f"""Below are {len(stamps)} livestream timestamps. Select ONLY the ~{target} most essential ones:
topic starts/pivots, official news/releases, key gameplay milestones, core conclusions, the stream ending.
Drop repeats of the same talking point, casual banter, and micro-talk (e.g. offhand remarks on translation or minor side-comments lasting only a few sentences).
Wrap/favor timestamps that represent the consolidated topic rather than fragmented micro-steps.
Copy selected lines EXACTLY, one per line, chronological, nothing else.

{"\n".join(stamps)}"""


def _extract_kept_stamps(content: str, source_set: set) -> List[str]:
    """Parse verbatim timestamps returned by LLM against source timestamps."""
    kept_lines = []
    seen = set()
    for line in content.splitlines():
        l = line.strip()
        if l in source_set and l not in seen:
            seen.add(l)
            kept_lines.append(l)
    return kept_lines


def _ensure_bookend_stamps(kept_lines: List[str], stamps: List[str]) -> List[str]:
    """Ensure first, last, and [Ending] timestamps are preserved in kept list."""
    seen = set(kept_lines)
    if stamps[0] not in seen:
        seen.add(stamps[0])
        kept_lines.append(stamps[0])
    if stamps[-1] not in seen:
        seen.add(stamps[-1])
        kept_lines.append(stamps[-1])
    for s in stamps:
        if "[Ending]" in s and s not in seen:
            seen.add(s)
            kept_lines.append(s)
    return kept_lines


def prune_essential(
    endpoint: str,
    model: str,
    stamps: List[str],
    temperature: float = DEFAULT_TEMPERATURE,
    min_input: int = PRUNE_MIN_INPUT,
) -> List[str]:
    """Filter timestamps to ~40-60 essential ones via local LLM before part grouping."""
    if not stamps or len(stamps) <= min_input:
        return stamps
    target = max(PRUNE_TARGET_MIN, min(PRUNE_TARGET_MAX, len(stamps) // 4))
    prompt = _build_prune_prompt(stamps, target)
    print(f"[prune] Calling local model to prune {len(stamps)} timestamps to ~{target} essential ones...")
    try:
        content = call_local(endpoint, model, prompt, PRUNE_MAX_TOKENS, temperature, PRUNE_TIMEOUT_SEC)
        kept_lines = _extract_kept_stamps(content, set(stamps))
        if len(kept_lines) < target // 2:
            print(f"[prune] Warning: model returned only {len(kept_lines)} valid stamps (target {target}). Falling back to full list.")
            return stamps
        kept_lines = _ensure_bookend_stamps(kept_lines, stamps)
        result = sorted(fill_pruned_gaps(kept_lines, stamps, max_gap_sec=600), key=lambda l: parse_ts(l[:8]))
        print(f"[prune] {len(stamps)} -> {len(result)}")
        return result
    except Exception as e:
        print(f"[prune] Warning: local model pruning failed ({e}). Falling back to full list.")
        return stamps
