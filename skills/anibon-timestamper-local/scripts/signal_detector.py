#!/usr/bin/env python3
"""Signal detector and domain knowledge resolver for local timestamper.

Re-exports the canonical signal detector implementation from lib/anibon/signal_detector.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from anibon.signal_constants import (
    AMBIGUOUS_SINGLE_TOKENS,
    ANIME_INSTRUCTION_BLOCK,
    ANIME_TAGS,
    COMMON_CHARACTER_NAMES_BLACKLIST,
    DUPE_TIER_RE,
    EXTENDED_CHAR_REPEAT_RE,
    GAME_SPECIAL_WORDS,
    GAMING_INSTRUCTION_BLOCK,
    GAMING_TAGS,
    GENERIC_GAMING_STANDING_WORDS,
    MULTI_SPACE_RE,
    MUSIC_NOTES_RE,
    NOISE_BRACKET_RE,
    SPEAKER_MARKER_RE,
    SPECIFIC_KINDS,
    SPECIFIC_TOKU_KEYWORDS,
    STAGE1_BLOCKED_EXTRA,
    TALK_INSTRUCTION_BLOCK,
    TALK_TAGS,
    TOKUSATSU_INSTRUCTION_BLOCK,
    TOKUSATSU_TAGS,
    _EXTENDED_CHAR_REPEAT_RE,
    _MULTI_SPACE_RE,
    _MUSIC_NOTES_RE,
    _NOISE_BRACKET_RE,
    _SPEAKER_MARKER_RE,
)
from anibon.signal_detector import (
    _process_single_chunk,
    clean_transcript_noise,
    compute_idf_stats,
    detect_signals_for_chunks,
    discover_reference_games,
    extract_chunk_text,
    extract_metadata_signals,
    filter_standing_gaming_words,
    get_domain_guidance,
    is_rule_doc,
    load_garbled_replacements,
    load_knowledge,
    load_mappings,
    match_chunk,
    normalize_transcript,
)

__all__ = [
    "AMBIGUOUS_SINGLE_TOKENS",
    "COMMON_CHARACTER_NAMES_BLACKLIST",
    "DUPE_TIER_RE",
    "GAME_SPECIAL_WORDS",
    "GENERIC_GAMING_STANDING_WORDS",
    "_EXTENDED_CHAR_REPEAT_RE",
    "_MULTI_SPACE_RE",
    "_MUSIC_NOTES_RE",
    "_NOISE_BRACKET_RE",
    "_SPEAKER_MARKER_RE",
    "_process_single_chunk",
    "clean_transcript_noise",
    "compute_idf_stats",
    "detect_signals_for_chunks",
    "discover_reference_games",
    "extract_chunk_text",
    "extract_metadata_signals",
    "filter_standing_gaming_words",
    "get_domain_guidance",
    "is_rule_doc",
    "load_garbled_replacements",
    "load_knowledge",
    "load_mappings",
    "match_chunk",
    "normalize_transcript",
]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run signal detection on workspace chunks.")
    parser.add_argument("workspace", type=Path, help="Path to stream workspace")
    parser.add_argument("--knowledge", type=Path, default=None, help="Custom knowledge.json path")
    args = parser.parse_args()

    results = detect_signals_for_chunks(args.workspace, args.knowledge)
    import json
    print(json.dumps(results, ensure_ascii=False, indent=2))
