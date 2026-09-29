"""Pass 2 local summarizer and YouTube comment block assembly.

Partitions linear timestamp output into comment blocks under 3,500 bytes
(YouTube comment capacity ceiling is 4,500 bytes; 3,500 ensures safety margin).
Supports local LLM summarizer pass with heuristic fallback and double-border formatting.
"""
import re
from pathlib import Path
from typing import List, Optional

from anibon.time import parse_ts, fmt_ts
from anibon.lmstudio import call_local


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a 2-3 topic summary sentence from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        if desc and desc not in topics:
            topics.append(desc)

    if not topics:
        return "สรุปเนื้อหาและบรรยากาศในไลฟ์สตรีม."

    if len(topics) <= 3:
        return ". ".join(topics) + "."

    t1 = topics[0].rstrip(". ")
    t2 = topics[len(topics) // 2].rstrip(". ")
    t3 = topics[-1].rstrip(". ")
    return f"{t1}. {t2}. {t3}."


def run_local_summarizer_pass(
    endpoint: str,
    model: str,
    all_stamps: List[str],
    workspace: Optional[Path] = None,
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> Optional[str]:
    """Call local LLM to partition timestamps into Parts with Caveman summaries."""
    if not all_stamps:
        return None

    raw_list = "\n".join(all_stamps)
    expected_parts = max(1, (len(all_stamps) + 9) // 10)
    prompt = f"""\
You are an expert livestream editor for Anibon Official.
Below are {len(all_stamps)} timestamps from a livestream by Pu Boat.

Divide these timestamps into roughly {expected_parts} logical Parts for YouTube comments.

CRITICAL GROUPING & CONSOLIDATION RULES (from anibon-summarizer):
1. GROUP BY ACTIVITY PERIOD:
   - Primary grouping unit is continuous activity (one watchparty screening, sustained discussion block of one game/topic, gameplay segment, closing).
   - Do NOT split on single-tag flickers or passing micro-topics inside the same activity.
   - Hard breaks that require new parts: Stream opening -> first watchparty/talk; Game -> news/donation segment; Talk -> gacha; Last content -> signing-off.
2. BYTE & STAMP CEILINGS:
   - YouTube comment limit is 3,500 bytes (Thai chars = 3 bytes).
   - Target size: 8 to 13 timestamps per part. NEVER exceed 14 timestamps per part.
   - Consolidation: Do NOT create parts containing only 1-3 timestamps (unless standalone closing/donation). Merge same activity parts if under 3,500 bytes.
3. CAVEMAN SUMMARY HEADERS:
   - Punchy Thai summary header (2-3 short, dense sentences in Thai, active voice, zero fluff, highlighting major drama, news, or gameplay).

For each part, specify:
1. The start timestamp where this part begins.
2. A punchy Caveman-style Thai summary header.

Format strictly as:
Part 1: 00:00:00
Summary: [Thai Summary 2-3 sentences]

Part 2: HH:MM:SS
Summary: [Thai Summary 2-3 sentences]

TIMESTAMPS:
{raw_list}
"""
    print("[summarizer] Calling local model for part division & Caveman summaries...")
    try:
        content = call_local(endpoint, model, prompt, max_tokens, temperature)
        raw_matches = re.findall(
            r"Part\s+(\d+)[:\s]+(\d{2}:\d{2}:\d{2}).*?Summary[:\s]+([^\n\r]+)",
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
            matches.append((p_num, p_start, p_sum))

        if len(matches) >= 2:
            border = "═" * 57
            rendered_parts = []
            for idx, (p_num, p_start, p_summary) in enumerate(matches):
                start_sec = parse_ts(p_start)
                next_start_sec = parse_ts(matches[idx + 1][1]) if idx + 1 < len(matches) else 999999
                part_stamps = [s for s in all_stamps if start_sec <= parse_ts(s[:8]) < next_start_sec]
                if part_stamps:
                    header = f" ส่วนที่ {p_num}: {p_summary.strip()} (⏱ เริ่ม: {p_start})"
                    part_text = f"{border}\n{header}\n{border}\n" + "\n".join(part_stamps)
                    if len(part_text.encode("utf-8")) > 3500:
                        return None
                    rendered_parts.append(part_text)
            if rendered_parts:
                return "\n\n".join(rendered_parts)
    except Exception as e:
        print(f"[summarizer] Warning: local summarizer call failed ({e}). Falling back to heuristic assembly.")
    return None


def assemble_parts(
    all_stamps: List[str],
    workspace: Optional[Path] = None,
    block_size: int = 2400,
) -> str:
    """Group timestamps into YouTube parts (<3500 bytes) with double borders."""
    if not all_stamps:
        return ""

    all_stamps = sorted(list(dict.fromkeys(all_stamps)), key=lambda l: parse_ts(l[:8]))

    n_parts = max(1, (len(all_stamps) + 9) // 10)
    chunk_size = (len(all_stamps) + n_parts - 1) // n_parts
    blocks: List[List[str]] = []
    for i in range(0, len(all_stamps), chunk_size):
        blocks.append(all_stamps[i:i + chunk_size])

    border = "═" * 57
    parts: List[str] = []
    for i, block in enumerate(blocks, 1):
        start = block[0][:8]
        summary = generate_part_summary(block)
        header = f" ส่วนที่ {i}: {summary} (⏱ เริ่ม: {start})"
        part_text = f"{border}\n{header}\n{border}\n" + "\n".join(block)

        if len(part_text.encode("utf-8")) > 3500 and len(block) > 4:
            mid = len(block) // 2
            b1, b2 = block[:mid], block[mid:]
            s1, s2 = generate_part_summary(b1), generate_part_summary(b2)
            p1 = f"{border}\n ส่วนที่ {i}.1: {s1} (⏱ เริ่ม: {b1[0][:8]})\n{border}\n" + "\n".join(b1)
            p2 = f"{border}\n ส่วนที่ {i}.2: {s2} (⏱ เริ่ม: {b2[0][:8]})\n{border}\n" + "\n".join(b2)
            parts.append(p1)
            parts.append(p2)
        else:
            parts.append(part_text)

    return "\n\n".join(parts)
