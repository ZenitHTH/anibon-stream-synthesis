"""Prompt templates and response parsing for Pass 2 local summarizer."""
from __future__ import annotations

import re
from typing import List, Tuple

from common.time import parse_ts


def build_summarizer_prompt(stamps: List[str]) -> str:
    """Construct prompt for local LLM part partitioning and summary generation."""
    raw_list = "\n".join(stamps)
    return f"""\
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
   - ห้ามขึ้นต้นหัวข้อสรุปด้วยคำว่า 'ปู่โบ๊ต' (ผู้ชมรู้อยู่แล้วว่าเป็นไลฟ์ปู่โบ๊ต) ให้เขียนสรุปแบบ Caveman กระชับ ตรงประเด็น เปิดด้วยประเด็นหรือการกระทำทันที
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


def parse_summarizer_matches(content: str) -> List[Tuple[str, str, str]]:
    """Extract valid ordered (part_num, start_ts, summary) tuples from LLM output."""
    raw_matches = re.findall(
        r"Part\s+(\d+)[:\s]+(\d{2}:\d{2}:\d{2}).*?Summary[:\s]+(.+?)(?=\n\s*\n|\n\s*Part\s+\d+|\Z)",
        content,
        flags=re.DOTALL,
    )
    seen_nums, prev_sec, matches = set(), -1, []
    for p_num, p_start, p_sum in raw_matches:
        sec = parse_ts(p_start)
        if p_num in seen_nums or sec <= prev_sec:
            continue
        seen_nums.add(p_num)
        prev_sec = sec
        matches.append((p_num, p_start, " ".join(p_sum.split())))
    return matches
