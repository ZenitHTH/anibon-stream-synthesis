"""Prompt templates and response parsing for Pass 2 local summarizer."""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

from common.time import parse_ts
from process.caveman import clean_caveman_text


def _normalize_summary_connectors(summary: str) -> str:
    """Replace literal ' + ' connectors and strip LLM self-evaluation artifacts."""
    text = clean_caveman_text(" ".join(summary.split()))
    if " + " not in text:
        return text
    parts = [p.strip() for p in text.split(" + ") if p.strip()]
    if len(parts) <= 1:
        return text.replace(" + ", " ")
    if len(parts) == 2:
        return f"{parts[0]} และ{parts[1]}"
    return ", ".join(parts[:-1]) + f" และ{parts[-1]}"


def build_summarizer_prompt(stamps: List[str]) -> str:
    """Construct prompt for local LLM part partitioning and summary generation."""
    n = len(stamps)
    numbered_list = "\n".join(f"[{i+1:03d}] {s}" for i, s in enumerate(stamps))
    min_parts = max(4, math.ceil(n / 18)) if n > 0 else 4
    max_parts = max(6, math.ceil(n / 12)) if n > 0 else 6
    first_ts = stamps[0][:8] if stamps else "00:00:00"
    return f"""\
You are an expert livestream editor for Anibon Official.
Below are {n} chronological timestamps (indexed [001] to [{n:03d}]) from a livestream by Pu Boat.

Divide these {n} timestamps into {min_parts} to {max_parts} cohesive macro-thematic Parts.

PART BOUNDARY & SIZE CONTRACT (REQUIRED):
1. Target Part Count: {min_parts} to {max_parts} Parts total.
2. Line Count Per Part: Every Part MUST enclose between 4 and 18 timestamps (strictly <= 20 lines per part).
   - Part 1 MUST start at [001] ({first_ts}) and enclose at least the first 4 timestamps (do NOT start Part 2 at [002], which leaves Part 1 as a 1-line orphan).
   - Group related episodes/discussions of a series (e.g. Lanterns Series review, DC), gaming sessions, or political critiques together within the <= 20 lines per part cap.
   - SAME-FRANCHISE TAIL GROUPING: Keep closing news, project announcements, or wrap-up remarks of the same franchise/topic (เช่น ข่าวต่อเนื่องหรือประกาศท้ายเรื่องของแฟรนไชส์เดียวกัน) at the END of that Part. Start Part K+1 at the opening break of the NEXT franchise/topic (never strand the last stamp of Topic X as `[start]` of Topic Y's Part).
3. Header-Content Alignment (STRICT BOUNDARY FENCE): The Summary for Part K MUST describe ONLY the timestamps enclosed within Part K's own `Range: [start]-[end]`. NEVER peek across the fence into Part K+1 or Part K-1 or pull a topic/game name from an adjacent Part into Part K's header!
4. Sequential Integer Numbering: Number parts sequentially as integers ONLY (Part 1, Part 2, Part 3...).

CAVEMAN SUMMARY HEADER RECIPE (8-15 words / under 80 Thai characters):
`<Primary Activity/Topic 1>, <Secondary Topic 2> และ <Key Highlight/Takeaway>`
- Start directly with the action verb or topic noun (ห้ามขึ้นต้นหัวข้อสรุปด้วยคำว่า 'ปู่โบ๊ต').
- Keep specific proper nouns (game titles, character names, series names); never use vague pronouns ("เกมนี้", "เรื่องนั้น").
- PURE THAI OUTPUT ONLY: Output ONLY the Thai summary text on the `Summary:` line. NEVER append English translations in parentheses (e.g. `(Analyze ...)`), reasoning notes, or self-evaluation grades (`- Good.`, `- OK.`).

Format strictly as:
Part 1: {first_ts}
Range: [001]-[010]
Summary: [Short Thai Summary 1 concise sentence on one line]

Part 2: HH:MM:SS
Range: [011]-[025]
Summary: [Short Thai Summary 1 concise sentence on one line]

TIMESTAMPS:
{numbered_list}
"""


_PART_BLOCK_RE = re.compile(
    r"Part\s+(\d+)[:\s]+(\d{2}:\d{2}:\d{2})"
    r"((?:(?!\n\s*Part\s+\d+).)*?)"
    r"Summary[:\s]+(.+?)(?=\n\s*\n|\n\s*Part\s+\d+|\Z)",
    flags=re.DOTALL,
)
_RANGE_INDEX_RE = re.compile(r"Range[:\s]+\[?(\d+)\]?\s*[-–]\s*\[?(\d+)\]?")
_HHMMSS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _resolve_part_start(p_start: str, middle_block: str, stamps: Optional[List[str]]) -> str:
    """Authoritatively recover start timestamp from Range index when available."""
    if not stamps:
        return p_start
    rm = _RANGE_INDEX_RE.search(middle_block)
    if not rm:
        return p_start
    start_idx = int(rm.group(1))
    if 1 <= start_idx <= len(stamps):
        candidate = stamps[start_idx - 1][:8]
        if _HHMMSS_RE.match(candidate):
            return candidate
    return p_start


def parse_summarizer_matches(
    content: str, stamps: Optional[List[str]] = None
) -> List[Tuple[str, str, str]]:
    """Extract valid ordered (part_num, start_ts, summary) tuples from LLM output."""
    raw_matches = _PART_BLOCK_RE.findall(content)
    seen_nums, prev_sec, matches = set(), -1, []
    for p_num, p_start, middle_block, p_sum in raw_matches:
        resolved_start = _resolve_part_start(p_start, middle_block, stamps)
        sec = parse_ts(resolved_start)
        if p_num in seen_nums or sec <= prev_sec:
            continue
        seen_nums.add(p_num)
        prev_sec = sec
        matches.append((p_num, resolved_start, _normalize_summary_connectors(p_sum)))
    return matches

