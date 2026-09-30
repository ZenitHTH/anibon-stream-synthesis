"""Timestamp parsing, sanitization, tag remapping, and validation utilities.

Handles timestamp line hygiene, tag normalization to allowed whitelists,
chronological loop breaking, and collision guards.
"""
import re
from typing import List, Tuple

from anibon.time import fmt_ts, parse_ts

TAGS = (
    "[Greeting]", "[Talk]", "[News]", "[Chat]", "[Donation]",
    "[Gameplay]", "[Gacha]", "[Boss]", "[Death]", "[Victory]",
    "[WatchParty]", "[Reaction]", "[Story]", "[Lore]", "[Review]",
)

TAG_REMAP = {
    "วิเคราะห์": "Talk",
    "เจาะลึก": "Talk",
    "ชำแหละ": "Talk",
    "บ่น": "Talk",
    "บ่นอุบ": "Talk",
    "คุย": "Talk",
    "เม้าท์": "Talk",
    "เม้าท์มอย": "Talk",
    "ส่อง": "Reaction",
    "ฮา": "Reaction",
    "เหวอ": "Reaction",
    "อึ้ง": "Reaction",
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
    """Normalize non-standard tags into canonical tags using TAG_REMAP."""
    tag = match.group(1).strip()
    if tag in TAG_REMAP:
        return f"[{TAG_REMAP[tag]}]"
    return f"[{tag}]"


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

            # 2. Collision Guard (< 60s):
            if prev_sec is not None and (sec - prev_sec) < 60:
                continue

            cleaned = sanitize_timestamp_line(line)
            if cleaned:
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
            print(f"  [drop] out-of-range stamp {stamp[:8]} (window {fmt_ts(start_sec)}-{fmt_ts(end_sec)})")
    return valid


def is_continuation(raw: str) -> bool:
    """Check if model response indicates a continuation with no new timestamp."""
    upper = raw.upper().strip()
    return (upper == "SKIP" or upper == "CONTINUATION") and not re.search(r"\d{2}:\d{2}:\d{2}", raw)


def deduplicate_consecutive_timestamps(
    stamps: List[str],
    min_gap_sec: int = 120,
    max_dedup_gap_sec: int = 600,
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
            "nikke", "genshin", "dark souls", "น้ำท่วม",
        ]
        desc_lower = desc.lower()
        for ent in common_entities:
            if ent in desc_lower:
                return ent
        return ""

    result: List[str] = [unique_stamps[0]]
    for curr_stamp in unique_stamps[1:]:
        prev_stamp = result[-1]
        prev_sec = parse_ts(prev_stamp[:8])
        curr_sec = parse_ts(curr_stamp[:8])
        gap = curr_sec - prev_sec

        # Never keep stamps < 45 seconds apart
        if gap < 45:
            continue

        prev_desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", prev_stamp).strip()
        curr_desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", curr_stamp).strip()

        # Check if same game entity or substantial topic overlap
        prev_game = _extract_game_entity(prev_desc)
        curr_game = _extract_game_entity(curr_desc)

        prev_kw = _extract_keywords(prev_desc)
        curr_kw = _extract_keywords(curr_desc)
        common_kw = prev_kw.intersection(curr_kw)

        is_same_topic = False
        if prev_game and curr_game and prev_game == curr_game:
            # Same game / topic discussed
            is_same_topic = True
        elif len(common_kw) >= 3 or (len(prev_kw) >= 2 and len(common_kw) / len(prev_kw) >= 0.75):
            is_same_topic = True

        # Rule: If consecutive timestamps are < 10 mins apart and cover the same topic -> keep only earliest
        # Exception: Don't drop Boss / Death / Victory / Gacha / Donation milestones unless < 2 mins apart
        is_milestone = bool(re.search(r"\[(Boss|Death|Victory|Gacha|Donation)\]", curr_stamp))

        # Filter out superficial reactions/off-hand micro-stamps (< 2.5 min apart from previous talk)
        is_reaction = bool(re.search(r"\[Reaction\]", curr_stamp))
        if is_reaction and gap < 150:
            continue

        if gap < min_gap_sec:
            # Micro-gap (< 2 min): drop duplicate/continuation unless critical milestone
            if not is_milestone:
                continue
        elif gap < max_dedup_gap_sec and is_same_topic and not is_milestone:
            # Redundant continuation stamp for same topic within 10 minutes
            continue

        result.append(curr_stamp)

    return result

