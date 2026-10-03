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


from anibon.timestamps import deduplicate_consecutive_timestamps


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a clean 2-3 topic summary phrase from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        # Clean speaker prefixes and trailing punctuation
        clean = re.sub(r"^(ปู่โบ๊ต|ปู่บอร์ด|พูดถึง|วิเคราะห์|คุยเรื่อง|ดู|รับชม|เปิดดู|เล่าข่าว|บ่นเรื่อง|ถกประเด็น)\s*", "", desc)
        clean = clean.strip(". ")
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

    # Apply semantic & chronological deduplication first
    stamps = deduplicate_consecutive_timestamps(all_stamps)
    if not stamps:
        return None

    raw_list = "\n".join(stamps)
    expected_parts = max(1, (len(stamps) + 9) // 10)
    prompt = f"""\
You are an expert livestream editor for Anibon Official.
Below are {len(stamps)} timestamps from a livestream by Pu Boat.

Divide these timestamps into cohesive, logical thematic Parts based on overarching topic categories.

CRITICAL GROUPING & CONSOLIDATION RULES:
1. GROUP STRICTLY BY THEMATIC ACTIVITY & TOPIC CATEGORY:
   - Primary grouping unit is continuous thematic activity (e.g. Political/Flood News & Social Critique, Watchparty / Media Review, Gaming Session, Concluding Thoughts / Q&A / Donations).
   - Do NOT split on single-tag flickers or passing micro-topics inside the same activity.
   - Strictly filter out superficial 1-2 sentence off-hand mentions in headers.
   - Hard breaks that require new parts: Stream opening -> first watchparty/talk; Game -> news/donation segment; Talk -> gacha/gaming; Last content -> signing-off.
2. NO BYTE LIMITS & SEQUENTIAL INTEGER NUMBERING ONLY:
   - Do NOT divide parts based on byte limits (no 3,500 byte limit). A thematic part can contain as many timestamps as belong to that topic category.
   - Number parts sequentially as integers ONLY (Part 1, Part 2, Part 3, etc.). NEVER create sub-parts like 1.1, 1.2.
   - Consolidation: Do NOT create tiny parts containing only 1-2 timestamps (unless standalone closing/donation).
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


def assemble_parts(
    all_stamps: List[str],
    workspace: Optional[Path] = None,
    block_size: int = 2400,
    deduplicate: bool = True,
) -> str:
    """Group timestamps into sequential integer parts with double borders."""
    if not all_stamps:
        return ""

    stamps = deduplicate_consecutive_timestamps(all_stamps) if deduplicate else sorted(list(dict.fromkeys(all_stamps)), key=lambda l: parse_ts(l[:8]))
    if not stamps:
        return ""

    target_stamps_per_part = 14
    blocks: List[List[str]] = []
    for i in range(0, len(stamps), target_stamps_per_part):
        blocks.append(stamps[i:i + target_stamps_per_part])

    border = "═" * 57
    parts: List[str] = []
    for i, block in enumerate(blocks, 1):
        start = block[0][:8]
        summary = generate_part_summary(block)
        header = f" ส่วนที่ {i}: {summary} (⏱ เริ่ม: {start})"
        part_text = f"{border}\n{header}\n{border}\n" + "\n".join(block)
        parts.append(part_text)

    return "\n\n".join(parts)

