from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from common.resources import resource_path


@dataclass(frozen=True)
class MediaCandidate:
    media_id: str
    title: str
    artist: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    canonical_phrases: tuple[str, ...] = field(default_factory=tuple)
    garble_patterns: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SeparatedSegment:
    timestamp: str
    label: str
    raw_text: str
    ground_truth: str
    media_title: str = ""


@dataclass(frozen=True)
class MediaTriggerResult:
    triggered: bool
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    chat_hints: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ChunkMediaInput:
    raw_lines: tuple[str, ...] = field(default_factory=tuple)
    livechat_lines: tuple[str, ...] = field(default_factory=tuple)
    gameplay_keywords: tuple[str, ...] = field(default_factory=tuple)


def _parse_candidate_dict(data: dict[str, Any]) -> MediaCandidate:
    return MediaCandidate(
        media_id=str(data.get("media_id", "")),
        title=str(data.get("title", "")),
        artist=str(data.get("artist", "")),
        aliases=tuple(str(x) for x in data.get("aliases", ())),
        canonical_phrases=tuple(str(x) for x in data.get("canonical_phrases", ())),
        garble_patterns=tuple(str(x) for x in data.get("garble_patterns", ())),
    )


def load_media_catalog(catalog_path: Path | None = None) -> list[MediaCandidate]:
    target = catalog_path or resource_path("media_catalog.json")
    if not target.is_file():
        return []
    content = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(content, list):
        return []
    return [_parse_candidate_dict(entry) for entry in content if isinstance(entry, dict)]
