"""
process.knowledge — Domain entity glossary, SQLite databases, and phonetic bridge.
"""

from __future__ import annotations

from process.knowledge.domain_db import (
    DEFAULT_FGO_DB,
    DEFAULT_POKE_DB,
    DEFAULT_YGO_DB,
    query_fgo_servants,
    query_pokemon,
    query_ygo_by_archetype,
    resolve_entities_for_chunk,
)
from process.knowledge.phonetic_bridge import (
    load_phonetic_bridge,
    match_phonemes,
)
from process.knowledge.reader import (
    enrich_with_sqlite_databases,
    extract_entity_glossary,
    resolve_reference_file,
    save_entity_glossary,
)

__all__ = [
    "DEFAULT_FGO_DB",
    "DEFAULT_POKE_DB",
    "DEFAULT_YGO_DB",
    "extract_entity_glossary",
    "save_entity_glossary",
    "enrich_with_sqlite_databases",
    "resolve_reference_file",
    "query_fgo_servants",
    "query_pokemon",
    "query_ygo_by_archetype",
    "resolve_entities_for_chunk",
    "load_phonetic_bridge",
    "match_phonemes",
]
