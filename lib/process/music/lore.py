from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from common.resources import resource_path


@dataclass(frozen=True)
class SongContextBrief:
    title: str
    artist: str
    theme: str
    meme_lore: str
    keywords: list[str] = field(default_factory=list)


def _load_lore_catalog(path: Path | None = None) -> list[dict]:
    target = path or resource_path("song_lore.json")
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data.get("songs", [])
    except (json.JSONDecodeError, OSError):
        return []


def _entry_matches_query(entry: dict, q: str) -> bool:
    if q in entry.get("title", "").lower() or q in entry.get("artist", "").lower():
        return True
    return any(q in kw.lower() or kw.lower() in q for kw in entry.get("keywords", []))


def _build_brief(entry: dict) -> SongContextBrief:
    return SongContextBrief(
        title=entry.get("title", ""),
        artist=entry.get("artist", ""),
        theme=entry.get("theme", ""),
        meme_lore=entry.get("meme_lore", ""),
        keywords=list(entry.get("keywords", [])),
    )


def fetch_song_lore_summary(query: str, catalog_path: Path | None = None) -> SongContextBrief:
    q = query.strip().lower()
    for entry in _load_lore_catalog(catalog_path):
        if _entry_matches_query(entry, q):
            return _build_brief(entry)
    return SongContextBrief(
        title=query,
        artist="Unknown",
        theme="เพลงคลอหลังฉาก",
        meme_lore="",
        keywords=[query],
    )
