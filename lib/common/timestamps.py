"""Timestamp parsing, sanitization, tag remapping, and validation utilities.

Handles timestamp line hygiene, tag normalization to allowed whitelists,
chronological loop breaking, and collision guards.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Tuple

from common.log import log_warn
from common.time import fmt_ts, parse_ts
from common.config import (
    DEDUP_MIN_GAP_SEC,
    DEDUP_MAX_GAP_SEC,
    REACTION_MIN_GAP_SEC,
    STAMP_COLLISION_SEC,
)

TAGS = (
    "[Intro]", "[Greeting]", "[Ending]", "[Talk]", "[News]", "[Chat]", "[Donation]",
    "[Gameplay]", "[Gacha]", "[Boss]", "[Death]", "[Victory]",
    "[WatchParty]", "[Reaction]", "[Story]", "[Lore]", "[Review]", "[Tierlist]",
)

_ALLOWED_TAGS = {t.strip("[]") for t in TAGS} | {"Highlight"}
_REACTION_TAG_HINTS = ("โวย", "ตกใจ", "อึ้ง", "เหวอ", "กรี๊ด", "ช็อก", "ฮา", "ขำ", "เดือด", "หัวร้อน", "ตื่นเต้น", "เฮลั่น")

TAG_REMAP = {
    "Viktory": "Victory",
    "ปิดสตรีม": "Ending",
    "ปิดไลฟ์": "Ending",
    "จบไลฟ์": "Ending",
    "กล่าวปิด": "Ending",
    "วิเคราะห์": "Talk",
    "เจาะลึก": "Talk",
    "ชำแหละ": "Talk",
    "บ่น": "Talk",
    "บ่นอุบ": "Talk",
    "บ่นยับ": "Talk",
    "สับแหลก": "Talk",
    "สับเละ": "Talk",
    "จวกยับ": "Talk",
    "คุย": "Talk",
    "เม้าท์": "Talk",
    "เม้าท์มอย": "Talk",
    "ส่อง": "Reaction",
    "ฮา": "Reaction",
    "เหวอ": "Reaction",
    "อึ้ง": "Reaction",
    "โวย": "Reaction",
    "โวยวาย": "Reaction",
    "ตื่นเต้น": "Reaction",
    "ตกใจ": "Reaction",
    "หัวร้อน": "Reaction",
    "เปิดตัว": "News",
    "อัปเดต": "News",
    "ข่าว": "News",
    "Game News": "News",
    "ตอบแชท": "Chat",
    "ถามตอบ": "Chat",
    "ขอบคุณ": "Donation",
    "โดเนท": "Donation",
    "เล่นเกม": "Gameplay",
    "ลองเล่น": "Gameplay",
    "กาชา": "Gacha",
    "เปิดกาชา": "Gacha",
    "สู้บอส": "Boss",
}


def normalize_tag(match: re.Match) -> str:
    """Normalize non-standard tags into canonical whitelisted tags."""
    tag = match.group(1).strip()
    if tag in TAG_REMAP:
        return f"[{TAG_REMAP[tag]}]"
    if tag in _ALLOWED_TAGS:
        return f"[{tag}]"
    if any(h in tag for h in _REACTION_TAG_HINTS):
        return "[Reaction]"
    return "[Talk]"


def sanitize_timestamp_line(line: str) -> str:
    """Strip reasoning, comments, and normalize tags."""
    if not line:
        return ""
    line = re.sub(r"^[`'\"]+|[`'\"\\.]+$", "", line.strip())
    line = re.sub(r"\s*-\s*\d+\s*words.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\.?\s*Wait,\s*.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\([A-Za-z\s\?\,\.\-\:\'\/]{8,}\).*$", "", line)
    line = re.sub(r"\s*\([A-Za-z0-9\s\?\,\.\-\:\'\/]+\)\.?$", "", line)
    line = re.sub(r"\s*(?:Or just describe|Note:|Remark:).*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^[`'\"]+|[`'\"\\.]+$", "", line.strip())

    # Tag Normalization: remap non-standard tags like [วิเคราะห์] -> [Talk]
    line = re.sub(r"\[([^\]]+)\]", normalize_tag, line, count=1)
    return line.strip()


def _collision_threshold(line: str) -> int:
    """Return minimum chronological separation for parsed timestamp lines."""
    return REACTION_MIN_GAP_SEC if "[Reaction]" in line else 60


def parse_timestamps(raw: str, max_stamps: int = 4) -> List[str]:
    """Extract and sanitize valid HH:MM:SS - [Tag] lines from model output.

    Guards against LLM repetition loops (where the model restarts from the first timestamp)
    and timestamp collisions (where multiple timestamps have identical seconds or are <60s apart).
    """
    lines = []
    prev_sec = None
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^(\d{2}):(\d{2}):(\d{2})\s*-\s*\[", line)
        if m:
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))

            # 1. Chronological Loop Breaker:
            if prev_sec is not None and sec <= prev_sec:
                break

            cleaned = sanitize_timestamp_line(line)
            if not cleaned:
                continue

            # 2. Collision Guard (< 45s for [Reaction], else < 60s):
            if prev_sec is not None and (sec - prev_sec) < _collision_threshold(cleaned):
                continue

            lines.append(cleaned)
            prev_sec = sec

            if len(lines) >= max_stamps:
                break

    return lines


def validate_timestamps(stamps: List[str], start_sec: int, end_sec: int) -> List[str]:
    """Discard stamps falling outside [start_sec - 60, end_sec + 60]."""
    lo = max(0, start_sec - 60)
    hi = end_sec + 60
    valid = []
    for stamp in stamps:
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})", stamp)
        if not m:
            continue
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        if lo <= sec <= hi:
            valid.append(stamp)
        else:
            log_warn("stamp", f"dropped out-of-range {stamp[:8]} (window {fmt_ts(start_sec)}-{fmt_ts(end_sec)})")
    return valid


def is_continuation(raw: str) -> bool:
    """Check if model response indicates a continuation with no new timestamp."""
    upper = raw.upper().strip()
    return (upper == "SKIP" or upper == "CONTINUATION") and not re.search(r"\d{2}:\d{2}:\d{2}", raw)


@dataclass(frozen=True)
class ReactionOverlap:
    """Comparison context for consecutive reaction timestamps."""

    prev_desc: str
    curr_desc: str
    prev_kw: set[str]
    common_kw: set[str]
    gap_sec: int


def _char_ngrams(text: str, size: int = 4) -> set[str]:
    """Return sliding character n-grams for unspaced Thai overlap checks."""
    compact = re.sub(r"\s+", "", text.lower())
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[i : i + size] for i in range(len(compact) - size + 1)}


def _has_high_reaction_overlap(overlap: ReactionOverlap) -> bool:
    """Detect duplicate banter reactions via keyword or Thai n-gram overlap."""
    n_prev = len(overlap.prev_kw)
    n_common = len(overlap.common_kw)
    if n_common >= 4 or (n_prev >= 2 and n_common / n_prev >= 0.65):
        return True
    prev_grams = _char_ngrams(overlap.prev_desc)
    curr_grams = _char_ngrams(overlap.curr_desc)
    denom = min(len(prev_grams), len(curr_grams))
    return denom > 0 and (len(prev_grams & curr_grams) / denom) >= 0.55


def _should_keep_distinct_reaction(curr_stamp: str, overlap: ReactionOverlap) -> bool:
    """Keep distinct [Reaction] beats >= REACTION_MIN_GAP_SEC apart unless banter overlaps."""
    if "[Reaction]" not in curr_stamp or overlap.gap_sec < REACTION_MIN_GAP_SEC:
        return False
    return not _has_high_reaction_overlap(overlap)


def deduplicate_consecutive_timestamps(
    stamps: List[str],
    min_gap_sec: int = DEDUP_MIN_GAP_SEC,
    max_dedup_gap_sec: int = DEDUP_MAX_GAP_SEC,
    ensure_no_gaps: bool = False,
    max_allowed_gap_sec: int = 600,
) -> List[str]:
    """Deduplicate consecutive timestamps following anibon-summarizer rules.

    - Consecutive stamps within min_gap_sec (< 2 mins) are merged/deduplicated.
    - Consecutive stamps covering the same topic/game within max_dedup_gap_sec (< 10 mins)
      keep only the earliest timestamp where the topic started.
    """
    if not stamps:
        return []

    # Sort chronologically and deduplicate exact duplicates
    unique_stamps = sorted(list(dict.fromkeys(stamps)), key=lambda s: parse_ts(s[:8]))
    if len(unique_stamps) <= 1:
        return unique_stamps

    _STOPWORDS = {
        "พูดถึง", "วิเคราะห์", "คุยเรื่อง", "ดู", "รับชม", "เปิดดู", "เล่าข่าว",
        "แสดงความคิดเห็นเกี่ยวกับ", "ตอบแชตเรื่อง", "ถกประเด็น", "บ่นเรื่อง", "เม้าท์มอย",
        "และ", "กับ", "ใน", "ที่", "ของ", "การ", "ความ", "ปู่โบ๊ต", "ปู่บอร์ด",
        "รายละเอียด", "สตรีม", "ประจำวัน", "ประเด็น", "เรื่อง", "เกี่ยวกับ",
    }

    def _extract_keywords(desc: str) -> set:
        clean = re.sub(r"^[\[\]\w]+", "", desc).strip()
        tokens = set(re.findall(r"[A-Za-z0-9]+|[\u0E00-\u0E7F]{3,}", clean))
        return {t.lower() for t in tokens if t not in _STOPWORDS and len(t) > 2}

    def _extract_game_entity(desc: str) -> str:
        common_entities = [
            "elden ring", "fgo", "fate", "minecraft", "jojo", "yugioh", "yu-gi-oh",
            "รางดาว", "star rail", "honkai", "lol", "league of legends", "limbus",
            "nikke", "genshin", "dark souls", "deadlock", "monster hunter",
            "where winds meet", "wwm", "phantom blade zero", "pbz", "phantom blade",
        ]
        desc_lower = desc.lower()
        for ent in common_entities:
            if ent in desc_lower:
                return ent
        return ""

    result: List[str] = [unique_stamps[0]]
    for idx, curr_stamp in enumerate(unique_stamps[1:], 1):
        prev_stamp = result[-1]
        prev_sec = parse_ts(prev_stamp[:8])
        curr_sec = parse_ts(curr_stamp[:8])
        gap = curr_sec - prev_sec

        # Never keep stamps < STAMP_COLLISION_SEC apart
        if gap < STAMP_COLLISION_SEC:
            continue

        prev_desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[[^\]]+\]\s*", "", prev_stamp).strip()
        curr_desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[[^\]]+\]\s*", "", curr_stamp).strip()

        # Check if same game entity or substantial topic overlap
        prev_game = _extract_game_entity(prev_desc)
        curr_game = _extract_game_entity(curr_desc)

        prev_kw = _extract_keywords(prev_desc)
        curr_kw = _extract_keywords(curr_desc)
        common_kw = prev_kw.intersection(curr_kw)

        is_same_topic = False
        if prev_game and curr_game and prev_game == curr_game:
            # Same game session: deduplicate gameplay grinding across up to max_dedup_gap_sec (10m)
            is_same_topic = True
            topic_dedup_gap = max_dedup_gap_sec
        elif len(common_kw) >= 4 or (len(prev_kw) >= 3 and len(common_kw) / len(prev_kw) >= 0.85):
            # Same talk topic with heavy keyword overlap: deduplicate only across 240s (4m)
            is_same_topic = True
            topic_dedup_gap = 240
        else:
            topic_dedup_gap = max_dedup_gap_sec

        # Drop consecutive identical or repetitive failure loops (e.g. "พ่ายแพ้บอส... อีกครั้ง")
        clean_prev = prev_desc.split("อีก")[0].strip()
        clean_curr = curr_desc.split("อีก")[0].strip()
        if clean_prev and clean_curr and clean_prev == clean_curr:
            continue

        # Exception: Don't drop Boss / Victory / Gacha / Donation / Highlight / Ending milestones unless < 2 mins apart
        # Note: Death is excluded to prevent boss fight retry loops
        is_milestone = bool(re.search(r"\[(Boss|Victory|Gacha|Donation|Highlight|Ending)\]", curr_stamp))

        # Filter out superficial reactions/off-hand micro-stamps (< 2.5 min apart from previous talk)
        # unless it is a distinct reaction beat >= REACTION_MIN_GAP_SEC with low overlap.
        overlap = ReactionOverlap(prev_desc, curr_desc, prev_kw, common_kw, gap)
        distinct_reaction = _should_keep_distinct_reaction(curr_stamp, overlap)
        is_reaction = bool(re.search(r"\[Reaction\]", curr_stamp))
        if is_reaction and gap < 150 and not distinct_reaction:
            continue

        # Lookahead safety guard: NEVER drop if dropping would cause gap > max_allowed_gap_sec to next candidate
        if ensure_no_gaps and idx + 1 < len(unique_stamps):
            next_sec = parse_ts(unique_stamps[idx + 1][:8])
            if next_sec is not None and (next_sec - prev_sec) > max_allowed_gap_sec:
                result.append(curr_stamp)
                continue

        if gap < min_gap_sec:
            # Micro-gap (< 2 min): drop duplicate/continuation unless critical milestone or distinct reaction
            if not is_milestone and not distinct_reaction:
                continue
        elif gap < topic_dedup_gap and is_same_topic and not is_milestone and not distinct_reaction:
            # Redundant continuation stamp for same topic within dedup window
            continue

        result.append(curr_stamp)

    return result

