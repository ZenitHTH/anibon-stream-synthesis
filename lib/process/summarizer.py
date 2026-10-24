"""Pass 2 local summarizer and YouTube comment block assembly.

Partitions linear timestamp output into cohesive macro-thematic parts
(typically 4–6 parts) based on overarching topic categories.
Viewer navigation and topic cohesion take precedence over artificial byte-cap splitting.
Supports local LLM summarizer pass with heuristic fallback and double-border formatting.
"""
import re
from pathlib import Path
from typing import List, Optional

from common.time import parse_ts, fmt_ts
from common.lmstudio import call_local
from common.timestamps import deduplicate_consecutive_timestamps
from common.config import (
    DEFAULT_TEMPERATURE,
    PRUNE_MIN_INPUT,
    PRUNE_TARGET_MIN,
    PRUNE_TARGET_MAX,
    PRUNE_MAX_TOKENS,
    PRUNE_TIMEOUT_SEC,
    SUMMARIZER_MAX_TOKENS,
    SUMMARIZER_TIMEOUT_SEC,
    DEFAULT_BLOCK_SIZE,
    BYTE_CAP_LIMIT,
)


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a clean 2-3 topic summary phrase from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        # Clean speaker prefixes and trailing punctuation (keep action verbs intact)
        clean = re.sub(r"^(ปู่โบ๊ต|ปู่บอร์ด)\s*", "", desc).strip(". ")
        if clean and clean not in topics:
            topics.append(clean)

    if not topics:
        return "สรุปเนื้อหาและบรรยากาศในไลฟ์สตรีม"

    if len(topics) <= 2:
        return " และ ".join(topics)

    t1 = topics[0]
    t2 = topics[len(topics) // 2]
    t3 = topics[-1]
    return f"{t1}, {t2} และ {t3}"


def fill_pruned_gaps(
    kept_stamps: List[str],
    all_stamps: List[str],
    max_gap_sec: int = 600,
) -> List[str]:
    """Guarantee no gaps > max_gap_sec between consecutive pruned timestamps by backfilling intermediate candidates."""
    if not kept_stamps or not all_stamps:
        return kept_stamps

    kept_tuples = [(parse_ts(s[:8]), s) for s in kept_stamps if parse_ts(s[:8]) is not None]
    all_tuples = [(parse_ts(s[:8]), s) for s in all_stamps if parse_ts(s[:8]) is not None]
    selected = {t: s for t, s in kept_tuples}

    while True:
        sorted_ts = sorted(selected.keys())
        gap_found = False
        for i in range(len(sorted_ts) - 1):
            t1, t2 = sorted_ts[i], sorted_ts[i + 1]
            if t2 - t1 > max_gap_sec:
                mid = (t1 + t2) // 2
                cands = [(abs(t - mid), t, s) for t, s in all_tuples if t1 < t < t2 and t not in selected]
                if cands:
                    cands.sort(key=lambda x: x[0])
                    selected[cands[0][1]] = cands[0][2]
                    gap_found = True
                    break
        if not gap_found:
            break
    return [selected[t] for t in sorted(selected.keys())]


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
    prompt = f"""Below are {len(stamps)} livestream timestamps. Select ONLY the ~{target} most essential ones:
topic starts/pivots, official news/releases, key gameplay milestones, core conclusions, the stream ending.
Drop repeats of the same talking point, casual banter, and micro-talk (e.g. offhand remarks on translation or minor side-comments lasting only a few sentences).
Wrap/favor timestamps that represent the consolidated topic rather than fragmented micro-steps.
Copy selected lines EXACTLY, one per line, chronological, nothing else.

{"\n".join(stamps)}"""

    print(f"[prune] Calling local model to prune {len(stamps)} timestamps to ~{target} essential ones...")
    try:
        content = call_local(endpoint, model, prompt, max_tokens=PRUNE_MAX_TOKENS, temperature=temperature, timeout=PRUNE_TIMEOUT_SEC)
        source_set = set(stamps)
        kept_lines = []
        seen = set()
        for line in content.splitlines():
            l = line.strip()
            if l in source_set and l not in seen:
                seen.add(l)
                kept_lines.append(l)

        if len(kept_lines) < target // 2:
            print(f"[prune] Warning: model returned only {len(kept_lines)} valid stamps (target {target}). Falling back to full list.")
            return stamps

        # Always re-add first timestamp, last timestamp, and any [Ending] stamps
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

        # Enforce NO GAPS rule (max 10 min) by backfilling intermediate candidates from original list
        kept_lines = fill_pruned_gaps(kept_lines, stamps, max_gap_sec=600)

        result = sorted(kept_lines, key=lambda l: parse_ts(l[:8]))
        print(f"[prune] {len(stamps)} -> {len(result)}")
        return result
    except Exception as e:
        print(f"[prune] Warning: local model pruning failed ({e}). Falling back to full list.")
        return stamps


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

    # Apply semantic & chronological deduplication first with gap protection
    stamps = deduplicate_consecutive_timestamps(all_stamps, ensure_no_gaps=True)
    if not stamps:
        return None

    raw_list = "\n".join(stamps)
    prompt = f"""\
You are an expert livestream editor for Anibon Official.
Below are {len(stamps)} timestamps from a livestream by Pu Boat.

Divide these timestamps into cohesive, logical macro-thematic Parts based on overarching topic categories (target roughly 4 to 6 Parts total).

CRITICAL GROUPING & CONSOLIDATION RULES:
1. GROUP STRICTLY BY MACRO-THEMATIC ACTIVITY (4–6 PARTS TOTAL):
   - Primary grouping unit is major activity/topic domain:
     * News & Social Critique / Politics
     * Media / Series Review / Watchparty (e.g. Lanterns Series review, DC) - KEEP ALL EPISODES/DISCUSSION OF THE SERIES TOGETHER IN ONE PART.
     * Gaming Session (e.g. Eternal Return, card games)
     * Anime, Manga & Pop-culture critique (e.g. JoJo, One Piece)
     * Stream Closing / Wrap-up
   - Do NOT split on single-tag flickers or passing micro-topics inside the same activity.
   - Do NOT create excessive micro-parts (NEVER create 10+ parts). Aim for 4 to 6 broad parts.
   - Strictly filter out superficial 1-2 sentence off-hand mentions in headers.
   - Hard breaks that require new parts: Stream opening -> first watchparty/talk; Game -> news/donation segment; Talk -> gacha/gaming; Last content -> signing-off.
2. SEQUENTIAL INTEGER NUMBERING ONLY:
   - Prioritize viewer navigation and thematic cohesion over comment byte limits. Keep related discussions unified.
   - Number parts sequentially as integers ONLY (Part 1, Part 2, Part 3, etc.). NEVER create sub-parts like 1.1, 1.2.
   - Consolidation: Do NOT create tiny parts containing only 1-2 timestamps (unless standalone closing/donation).
3. CAVEMAN SUMMARY HEADERS:
   - Punchy Thai summary header (2-3 complete, dense sentences in Thai, active voice, zero fluff, highlighting major drama, news, or gameplay). Write FULL complete sentences—never cut or abbreviate mid-sentence.
   - NEVER drop proper nouns (game titles, character names, people).
   - Never use vague pronouns ("เกมนี้", "เรื่องนั้น"); name the specific title/person.

For each part, specify:
1. The start timestamp where this part begins.
2. A punchy Caveman-style Thai summary header.

Format strictly as:
Part 1: 00:00:00
Summary: [Thai Summary 2-3 complete sentences on one line]

Part 2: HH:MM:SS
Summary: [Thai Summary 2-3 complete sentences on one line]

TIMESTAMPS:
{raw_list}
"""
    print("[summarizer] Calling local model for part division & Caveman summaries...")
    try:
        content = call_local(endpoint, model, prompt, max_tokens, temperature, timeout=SUMMARIZER_TIMEOUT_SEC)
        raw_matches = re.findall(
            r"Part\s+(\d+)[:\s]+(\d{2}:\d{2}:\d{2}).*?Summary[:\s]+(.+?)(?=\n\s*\n|\n\s*Part\s+\d+|\Z)",
            content,
            flags=re.DOTALL,
        )
        seen_nums = set()
        prev_sec = -1
        matches = []
        for p_num, p_start, p_sum in raw_matches:
            sec = parse_ts(p_start)
            if p_num in seen_nums or sec <= prev_sec:
                continue
            seen_nums.add(p_num)
            prev_sec = sec
            matches.append((p_num, p_start, " ".join(p_sum.split())))

        if len(matches) >= 2:
            border = "═" * 57
            rendered_parts = []
            curr_part_num = 1
            for idx, (p_num, p_start, p_summary) in enumerate(matches):
                start_sec = parse_ts(p_start)
                next_start_sec = parse_ts(matches[idx + 1][1]) if idx + 1 < len(matches) else 999999
                part_stamps = [s for s in stamps if start_sec <= parse_ts(s[:8]) < next_start_sec]
                if not part_stamps:
                    continue

                header = f" ส่วนที่ {curr_part_num}: {p_summary.strip()} (⏱ เริ่ม: {p_start})"
                part_text = f"{border}\n{header}\n{border}\n" + "\n".join(part_stamps)
                rendered_parts.append(part_text)
                curr_part_num += 1

            if rendered_parts:
                return "\n\n".join(rendered_parts)
    except Exception as e:
        print(f"[summarizer] Warning: local summarizer call failed ({e}). Falling back to heuristic assembly.")
    return None


TRANSITION_PATTERNS = [
    r"เตรียมเปลี่ยนไปคุย",
    r"สรุปการพูดคุย.*?และเตรียม",
    r"เตรียมเข้าสู่ช่วง",
    r"เตรียมเริ่มเล่นเกม",
    r"เข้าสู่ช่วง",
    r"เตรียมปิดไลฟ์",
]


def find_best_boundary(stamps: List[str], target_idx: int, window: int = 4) -> int:
    """Snap split index to the nearest major topic transition marker within window."""
    start = max(1, target_idx - window)
    end = min(len(stamps), target_idx + window + 1)
    matches = []
    for idx in range(start, end):
        for pattern in TRANSITION_PATTERNS:
            if re.search(pattern, stamps[idx]):
                matches.append(idx)
                break
    if matches:
        best_match = min(matches, key=lambda idx: abs(idx - target_idx))
        return best_match + 1
    return target_idx


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

    stamps = deduplicate_consecutive_timestamps(all_stamps, ensure_no_gaps=True) if deduplicate else sorted(list(dict.fromkeys(all_stamps)), key=lambda l: parse_ts(l[:8]))
    if not stamps:
        return ""

    n = len(stamps)
    if n <= 10:
        target_parts = 1
    elif n <= 24:
        target_parts = 2
    elif n <= 60:
        target_parts = 3
    elif n <= 120:
        target_parts = 4
    else:
        target_parts = 5

    target_stamps_per_part = max(1, n // target_parts)
    window = max(4, min(15, target_stamps_per_part // 3))

    blocks: List[List[str]] = []
    curr = 0
    while curr < n:
        raw_next = curr + target_stamps_per_part
        if raw_next >= n or (n - raw_next) < (target_stamps_per_part // 2):
            blocks.append(stamps[curr:])
            break
        next_boundary = find_best_boundary(stamps, raw_next, window=window)
        if next_boundary <= curr:
            next_boundary = raw_next
        blocks.append(stamps[curr:next_boundary])
        curr = next_boundary

    border = "═" * 57
    parts: List[str] = []
    for i, block in enumerate(blocks, 1):
        start = block[0][:8]
        summary = generate_part_summary(block)
        header = f" ส่วนที่ {i}: {summary} (⏱ เริ่ม: {start})"
        part_text = f"{border}\n{header}\n{border}\n" + "\n".join(block)
        parts.append(part_text)

    assembled = "\n\n".join(parts)
    if enforce_byte_limit:
        return enforce_byte_cap(assembled)
    return assembled


_PART_NUM_RE = re.compile(r"ส่วนที่ \d+:")


def enforce_byte_cap(md: str, limit: int = BYTE_CAP_LIMIT) -> str:
    """Split any part over `limit` bytes (front-tier anibon-summarizer cap), then renumber.

    Split point prefers a topic transition near the middle (find_best_boundary).
    The first half keeps its original header; the second half gets a heuristic header.
    """
    out: List[str] = []
    queue = [b for b in md.strip().split("\n\n") if b.strip()]
    while queue:
        block = queue.pop(0)
        lines = block.splitlines()
        border_indices = [i for i, line in enumerate(lines) if line.startswith("═")]
        if len(border_indices) >= 2:
            stamps_start = border_indices[1] + 1
            header_chunk = "\n".join(lines[:stamps_start])
            stamps = lines[stamps_start:]
            border = lines[border_indices[0]]
        else:
            header_chunk = "\n".join(lines[:3])
            stamps = lines[3:]
            border = lines[0] if lines else "═" * 57

        if len(block.encode("utf-8")) <= limit or len(lines) < 4 or len(stamps) < 2:
            out.append(block)
            continue

        mid = find_best_boundary(stamps, len(stamps) // 2, window=3)
        mid = min(max(mid, 1), len(stamps) - 1)
        first, second = stamps[:mid], stamps[mid:]
        second_header = f" ส่วนที่ 0: {generate_part_summary(second)} (⏱ เริ่ม: {second[0][:8]})"
        queue[0:0] = [
            f"{header_chunk}\n" + "\n".join(first),
            f"{border}\n{second_header}\n{border}\n" + "\n".join(second),
        ]
    return "\n\n".join(_PART_NUM_RE.sub(f"ส่วนที่ {i}:", b, count=1) for i, b in enumerate(out, 1))

