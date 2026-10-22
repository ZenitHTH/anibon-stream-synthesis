"""
anibon.audit — Timestamp sanitization, phonetic scrubbing, and glossary auditing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List

from anibon.cleaner import _SPEAKER_SCRUB_RE, compile_mapping_entries
from anibon.signal_detector import load_garbled_replacements
from anibon.transcript_source import is_youtube_auto_transcript

_get_compiled_garbled = compile_mapping_entries


def _scrub_speaker_drift(text: str) -> Tuple[str, int]:
    """Deterministically scrub speaker drift: 'ปู่บอท', 'ลุงบอท', 'ปู่โบต' -> 'ปู่โบ๊ต'."""
    return _SPEAKER_SCRUB_RE.subn("ปู่โบ๊ต", text)


def _apply_garbled_patterns(text: str, garbled: list) -> Tuple[str, int]:
    """Apply confirmed ground-truth replacements from garbled dictionary."""
    cleaned = text
    applied = 0
    for pattern, replacement in _get_compiled_garbled(garbled):
        cleaned, n = pattern.subn(replacement, cleaned)
        applied += n
    return cleaned, applied


def _apply_glossary_aliases(text: str, glossary: dict) -> Tuple[str, int]:
    """Replace non-canonical Thai aliases with canonical glossary entity names."""
    cleaned = text
    applied = 0
    for meta in glossary.values():
        if not isinstance(meta, dict):
            continue
        th = meta.get("th")
        alias_th = meta.get("alias_th")
        if alias_th and th and alias_th != th and alias_th in cleaned:
            matches = cleaned.count(alias_th)
            if matches:
                cleaned = cleaned.replace(alias_th, th)
                applied += matches
    return cleaned, applied


def _build_whitelisted_latin(glossary: dict) -> set[str]:
    """Compile set of allowed Latin words from stream tags and glossary keys."""
    whitelisted = {
        "talk", "gameplay", "gacha", "boss", "death", "victory", "watchparty",
        "reaction", "story", "lore", "review", "news", "chat", "donation", "greeting",
        "part", "switch", "dota", "lol", "fgo", "czn", "steam", "moba", "ps5", "pc",
        "skill", "parry", "spirit", "mario", "kart", "zelda", "boat", "anibon", "extra", "class",
        "arcane", "viktor", "abrams", "vindicta", "bebop", "shiv", "seven", "dynamo", "haze",
    }
    for k, meta in glossary.items():
        whitelisted.add(k.lower())
        if isinstance(meta, dict) and meta.get("en"):
            whitelisted.add(str(meta.get("en")).lower())
    return whitelisted


def _extract_unverified_latin(desc: str, whitelist: set[str]) -> list[str]:
    """Extract unverified capitalized Latin words from a single timestamp description."""
    unverified = []
    for word in re.findall(r"\b[A-Z][a-zA-Z0-9'\-]+\b", desc):
        if word.lower() not in whitelist:
            unverified.append(word)
    return unverified


def _detect_suspected_hallucinations(text: str, glossary: dict) -> list[str]:
    """Audit timestamp lines for unverified capitalized Latin words against tags and glossaries."""
    whitelist = _build_whitelisted_latin(glossary)
    suspected: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^\d{2}:\d{2}:\d{2}\s*-\s*(?:\[.*?\])+\s*(.*)$", line)
        if m:
            suspected.extend(_extract_unverified_latin(m.group(1), whitelist))
    return sorted(list(set(suspected)))


def sanitize_and_audit_timestamps(
    content: str,
    glossary: Optional[dict] = None,
    signals: Optional[dict] = None,
    garbled: Optional[list] = None,
) -> Tuple[str, dict]:
    """Deterministically sanitize timestamps, replace phonetic drifts, and audit hallucinations."""
    if not content:
        return "", {"corrections_applied": 0, "suspected_hallucinations": []}

    glossary = glossary or {}
    garbled = garbled or []

    cleaned, n_spk = _scrub_speaker_drift(content)
    cleaned, n_garb = _apply_garbled_patterns(cleaned, garbled)
    cleaned, n_alias = _apply_glossary_aliases(cleaned, glossary)
    suspected = _detect_suspected_hallucinations(cleaned, glossary)

    stats = {
        "corrections_applied": n_spk + n_garb + n_alias,
        "suspected_hallucinations": suspected,
    }
    return cleaned, stats


def _resolve_garbled_for_audit(timestamps_file: Path, garbled: Optional[list]) -> list:
    """Resolve garbled dictionary if not explicitly provided."""
    if garbled is not None:
        return garbled
    try:
        return load_garbled_replacements() if is_youtube_auto_transcript(timestamps_file.parent) else []
    except Exception:
        return []


def _run_stage5_world_sanitizer(content: str, workspace: Path) -> str:
    """Execute Stage 5 World Sanitizer (Pokémon naming, token stutter, outro injection)."""
    try:
        from anibon.world_sanitizer import audit_and_sanitize_final_markdown
        from anibon.topic_scanner import extract_macro_anchor
        info_f = workspace / "info.json"
        macro_anchor = None
        if info_f.is_file():
            try:
                macro_anchor = extract_macro_anchor(json.loads(info_f.read_text(encoding="utf-8")))
            except Exception:
                pass
        cleaned, _ = audit_and_sanitize_final_markdown(content, workspace, macro_anchor=macro_anchor)
        return cleaned
    except Exception as e:
        print(f"[audit] World sanitizer notice: {e}")
        return content


def _apply_audit_updates(timestamps_file: Path, content: str, cleaned: str, stats: dict) -> None:
    """Persist cleaned timestamps and report corrections and hallucination warnings."""
    replacements_count = stats.get("corrections_applied", 0)
    if cleaned != content:
        timestamps_file.write_text(cleaned, encoding="utf-8")
        print(f"[audit] Applied {replacements_count} glossary/phonetic corrections to {timestamps_file.name}")

    suspected = stats.get("suspected_hallucinations", [])
    if suspected:
        print(f"[audit] Warning: Suspected unverified entities in {timestamps_file.name}: {', '.join(suspected)}")


def audit_timestamps_against_glossary(
    timestamps_file: Path,
    glossary: dict,
    signals: Optional[dict] = None,
    garbled: Optional[list] = None,
) -> int:
    """Scan generated anibon_timestamps.md against entity_glossary.json and audit/replace mistranslations."""
    timestamps_file = Path(timestamps_file)
    if not timestamps_file.exists():
        return 0

    content = timestamps_file.read_text(encoding="utf-8")
    resolved_garbled = _resolve_garbled_for_audit(timestamps_file, garbled)
    cleaned, stats = sanitize_and_audit_timestamps(content, glossary=glossary, signals=signals, garbled=resolved_garbled)
    cleaned = _run_stage5_world_sanitizer(cleaned, timestamps_file.parent)
    _apply_audit_updates(timestamps_file, content, cleaned, stats)
    return stats.get("corrections_applied", 0)
