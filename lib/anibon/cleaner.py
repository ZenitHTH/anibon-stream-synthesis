"""Text cleaning utilities for garbled English and transcript correction.

Consumers:
  clean_text          — clean_garbled_english.py, pack_timestamps.py
  clean_chunk         — clean_garbled_english.py
  scan_garbles        — check_sections.py
  load_replacements   — clean_garbled_english.py, whisper_dispatcher.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from anibon.resources import resource_path

_REGEX_META_RE = re.compile(r"\\b|\\B|\\d|\\w|\\s|[\[\]()^$?*+{|]")
_SPEAKER_SCRUB_RE = re.compile(r"(?:ปู่บอท|ลุงบอท|ปู่โบต)")
_CACHE: dict[Path, list[tuple[re.Pattern, str]]] = {}
_MAPPINGS_CACHE: dict[tuple, list[tuple[re.Pattern, str]]] = {}


def compile_pattern(pat: str, flags: int = re.IGNORECASE) -> re.Pattern:
    """Compile a pattern string, preserving regex metacharacters (\b, etc.) or escaping literals."""
    expr = pat if _REGEX_META_RE.search(pat) else re.escape(pat)
    return re.compile(expr, flags)


_compile_pattern = compile_pattern


def compile_mapping_entries(mappings: list[dict] | tuple) -> list[tuple[re.Pattern, str]]:
    """Compile mapping entries [{"correct": str, "patterns": [str, ...]}] into regex pairs.

    Safe caching keyed by contents rather than object identity.
    """
    if not mappings:
        return []

    key_items = []
    for item in mappings:
        c = item.get("correct") or ""
        pats = tuple(item.get("patterns") or ())
        key_items.append((c, pats))
    cache_key = tuple(key_items)

    if cache_key in _MAPPINGS_CACHE:
        return _MAPPINGS_CACHE[cache_key]

    compiled: list[tuple[re.Pattern, str]] = []
    for item in mappings:
        correct = item.get("correct")
        patterns = item.get("patterns", [])
        if not correct or not patterns:
            continue
        for pat in patterns:
            if not pat:
                continue
            try:
                compiled.append((compile_pattern(pat), correct))
            except re.error:
                continue

    _MAPPINGS_CACHE[cache_key] = compiled
    return compiled


def load_replacements(path: Path | None = None) -> list[tuple[re.Pattern, str]]:
    """Load garbled->correct replacements supporting v2 schema, flat dict, and v1 replacements."""
    target_path = Path(path) if path else resource_path("garbled_replacements.json")
    if target_path in _CACHE:
        return _CACHE[target_path]
    if not target_path.is_file():
        return []

    data = json.loads(target_path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []

    if isinstance(data.get("mappings"), dict):
        for canonical, patterns in data["mappings"].items():
            pats = patterns if isinstance(patterns, list) else [patterns]
            for p in pats:
                if p and str(p).strip():
                    pairs.append((str(p).strip(), str(canonical).strip()))

    for k, v in data.items():
        if k in ("version", "description", "note", "mappings", "replacements"):
            continue
        if isinstance(v, str) and k.strip():
            pairs.append((k.strip(), v.strip()))
        elif isinstance(v, list):
            for p in v:
                if p and str(p).strip():
                    pairs.append((str(p).strip(), k.strip()))

    for entry in data.get("replacements", []):
        pat = entry.get("pattern", "").strip()
        rep = entry.get("replacement", "").strip()
        if pat:
            pairs.append((pat, rep))

    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    compiled: list[tuple[re.Pattern, str]] = [(_SPEAKER_SCRUB_RE, "ปู่โบ๊ต")]
    for pat, rep in pairs:
        try:
            compiled.append((_compile_pattern(pat), rep))
        except re.error:
            continue

    _CACHE[target_path] = compiled
    return compiled


def clean_text_with_count(
    text: str, compiled: list[tuple[re.Pattern, str]] | None = None
) -> tuple[str, int]:
    """Apply all garbled-English regex replacements to text string, returning (cleaned, count)."""
    if not text:
        return "", 0
    active = compiled if compiled is not None else load_replacements()
    total_changes = 0
    for pattern, replacement in active:
        text, n = pattern.subn(replacement, text)
        total_changes += n
    return text, total_changes


def clean_text(
    text: str, compiled: list[tuple[re.Pattern, str]] | None = None
) -> str:
    """Apply all garbled-English regex replacements to a text string."""
    cleaned, _ = clean_text_with_count(text, compiled)
    return cleaned


def clean_chunk(data: dict, compiled: list[tuple[re.Pattern, str]] | None = None) -> list:
    """Clean all item['text'] fields in a chunk JSON structure.

    Returns list of (original, cleaned) tuples for changed items.
    """
    changes = []
    active = compiled if compiled is not None else load_replacements()
    for item in data.get("items", []):
        orig = item.get("text", "")
        cleaned = clean_text(orig, active)
        if cleaned != orig:
            changes.append((orig, cleaned))
            item["text"] = cleaned
    return changes


# ── Transcript correction (mapping-dict based) ────────────────────────────


def correct_transcript(transcript: list, mappings: dict) -> list:
    """Apply text correction mappings to a transcript in-place."""
    precompiled = []
    for mapping in mappings.get("mappings", []):
        correct = mapping.get("correct", "")
        excludes = [compile_pattern(ex) for ex in mapping.get("exclude_if_contains", []) if ex]
        pats = [compile_pattern(pat) for pat in mapping.get("patterns", []) if pat]
        precompiled.append((pats, correct, excludes))

    for item in transcript:
        text = re.sub(r"\s+", " ", item.get("text", "")).strip()
        for pats, correct, excludes in precompiled:
            if any(ex.search(text) for ex in excludes):
                continue
            for pat in pats:
                text = pat.sub(correct, text)
        item["text"] = text
    return transcript


# ── ASR garbled pattern scan (used by check_sections.py) ─────────────────


def load_asr_garbled_patterns(path: Path) -> list[tuple[re.Pattern, str]]:
    """Load ASR garbled patterns from JSON config."""
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
