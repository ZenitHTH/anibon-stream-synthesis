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
