from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

MUSIC_KEYWORDS = ("เพลง", "ร้อง", "bgm", "cover", "ชื่อเพลง", "นักร้อง", "ดักเจ้า")


@dataclass(frozen=True)
class TrackMetadata:
    title: str
    artist: str
    confidence: float = 1.0


def _extract_message_text(item: str | dict) -> str:
    if isinstance(item, dict):
        return str(item.get("text", item.get("message", "")))
    return str(item)


def is_music_query(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in MUSIC_KEYWORDS)


def scan_chat_music_density(messages: Sequence[str | dict]) -> float:
    if not messages:
        return 0.0
    music_count = 0
    for item in messages:
        text = _extract_message_text(item)
        if is_music_query(text):
            music_count += 1
    return float(music_count / len(messages))


def has_music_chat_surge(messages: Sequence[str | dict], threshold: float = 0.15) -> bool:
    return scan_chat_music_density(messages) >= threshold
