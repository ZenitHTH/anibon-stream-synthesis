#!/usr/bin/env python3
"""Manage and auto-update the garbled-English replacement dictionary.

Supports the Version 2 Grouped Schema where canonical target words map to
lists of garbled phonetic noise patterns:
{
  "version": 2,
  "description": "Canonical word -> list of garbled phonetic patterns",
  "note": "Compiled with re.IGNORECASE. Specific/longer patterns take precedence.",
  "mappings": {
    "TargetWord": [
      "noise_pattern_1",
      "noise_pattern_2"
    ]
  }
}

Usage:
  # Add single or multiple patterns to a target word
  python3 update_garbled_dictionary.py --add "Roblox" "Rob[oล]อก" "Rock One"

  # Import confirmed rules from garbled_notes.json
  python3 update_garbled_dictionary.py --from-notes ~/workspace/garbled_notes.json

  # Consolidate raw subagent notes from workspace & sync dictionary
  python3 update_garbled_dictionary.py --from-raw-dir ~/workspace/garbled_notes_raw/ --workspace ~/workspace

  # Re-sync and validate dictionary files across plugin locations
  python3 update_garbled_dictionary.py --sync-only
"""

import os
import sys
import json
import re
import glob
import argparse
from pathlib import Path

# Locate plugin root and target resource files
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parents[2]  # from skills/cleaning-auto-transcripts/scripts -> plugin root

TARGET_FILES = [
    _PLUGIN_ROOT / "resources" / "garbled_replacements.json",
    _PLUGIN_ROOT / "skills" / "anibon-timestamper" / "resources" / "garbled_replacements.json"
]


def load_master_dictionary() -> tuple[dict[str, list[str]], str]:
    """Load existing dictionary, merging from all available copies, supporting v1 and v2 formats."""
    merged_mappings: dict[str, list[str]] = {}
    description = "Canonical word -> list of garbled phonetic patterns"

    for path in TARGET_FILES:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] Warning: failed to parse {path}: {e}", file=sys.stderr)
            continue

        description = data.get("description", description)

        # Version 2 schema: "mappings": { "Target": ["pat1", "pat2"] }
        if "mappings" in data and isinstance(data["mappings"], dict):
            for target, patterns in data["mappings"].items():
                target_str = str(target).strip()
                if not target_str:
                    continue
                if target_str not in merged_mappings:
                    merged_mappings[target_str] = []
                pats = patterns if isinstance(patterns, list) else [patterns]
                for p in pats:
                    p_str = str(p).strip()
                    if p_str and p_str not in merged_mappings[target_str]:
                        merged_mappings[target_str].append(p_str)

        # Version 1 schema fallback: "replacements": [ {"pattern": "...", "replacement": "..."} ]
        elif "replacements" in data and isinstance(data["replacements"], list):
            for entry in data["replacements"]:
                rep = str(entry.get("replacement", "")).strip()
                pat = str(entry.get("pattern", "")).strip()
                if not rep or not pat:
                    continue
                if rep not in merged_mappings:
                    merged_mappings[rep] = []
                if pat not in merged_mappings[rep]:
                    merged_mappings[rep].append(pat)

    return merged_mappings, description


# Known real franchise/game titles and common phrases that must never be used as noise replacement patterns
_BLOCKED_SUBSTRINGS = [
    "Marvel Tōkon",
    "Alien: Isolation",
    "TMNT",
    "God of War",
    "Rayman Legends",
    "Velina & Norma",
    "Control: Resonant",
]

_EXACT_BLOCKED_PATTERNS = {
    "rock one",
    "where we meet",
    "where meet",
    "wherein meet",
}


def is_blocked_pattern(target: str, pattern: str) -> tuple[bool, str]:
    """Check if a pattern is a real game title or common phrase that shouldn't be overwritten."""
    p_lower = pattern.lower().strip()
    if p_lower in _EXACT_BLOCKED_PATTERNS:
        return True, "matches blocked common phrase / false positive"
    for bs in _BLOCKED_SUBSTRINGS:
        if bs.lower() in p_lower and bs.lower() not in target.lower():
            return True, f"contains protected game/brand name '{bs}'"
    return False, ""


def validate_and_sort_mappings(mappings: dict[str, list[str]]) -> dict[str, list[str]]:
    """Validate all regex patterns, filter false-positives, and sort canonical words & patterns."""
    clean_mappings: dict[str, list[str]] = {}

    for target in sorted(mappings.keys(), key=lambda s: s.lower()):
        patterns = mappings[target]
        valid_patterns = []
        for p in patterns:
            p_clean = p.strip()
            if not p_clean:
                continue

            blocked, reason = is_blocked_pattern(target, p_clean)
            if blocked:
                print(f"[!] Blocked bad pattern for '{target}': '{p_clean}' ({reason}) - Skipping", file=sys.stderr)
                continue

            try:
                re.compile(p_clean, re.IGNORECASE)
                if p_clean not in valid_patterns:
                    valid_patterns.append(p_clean)
            except re.error as err:
                print(f"[!] Invalid regex pattern for '{target}': '{p_clean}' ({err}) - Skipping", file=sys.stderr)

        if valid_patterns:
            # Sort patterns by length descending (more specific patterns first)
            valid_patterns.sort(key=lambda s: len(s), reverse=True)
            clean_mappings[target] = valid_patterns

    return clean_mappings



def save_dictionary(mappings: dict[str, list[str]], description: str = "") -> None:
    """Save sorted & validated dictionary to all target files atomically."""
    clean_mappings = validate_and_sort_mappings(mappings)
    total_patterns = sum(len(pats) for pats in clean_mappings.values())

    payload = {
        "version": 2,
        "description": description or "Canonical word -> list of garbled phonetic patterns",
        "note": "First-match wins. Within each word, longer/more specific patterns are tried first.",
        "mappings": clean_mappings
    }

    formatted_json = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    for target_path in TARGET_FILES:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")
        temp_path.write_text(formatted_json, encoding="utf-8")
        temp_path.replace(target_path)
        print(f"[+] Synchronized {target_path} ({len(clean_mappings)} words, {total_patterns} patterns)")


def add_patterns(mappings: dict[str, list[str]], target: str, patterns: list[str]) -> int:
    """Add new patterns to a target canonical word. Returns count of newly added patterns."""
    target = target.strip()
    if not target:
        return 0
    if target not in mappings:
        mappings[target] = []
    added = 0
    for p in patterns:
        p_clean = p.strip()
        if p_clean and p_clean not in mappings[target]:
            mappings[target].append(p_clean)
            added += 1
    return added


def import_from_notes_json(mappings: dict[str, list[str]], notes_file: Path) -> int:
    """Import confirmed rules from a garbled_notes.json file."""
    if not notes_file.is_file():
        print(f"[!] Notes file not found: {notes_file}", file=sys.stderr)
        return 0
    data = json.loads(notes_file.read_text(encoding="utf-8"))
    notes = data.get("notes", [])
    added = 0
    for item in notes:
        correct = item.get("correct")
        garbled = item.get("garbled")
        if correct and garbled:
            added += add_patterns(mappings, correct, [garbled])
    return added


def parse_raw_notes_dir(raw_dir: Path) -> tuple[list[dict], dict[str, list[str]]]:
    """Parse raw GARBLED_NOTES text files emitted by subagents."""
    candidates = []
    confirmed_rules: dict[str, list[str]] = {}

    for fpath in sorted(glob.glob(str(raw_dir / "*.txt"))):
        chunk_group = Path(fpath).stem
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("GARBLED_NOTES"):
                continue

            # Match format: "garbled" -> correct @ ts (chunk_NN)
            # e.g.: "doม day" -> Doomsday @ 00:05:23 (chunk_01)
            # or: "ABORช" -> UNKNOWN @ 03:02:38 (chunk_40)
            m = re.search(r'"([^"]+)"\s*->\s*([^@]+?)(?:\s*@\s*(\d{2}:\d{2}:\d{2}))?(?:\s*\(([^)]+)\))?$', line)
            if m:
                garbled = m.group(1).strip()
                correct_raw = m.group(2).strip()
                ts = m.group(3) or ""
                chunk = m.group(4) or chunk_group

                is_unknown = correct_raw.upper() in ["UNKNOWN", "NULL", "NONE"] or not correct_raw
                correct = None if is_unknown else correct_raw

                candidates.append({
                    "garbled": garbled,
                    "correct": correct,
                    "chunk": chunk,
                    "ts": ts,
                    "context": f"Candidate from {chunk} ({ts})"
                })

                if correct:
                    if correct not in confirmed_rules:
                        confirmed_rules[correct] = []
                    if garbled not in confirmed_rules[correct]:
                        confirmed_rules[correct].append(garbled)

    return candidates, confirmed_rules


def main():
    parser = argparse.ArgumentParser(description="Update and sync garbled English replacement dictionary.")
    parser.add_argument("--add", nargs="+", metavar=("TARGET", "PATTERN"),
                        help="Add one or more patterns to a target canonical word: --add 'Target' 'pattern1' 'pattern2'")
    parser.add_argument("--from-notes", type=Path, help="Path to garbled_notes.json to import")
    parser.add_argument("--from-raw-dir", type=Path, help="Path to garbled_notes_raw directory")
    parser.add_argument("--workspace", type=Path, help="Workspace directory to save consolidated garbled_notes.json")
    parser.add_argument("--sync-only", action="store_true", help="Sync, validate, and format existing dictionary files")

    args = parser.parse_args()

    mappings, description = load_master_dictionary()
    initial_patterns = sum(len(pats) for pats in mappings.values())
    print(f"[*] Loaded master dictionary: {len(mappings)} canonical words, {initial_patterns} patterns")

    modified = False

    if args.add:
        target = args.add[0]
        patterns = args.add[1:]
        added = add_patterns(mappings, target, patterns)
        print(f"[*] Added {added} pattern(s) for target '{target}'")
        modified = True

    if args.from_notes:
        added = import_from_notes_json(mappings, args.from_notes)
        print(f"[*] Imported {added} pattern(s) from {args.from_notes}")
        modified = True

    if args.from_raw_dir:
        candidates, confirmed = parse_raw_notes_dir(args.from_raw_dir)
        print(f"[*] Extracted {len(candidates)} candidate(s) from {args.from_raw_dir}")

        for target, pats in confirmed.items():
            add_patterns(mappings, target, pats)
        modified = True

        if args.workspace:
            out_notes = args.workspace / "garbled_notes.json"
            notes_payload = {
                "version": 1,
                "notes": candidates
            }
            out_notes.write_text(json.dumps(notes_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[+] Wrote consolidated notes to {out_notes}")

    if args.sync_only or modified or not any([args.add, args.from_notes, args.from_raw_dir]):
        save_dictionary(mappings, description)

    final_patterns = sum(len(pats) for pats in mappings.values())
    print(f"[*] Completed! Master dictionary now has {len(mappings)} canonical words, {final_patterns} patterns.")


if __name__ == "__main__":
    main()
