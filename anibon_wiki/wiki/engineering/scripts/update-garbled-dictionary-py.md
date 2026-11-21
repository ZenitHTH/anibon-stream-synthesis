---
title: "update_garbled_dictionary.py (skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py"
tags: ["python", "script", "dictionary", "asr", "garbled", "cleaning"]
sources: []
status: "active"
---

# `update_garbled_dictionary.py`

- **Source File**: [skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py)
- **Target Dictionary**: [resources/garbled_replacements.json](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/resources/garbled_replacements.json)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[assembly-py]], [[prepare-video-py]], [[audit-gaps-and-check-sections]]

## Purpose & Responsibility
Canonical CLI tool for maintaining `resources/garbled_replacements.json` in **Schema v2** (`"version": 2`, `"mappings": {CanonicalTarget: [noise_pattern, ...]}`). Prevents raw JSON corruption, blocks dangerous substring/short-ASCII regex collisions, consolidates subagent `garbled_notes_raw/` candidates into `garbled_notes.json`, writes atomically, and optionally re-cleans workspace chunks and timestamp files in place.

## Key Functions & CLI Contracts
- **CLI Arguments** ([update_garbled_dictionary.py:264-273](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L264-L273)):
  - `--add TARGET PATTERN [PATTERN ...]`: Add one or more phonetic noise patterns under a canonical target word.
  - `--from-notes PATH`: Import confirmed `{correct, garbled}` entries from `garbled_notes.json`.
  - `--from-raw-dir PATH`: Parse `*.txt` files in `garbled_notes_raw/`, auto-add confirmed rules, and optionally emit consolidated `garbled_notes.json` when `--workspace` is set.
  - `--workspace PATH`: Target stream workspace for writing `garbled_notes.json` and re-running cleanup across `chunks/` and timestamp outputs.
  - `--sync-only`: Validate, deduplicate, sort, and re-write the master dictionary without adding entries.
- `load_master_dictionary()` ([update_garbled_dictionary.py:51-93](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L51-L93)): Reads `TARGET_FILES` (`resources/garbled_replacements.json`), supporting both Schema v2 (`"mappings"`) and legacy Schema v1 (`"replacements"`).
- `is_blocked_pattern(target, pattern)` ([update_garbled_dictionary.py:115-127](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L115-L127)): Rejects unsafe patterns before compilation:
  1. Exact matches in `_EXACT_BLOCKED_PATTERNS` (`"rock one"`, `"where we meet"`, `"where meet"`, `"wherein meet"`, [update_garbled_dictionary.py:107-112](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L107-L112)).
  2. Proper-substring collisions where `p_lower in target.lower()` and `len(p_lower) < len(target.strip())`.
  3. Pure-ASCII patterns shorter than 5 characters (`pattern.strip().isascii() and len(pattern.strip()) < 5`).
  4. Patterns containing protected brand/game titles in `_BLOCKED_SUBSTRINGS` (`"Marvel Tōkon"`, `"Alien: Isolation"`, `"TMNT"`, `"God of War"`, `"Rayman Legends"`, `"Velina & Norma"`, `"Control: Resonant"`, [update_garbled_dictionary.py:97-105](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L97-L105)) unless also present in `target`.
- `validate_and_sort_mappings(mappings)` ([update_garbled_dictionary.py:130-159](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L130-L159)): Filters blocked patterns, compiles each with `re.IGNORECASE` (skipping invalid regexes), sorts canonical keys case-insensitively, and sorts patterns per key by descending length (longest/most specific match first).
- `save_dictionary(mappings, description)` ([update_garbled_dictionary.py:163-182](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L163-L182)): Writes validated Schema v2 JSON to a `.tmp` sibling file and atomically replaces `target_path`.
- `parse_raw_notes_dir(raw_dir)` ([update_garbled_dictionary.py:219-261](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L219-L261)): Extracts `"garbled" -> correct @ HH:MM:SS (chunk_NN)` lines; treats `UNKNOWN`, `NULL`, and `NONE` as unconfirmed (`correct = None`) candidates without adding them to the dictionary.
- **Workspace Re-Cleaning** ([update_garbled_dictionary.py:317-346](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py#L317-L346)): When `--workspace` exists, executes `clean_garbled_english.py --chunks` on `workspace/chunks/` and re-cleans `all_timestamps.txt`, `anibon_timestamps.md`, `anibon_timestamps_essential.md`, and `anibon_timestamps_full.md` in-place.

## Error Handling & Invariants
- **Atomic Persistence**: Writing to `.tmp` followed by `Path.replace()` ensures `garbled_replacements.json` is never left partially written on crash.
- **Regex & Substring Safety**: Invalid regexes (`re.error`) and collision-prone patterns are logged to `stderr` and skipped rather than aborting the sync, preserving existing valid mappings.
- **Schema Preservation**: Always upgrades/normalizes loaded entries to Schema v2 on save; direct raw `dict.update()` edits to `garbled_replacements.json` are forbidden by plugin policy.
