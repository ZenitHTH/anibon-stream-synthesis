from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

MUSIC_KEYWORDS = ("เพลง", "ร้องเพลง", "bgm", "cover", "ชื่อเพลง", "นักร้อง", "ดักเจ้า")
EXCLUDE_CRY_KEYWORDS = ("ร้องไห้", "ร้องกรี๊ด", "ร้องเลย", "เรียกร้อง", "ร้องแง")


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
    if any(cry in t for cry in EXCLUDE_CRY_KEYWORDS):
        return any(core in t for core in ("เพลง", "ดักเจ้า", "cover", "bgm"))
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


async def recognize_shazam_slice(audio_path: str) -> TrackMetadata | None:
    """Offline-safe Shazam recognition fallback using shazamio."""
    try:
        from shazamio import Shazam
        shazam = Shazam()
        out = await shazam.recognize(audio_path)
        track = out.get("track", {})
        if "title" in track and "subtitle" in track:
            return TrackMetadata(title=track["title"], artist=track["subtitle"])
    except Exception:
        return None
    return None
