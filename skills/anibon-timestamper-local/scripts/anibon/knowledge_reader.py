"""Domain knowledge reader and entity glossary generator for anibon-timestamper-local.

Parses signals.json to discover relevant domain references (anibon-world-identity/references/*.md),
reads knowledge files, extracts entity mappings (English/Thai, class/role, aliases),
and bootstraps SQLite database lookups (FGO, Pokemon).
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

DEFAULT_FGO_DB = Path(r"C:\Users\peter\.gemini\config\plugins\anibon-stream-synthesis\skills\reference\FGO and DATA\atlas_fgo.db")
DEFAULT_POKEMON_DB = Path(r"C:\Users\peter\.gemini\config\plugins\anibon-stream-synthesis\skills\anibon-world-identity\references\Pokemon DATA\pokemon.db")



def parse_markdown_entities(text: str) -> Dict[str, Dict[str, Any]]:
    """Extract character, faction, and game entities from markdown tables and bullet lists."""
    entities: Dict[str, Dict[str, Any]] = {}

    # 1. Match Markdown table rows with bold bilingual names:
    # Example: | **Maribell (มาริเบล)** | Vanguard | Passion | ...
    table_pattern = re.compile(
        r"\|\s*\*\*([A-Za-z0-9\s\-'\.]+)\s*\(([\u0E00-\u0E7F\s\-'\.]+)\)\*\*\s*\|\s*([^\|]*)\|\s*([^\|]*)\|"
    )
    for m in table_pattern.finditer(text):
        en_name = m.group(1).strip()
        th_name = m.group(2).strip()
        col2 = m.group(3).strip()
        col3 = m.group(4).strip()
        entities[en_name] = {
            "en": en_name,
            "th": th_name,
            "class": col2 if col2 and col2 != ":---:" else "",
            "attribute": col3 if col3 and col3 != ":---:" else "",
        }

    # 2. Match Bullet points with bold bilingual names:
    # Example: * **Navigator (ผู้ชี้ทาง):** บทบาทของผู้เล่น...
    # Example: - **Maribell (มาริเบล)**: แทงค์สายเกราะ...
    bullet_pattern = re.compile(
        r"[\*\-]\s+\*\*([A-Za-z0-9\s\-'\.]+)\s*\(([\u0E00-\u0E7F\s\-'\.]+)\)\*\*\s*[:\-]?\s*([^\n\r]*)"
    )
    for m in bullet_pattern.finditer(text):
        en_name = m.group(1).strip()
        th_name = m.group(2).strip()
        desc = m.group(3).strip()
        if en_name not in entities:
            entities[en_name] = {
                "en": en_name,
                "th": th_name,
                "description": desc[:100],
            }

    # 3. Match pure Thai bold aliases:
    # Example: * **ผู้ชี้ทาง:** คำแปลไทยอย่างเป็นทางการของ Navigator
    alias_pattern = re.compile(
        r"[\*\-]\s+\*\*([\u0E00-\u0E7F\s\-'\.]+)\*\*\s*[:\-]\s*([^\n\r]*)"
    )
    for m in alias_pattern.finditer(text):
        th_term = m.group(1).strip()
        desc = m.group(2).strip()
        if th_term not in entities:
            entities[th_term] = {
                "en": "",
                "th": th_term,
                "description": desc[:100],
            }

    return entities


def extract_entity_glossary(
    signals_map: Dict[str, Any],
    ref_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Scan signals_map for knowledge references, self-read markdown files, and build entity glossary."""
    glossary: Dict[str, Dict[str, Any]] = {}
    if not ref_dir or not ref_dir.exists():
        return glossary

    # Collect unique target files from all chunk signals
    targets: Set[str] = set()
    for sig in signals_map.values():
        if not isinstance(sig, dict):
            continue
        best_file = sig.get("best_file")
        if best_file:
            targets.add(best_file)
        for wf in sig.get("weighted_files", []):
            f = wf.get("file") if isinstance(wf, dict) else wf
            if f:
                targets.add(f)

    # Resolve and parse each target reference
    for target in targets:
        target_name = Path(target).name
        candidate = ref_dir / target_name
        if not candidate.exists():
            stem = Path(target).stem.lower()
            matches = [p for p in ref_dir.glob("*.md") if p.stem.lower() == stem]
            candidate = matches[0] if matches else None

        if candidate and candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8")
                parsed = parse_markdown_entities(content)
                for k, v in parsed.items():
                    if k not in glossary:
                        glossary[k] = v
                        glossary[k]["source_file"] = candidate.name
            except Exception:
                continue

    return glossary


def save_entity_glossary(glossary: Dict[str, Any], workspace: Path) -> Path:
    """Save entity glossary to <workspace>/entity_glossary.json."""
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    out_file = workspace / "entity_glossary.json"
    out_file.write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def _has_keyword_or_signal(signals_map: Dict[str, Any], keys: List[str]) -> bool:
    """Check if any signal in signals_map contains any of the given keywords."""
    keys_lower = [k.lower() for k in keys]
    for sig in signals_map.values():
        if not isinstance(sig, dict):
            continue
        bf = str(sig.get("best_file", "")).lower()
        if any(k in bf for k in keys_lower):
            return True
        for wf in sig.get("weighted_files", []):
            f_str = str(wf.get("file", "") if isinstance(wf, dict) else wf).lower()
            if any(k in f_str for k in keys_lower):
                return True
        mk = sig.get("matched_keywords", {})
        if isinstance(mk, dict):
            for k_term in mk.keys():
                if any(k in str(k_term).lower() for k in keys_lower):
                    return True
    return False


def enrich_with_sqlite_databases(
    glossary: Dict[str, Any],
    signals_map: Dict[str, Any],
    fgo_db: Optional[Path] = None,
    pokemon_db: Optional[Path] = None,
) -> Dict[str, Any]:
    """Enrich glossary with local SQLite database entries if corresponding franchise signals match."""
    # FGO Servant database lookup
    actual_fgo = Path(fgo_db) if fgo_db else DEFAULT_FGO_DB
    if actual_fgo.exists() and _has_keyword_or_signal(signals_map, ["fgo", "fate"]):
        try:
            conn = sqlite3.connect(actual_fgo)
            cursor = conn.cursor()
            cursor.execute("SELECT name, className, rarity FROM basic_servant")
            for row in cursor.fetchall():
                name, class_name, rarity = row[0], row[1], row[2]
                if name and name not in glossary:
                    glossary[name] = {
                        "en": name,
                        "th": "",
                        "class": class_name,
                        "rarity": rarity,
                        "source": "atlas_fgo.db",
                    }
            conn.close()
        except Exception:
            pass

    # Pokemon database lookup
    actual_poke = Path(pokemon_db) if pokemon_db else DEFAULT_POKEMON_DB
    if actual_poke.exists() and _has_keyword_or_signal(signals_map, ["pokemon", "โปเกมอน"]):
        try:
            conn = sqlite3.connect(actual_poke)
            cursor = conn.cursor()
            cursor.execute("SELECT name_en, name_th_official, name_th_english_sound FROM pokemon")
            for row in cursor.fetchall():
                en, th_off, th_snd = row[0], row[1], row[2]
                if en and en not in glossary:
                    glossary[en] = {
                        "en": en,
                        "th": th_off or th_snd or "",
                        "alias_th": th_snd or "",
                        "source": "pokemon.db",
                    }
            conn.close()
        except Exception:
            pass

    return glossary

