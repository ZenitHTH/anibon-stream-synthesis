"""Domain knowledge reader and entity glossary generator for anibon-timestamper-local.

Parses signals.json to discover relevant domain references (anibon-world-identity/references/*.md),
reads knowledge files, extracts entity mappings (English/Thai, class/role, aliases),
and bootstraps SQLite database lookups (FGO, Pokemon).
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


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
