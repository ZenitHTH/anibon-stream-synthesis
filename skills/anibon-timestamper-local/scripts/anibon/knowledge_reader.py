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

    # 1. Tables: split lines with '|'
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line[1:-1].split("|")]
        if len(cols) < 2 or ":---" in cols[0] or ":---" in cols[1]:
            continue
        c0, c1 = cols[0], cols[1]
        c2 = cols[2] if len(cols) > 2 else ""
        c3 = cols[3] if len(cols) > 3 else ""

        # Check bold in c0
        m_bold = re.search(r"\*\*([^\*]+)\*\*", c0)
        if not m_bold:
            continue
        raw_name = m_bold.group(1).strip()

        # Check if raw_name is X (Y)
        m_paren = re.search(r"([^\(\)]+)\s*\(([^)]+)\)", raw_name)
        if m_paren:
            part1 = m_paren.group(1).strip()
            part2 = m_paren.group(2).strip()
            # If part1 is Thai and part2 is Eng, check if c1 is canonical Eng (e.g. Pokemon table)
            if re.search(r"[\u0E00-\u0E7F]", part1) and re.search(r"[a-zA-Z\u00C0-\u024F]", part2):
                th = part1
                en = c1 if re.match(r"^[a-zA-Z\u00C0-\u024F0-9\s\-\'\.]+$", c1) else part2
            else:
                en = part1
                th = part2
        else:
            if re.search(r"[\u0E00-\u0E7F]", raw_name):
                th = raw_name
                en = c1 if re.match(r"^[a-zA-Z\u00C0-\u024F0-9\s\-\'\.]+$", c1) else ""
            else:
                en = raw_name
                th = c1 if re.search(r"[\u0E00-\u0E7F]", c1) else ""

        en_clean = re.sub(r"[^a-zA-Z\u00C0-\u024F0-9\s\-\.]", "", en).strip()
        m_th = re.search(r"[\u0E00-\u0E7F\s\-\.]+", th)
        th_clean = m_th.group(0).strip() if m_th else ""

        if c1 and c1 != en and ":---" not in c1:
            role = c1
            attr = c2 if (c2 and ":---" not in c2) else ""
        else:
            role = c2 if (c2 and ":---" not in c2) else ""
            attr = c3 if (c3 and ":---" not in c3) else ""

        role = re.sub(r"[:\-\|]", "", role).strip()

        key = en_clean or th_clean
        if key and len(key) >= 3:
            entities[key] = {
                "en": en_clean,
                "th": th_clean,
                "class": role,
                "role": role,
                "attribute": attr.strip(),
            }

    # 2. Bullets: - **Name (Alias)** [:—-] desc
    for line in text.splitlines():
        line = line.strip()
        m_b = re.match(r"^[\*\-]\s+\*\*([^\*]+)\*\*\s*[:\-—]?\s*(.*)", line)
        if not m_b:
            continue
        raw_name = m_b.group(1).strip()
        desc = m_b.group(2).strip()

        m_paren = re.search(r"([^\(\)]+)\s*\(([^)]+)\)", raw_name)
        if m_paren:
            part1 = m_paren.group(1).strip()
            part2 = m_paren.group(2).strip()
            m_en = re.search(r"[a-zA-Z\u00C0-\u024F0-9\s\-\.]+", part1 if re.search(r"[a-zA-Z\u00C0-\u024F]", part1) else part2)
            m_th = re.search(r"[\u0E00-\u0E7F\s\-\.]+", part2 if re.search(r"[\u0E00-\u0E7F]", part2) else part1)
            en = m_en.group(0).strip() if m_en else ""
            th = m_th.group(0).strip() if m_th else ""
        else:
            m_en = re.search(r"[a-zA-Z\u00C0-\u024F0-9\s\-\.]+", raw_name)
            m_th = re.search(r"[\u0E00-\u0E7F\s\-\.]+", raw_name)
            en = m_en.group(0).strip() if m_en and not re.search(r"[\u0E00-\u0E7F]", raw_name) else ""
            th = m_th.group(0).strip() if m_th else ""

        key = en or th
        if key and len(key) >= 3 and key not in entities:
            entities[key] = {
                "en": en,
                "th": th,
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

