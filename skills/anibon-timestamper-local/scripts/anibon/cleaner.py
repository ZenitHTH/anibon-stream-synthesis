"""Text cleaning utilities for garbled English and transcript correction.

Consumers (before extraction):
  clean_text          — clean_garbled_english.py:44, _chunker.py:8 (2 impls)
  clean_chunk         — clean_garbled_english.py:51
  scan_garbles        — check_sections.py:87
  load_replacements   — clean_garbled_english.py:30
"""
import re
import json
from pathlib import Path


# ── Garbled-English cleaning (regex-based) ────────────────────────────────


def load_replacements(path: Path) -> list[tuple[re.Pattern, str]]:
    """Load garbled→correct replacements from JSON config.

    Expected format: {"replacements": [{"pattern": "...", "replacement": "..."}]}
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    compiled = []
    for entry in data.get("replacements", []):
        compiled.append((re.compile(entry["pattern"], re.IGNORECASE), entry["replacement"]))
    return compiled


def clean_text(text: str, compiled: list[tuple[re.Pattern, str]] | None = None) -> str:
    """Apply all garbled-English regex replacements to a text string.

    If compiled is None, returns text unchanged (no-op fallback).
    """
    if not compiled:
        return text
    for pattern, replacement in compiled:
        text = pattern.sub(replacement, text)
    return text


def clean_chunk(data: dict, compiled: list[tuple[re.Pattern, str]] | None = None) -> list:
    """Clean all item['text'] fields in a chunk JSON structure.

    Returns list of (original, cleaned) tuples for changed items.
    """
    changes = []
    for item in data.get("items", []):
        orig = item.get("text", "")
        cleaned = clean_text(orig, compiled)
        if cleaned != orig:
            changes.append((orig, cleaned))
            item["text"] = cleaned
    return changes


# ── Transcript correction (mapping-dict based) ────────────────────────────


def correct_transcript(transcript: list, mappings: dict) -> list:
    """Apply text correction mappings to a transcript in-place.

    Mappings format: {"mappings": [{"patterns": [...], "correct": "...", "exclude_if_contains": [...]}]}
    """
    for item in transcript:
        text = re.sub(r"\s+", " ", item["text"]).strip()
        for mapping in mappings.get("mappings", []):
            for pat in mapping.get("patterns", []):
                excludes = mapping.get("exclude_if_contains", [])
                if any(re.search(re.escape(ex), text, re.I) for ex in excludes):
                    continue
                text = re.sub(re.escape(pat), lambda m: mapping["correct"], text, flags=re.I)
        item["text"] = text
    return transcript


# ── ASR garbled pattern scan (used by check_sections.py) ─────────────────


def load_asr_garbled_patterns(path: Path) -> list[tuple[re.Pattern, str]]:
    """Load ASR garbled patterns from JSON config.

    Expected format: {"patterns": [{"pattern": "...", "message": "..."}]}
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    compiled = []
    for entry in data.get("patterns", []):
        compiled.append((re.compile(entry["pattern"]), entry["message"]))
    return compiled


def scan_garbles(text: str, patterns: list[tuple[re.Pattern, str]]) -> list[str]:
    """Scan text for known ASR garbled patterns. Returns list of warning strings."""
    warnings = []
    for pattern, msg in patterns:
        matches = re.findall(pattern, text)
        if matches:
            warnings.append(f"  ⚠  Found {len(matches)}× {msg}")
    return warnings
