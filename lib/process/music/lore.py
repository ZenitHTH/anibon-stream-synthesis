from __future__ import annotations

import functools
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


@functools.lru_cache(maxsize=4)
def _load_cached_catalog(target_str: str) -> tuple[dict, ...]:
    target = Path(target_str)
    if not target.exists():
        return ()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return tuple(data.get("songs", []))
    except (json.JSONDecodeError, OSError):
        return ()


def _load_lore_catalog(path: Path | None = None) -> tuple[dict, ...]:
    target = path or resource_path("song_lore.json")
    return _load_cached_catalog(str(target))


def _match_score(entry: dict, q: str) -> int:
    if not q:
        return 0
    score = 0
    title_l = entry.get("title", "").lower()
    if title_l and (title_l in q or q in title_l):
        score = max(score, len(title_l) * 2)
    for kw in entry.get("keywords", []):
        if not kw:
            continue
        kw_l = kw.lower()
        if kw_l in q or q in kw_l:
            score = max(score, len(kw_l))
    return score


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
    best_entry: dict | None = None
    best_score = 0
    for entry in _load_lore_catalog(catalog_path):
        score = _match_score(entry, q)
        if score > best_score:
            best_score = score
            best_entry = entry
    if best_entry and best_score > 0:
        return _build_brief(best_entry)
    return SongContextBrief(
        title=query,
        artist="Unknown",
        theme="เพลงคลอหลังฉาก",
        meme_lore="",
        keywords=[query],
    )
