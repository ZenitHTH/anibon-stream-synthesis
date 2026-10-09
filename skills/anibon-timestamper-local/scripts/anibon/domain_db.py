"""SQLite domain database connectors and JIT archetype entity resolver.

Supports:
- Yu-Gi-Oh (ygo_cards.db) — archetype-level card filtering
- FGO (atlas_fgo.db) — servant class/rarity lookup
- Pokémon (pokemon.db) — Thai official & English sound naming
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any

from anibon.phonetic_bridge import load_phonetic_bridge, match_phonemes

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FGO_DB = _SCRIPT_DIR.parent.parent.parent / "reference" / "FGO and DATA" / "atlas_fgo.db"
DEFAULT_YGO_DB = _SCRIPT_DIR.parent.parent.parent / "reference" / "Yu-Gi-Oh DATA" / "ygo_cards.db"
DEFAULT_POKE_DB = _SCRIPT_DIR.parent.parent.parent / "anibon-world-identity" / "references" / "Pokemon DATA" / "pokemon.db"


def query_ygo_by_archetype(
    archetype: str,
    limit: int = 5,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Query Yu-Gi-Oh cards belonging to an archetype, strictly limited."""
    p = Path(db_path) if db_path else DEFAULT_YGO_DB
    if not p.is_file():
        return []
    try:
        with sqlite3.connect(p) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM cards WHERE archetype = ? LIMIT ?", (archetype, limit))
            return [row[0] for row in cur.fetchall() if row[0]]
    except Exception:
        return []


def query_fgo_servants(
    names: List[str],
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Query FGO servant metadata (name, className, rarity) by list of names."""
    p = Path(db_path) if db_path else DEFAULT_FGO_DB
    if not p.is_file() or not names:
        return []
    try:
        with sqlite3.connect(p) as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" for _ in names)
            query = f"SELECT name, className, rarity FROM basic_servant WHERE name IN ({placeholders})"
            cur.execute(query, names)
            return [
                {"name": r[0], "className": r[1], "rarity": r[2]}
                for r in cur.fetchall()
            ]
    except Exception:
        return []


def query_pokemon(
    name: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Query Pokémon by English name or Thai phonetic transliteration."""
    p = Path(db_path) if db_path else DEFAULT_POKE_DB
    if not p.is_file() or not name:
        return None
    try:
        with sqlite3.connect(p) as conn:
            cur = conn.cursor()
            query = (
                "SELECT name_en, name_th_official, name_th_english_sound "
                "FROM pokemon WHERE name_en = ? OR name_th_official = ? OR name_th_english_sound = ? LIMIT 1"
            )
            cur.execute(query, (name, name, name))
            row = cur.fetchone()
            if row:
                return {
                    "name_en": row[0],
                    "name_th_official": row[1] or "",
                    "name_th_english_sound": row[2] or "",
                }
    except Exception:
        pass
    return None


def resolve_entities_for_chunk(
    chunk_text: str,
    bridge: Optional[Dict[str, Any]] = None,
    max_entities: int = 12,
) -> List[str]:
    """Extract and resolve grounded entities for chunk text using phonetic bridge and SQLite."""
    if not chunk_text:
        return []

    hits = match_phonemes(chunk_text, bridge)
    resolved: List[str] = []
    seen: set = set()

    for h in hits:
        en = h.get("en", "")
        th = h.get("th", "")
        domain = h.get("domain", "")
        archetype = h.get("archetype")

        # Format label
        label = f"{th} ({en})" if (th and en and th != en) else (th or en)
        if label and label not in seen:
            seen.add(label)
            resolved.append(label)

        # 1. Yu-Gi-Oh: Archetype lookup
        if domain == "yugioh" and archetype:
            cards = query_ygo_by_archetype(archetype, limit=4)
            for c in cards:
                if c not in seen:
                    seen.add(c)
                    resolved.append(c)

        # 2. Pokémon: Mandatory Thai + EN formatting
        elif domain == "pokemon" and en:
            p_data = query_pokemon(en)
            if p_data:
                th_sound = p_data.get("name_th_english_sound") or p_data.get("name_th_official")
                if th_sound:
                    formatted = f"{th_sound} ({en})"
                    if formatted not in seen:
                        seen.add(formatted)
                        resolved.append(formatted)

        if len(resolved) >= max_entities:
            break

    return resolved[:max_entities]
