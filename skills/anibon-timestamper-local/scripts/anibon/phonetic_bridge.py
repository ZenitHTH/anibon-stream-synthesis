"""Thai phonetic bridge module for Whisper speech-to-text proper nouns.

Bridges spoken Thai phonemes and transliterations into canonical English entities
and franchise domains, preventing SQLite exact-match misses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

_CACHED_BRIDGE: Optional[Dict[str, Any]] = None


def load_phonetic_bridge(
    search_dirs: Optional[List[Path]] = None,
    force_reload: bool = False,
) -> Dict[str, Any]:
    """Load thai_phonetic_bridge.json from standard candidate reference paths."""
    global _CACHED_BRIDGE
    if _CACHED_BRIDGE is not None and not force_reload:
        return _CACHED_BRIDGE

    script_dir = Path(__file__).resolve().parent
    candidates: List[Path] = []
    if search_dirs:
        for d in search_dirs:
            if d and Path(d).is_dir():
                candidates.append(Path(d) / "thai_phonetic_bridge.json")

    standard_paths = [
        script_dir.parent.parent.parent / "anibon-world-identity" / "references" / "thai_phonetic_bridge.json",
        script_dir.parent.parent / "references" / "thai_phonetic_bridge.json",
        script_dir.parent.parent / "references" / "stream" / "thai_phonetic_bridge.json",
    ]
    candidates.extend(standard_paths)

    for target in candidates:
        if target.is_file():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                mappings = data.get("mappings", data)
                if isinstance(mappings, dict):
                    _CACHED_BRIDGE = mappings
                    return _CACHED_BRIDGE
            except Exception:
                continue

    _CACHED_BRIDGE = {}
    return _CACHED_BRIDGE


def match_phonemes(
    text: str,
    bridge: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Match Thai Whisper text against phonetic bridge dictionary."""
    if not text:
        return []

    active_bridge = bridge if bridge is not None else load_phonetic_bridge()
    text_lower = text.lower()
    matches: List[Dict[str, Any]] = []
    seen: set = set()

    for phoneme_key, meta in active_bridge.items():
        if not isinstance(meta, dict):
            continue
        key_lower = phoneme_key.lower()
        if key_lower in text_lower:
            en = meta.get("en", phoneme_key)
            if en in seen:
                continue
            seen.add(en)
            entry = dict(meta)
            entry["matched_phoneme"] = phoneme_key
            matches.append(entry)

    return matches
