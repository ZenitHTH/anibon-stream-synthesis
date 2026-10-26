"""
anibon.garbled_grounding — Grounding validation against canonical references.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

from common.resources import resource_path


@dataclass(frozen=True)
class GroundingContext:
    """Canonical terms, stream title, and prompt hint for grounding validation."""
    known_canonical_terms: frozenset[str]
    stream_title: str = ""
    domain_hint: str = ""


def _extract_dictionary_keys() -> Set[str]:
    dict_path = resource_path("garbled_replacements.json")
    if not dict_path.is_file():
        return set()
    try:
        data = json.loads(dict_path.read_text(encoding="utf-8"))
        mappings = data.get("mappings", data)
        return {str(k).lower().strip() for k in mappings.keys() if str(k).strip()}
    except Exception:
        return set()


def _extract_glossary_terms(workspace: Path) -> Set[str]:
    glossary_path = workspace / "entity_glossary.json"
    if not glossary_path.is_file():
        return set()
    try:
        gloss = json.loads(glossary_path.read_text(encoding="utf-8"))
        return {str(k).lower().strip() for k in gloss.keys() if len(str(k).strip()) >= 3}
    except Exception:
        return set()


def _extract_stream_title(workspace: Path) -> str:
    info_path = workspace / "info.json"
    if not info_path.is_file():
        return ""
    try:
        data = json.loads(info_path.read_text(encoding="utf-8"))
        return str(data.get("title", "")).strip()
    except Exception:
        return ""


def _build_domain_hint(title: str, names: List[str]) -> str:
    parts: List[str] = []
    if title:
        parts.append(f"Stream Title: {title}")
    if names:
        parts.append("Known Entities: " + ", ".join(names[:80]))
    return "\n".join(parts)


def load_domain_hint(workspace: Path) -> str:
    """Build compact domain proper-noun hint from info.json title and entity_glossary.json."""
    title = _extract_stream_title(workspace)
    names = sorted(list(_extract_glossary_terms(workspace)))
    return _build_domain_hint(title, names)


def load_grounding_context(workspace: Path) -> GroundingContext:
    """Load canonical dictionary keys, workspace glossary terms, and stream title."""
    terms = _extract_dictionary_keys()
    glossary = _extract_glossary_terms(workspace)
    terms.update(glossary)
    title = _extract_stream_title(workspace)
    hint = _build_domain_hint(title, sorted(list(glossary)))
    return GroundingContext(
        known_canonical_terms=frozenset(terms),
        stream_title=title,
        domain_hint=hint,
    )


def is_grounded_target(target: str, whisper_segment: str, context: GroundingContext) -> bool:
    """Verify target exists in canonical dictionary, entity glossary, stream title, or Whisper segment."""
    target_clean = target.strip().lower()
    if not target_clean:
        return False
    if target_clean in context.known_canonical_terms:
        return True
    if context.stream_title and target_clean in context.stream_title.lower():
        return True
    if whisper_segment and target_clean in whisper_segment.lower():
        return True
    return False
