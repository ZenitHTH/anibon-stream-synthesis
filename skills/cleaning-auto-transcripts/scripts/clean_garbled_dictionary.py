#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_garbled_dictionary.py — Deterministic Cleaner & Normalizer for garbled_replacements.json.

Resolves:
1. Cascaded cleaner artifacts (Hogwall, True Vision, Wuthering Waves, etc.)
2. Case-insensitive duplicate target keys (Combat, Casual, Adblock, etc.)
3. Cross-target pattern collisions (ensuring 1 pattern -> 1 canonical target)
4. Word boundary protection (\\b) for short pure-ASCII patterns (AQ, CPL, etc.)
5. Removal of hazardous unanchored Thai/English patterns (โคโล, prat, sounder)
6. Canonical sorting and multi-location resource synchronization
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Paths
PLUGIN_ROOT = Path("/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis")
TARGET_FILES = [
    PLUGIN_ROOT / "resources" / "garbled_replacements.json",
    PLUGIN_ROOT / "skills" / "anibon-timestamper" / "resources" / "garbled_replacements.json"
]


def clean_dictionary():
    master_path = TARGET_FILES[0]
    if not master_path.is_file():
        print(f"[!] Error: {master_path} not found!", file=sys.stderr)
        return 1

    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    mappings = data.get("mappings", {})
    print(f"[*] Starting dictionary clean: {len(mappings)} initial target keys.")

    # --------------------------------------------------------------------------
    # 1. Specific Target & Cascaded Artifact Fixes
    # --------------------------------------------------------------------------

    # Fix Haschwalth (merge into single canonical key with restored phonetic stems)
    haschwalth_keys = ["ฮัชวาลด์ (Haschwalth)", "ฮัชวาลต์", "ฮัชวาลต์ (Haschwalth)"]
    haschwalth_patterns = ["Hogwallที่", "Hogwall", "Hogwอมัน", "กรมฮัชวา"]
    for k in haschwalth_keys:
        if k in mappings:
            del mappings[k]
    mappings["ฮัชวาลต์ (Haschwalth)"] = haschwalth_patterns

    # Fix True Vision
    if "True Vision" in mappings:
        mappings["True Vision"] = [
            p for p in mappings["True Vision"]
            if not p.startswith("NTE (Neverness to Everness)") and p != "True Vision"
        ]
        if "แบบูion" not in mappings["True Vision"]:
            mappings["True Vision"].append("แบบูion")

    # Fix Wuthering Waves cascaded patterns
    if "Wuthering Waves" in mappings:
        bad_ww = {
            "wutherwuthering wavessave", "wutherwuthering wavess",
            "wuthering wavesave", "winwuthering waves"
        }
        mappings["Wuthering Waves"] = [
            p for p in mappings["Wuthering Waves"]
            if p.lower().strip() not in bad_ww
        ]

    # Drop conversational fragment targets
    if "Wuthering Waves มาก" in mappings:
        del mappings["Wuthering Waves มาก"]

    if "milking หนักมาก" in mappings:
        del mappings["milking หนักมาก"]
        if "milking" not in mappings:
            mappings["milking"] = []
        if "หมักมาก" not in mappings["milking"]:
            mappings["milking"].append("หมักมาก")

    # Clean double-replaced patterns
    if "Silver Palace" in mappings:
        mappings["Silver Palace"] = [
            p for p in mappings["Silver Palace"] if p != "Silver Palaceace"
        ]
    if "no damage" in mappings:
        mappings["no damage"] = [p for p in mappings["no damage"] if p != "no damageเage"]
    if "คริติคอล" in mappings:
        mappings["คริติคอล"] = [p for p in mappings["คริติคอล"] if p != "crคริติคอล"]
    if "โดเนต" in mappings:
        mappings["โดเนต"] = [
            "donเนต" if p == "donโดเนต" else p for p in mappings["โดเนต"]
        ]

    # Remove dangerous unanchored / real word patterns
    dangerous_drops = {
        "Kuro Games": ["โคโล"],
        "Attack on Titan": ["ไตัน"],
        "Chowder": ["sounder"],
        "Predator": ["prat"],
        "Focus Sash": ["ฟูซ"],
        "สไตรค์วิทเชส (Strike Witches)": ["ไวิ"]
    }
    for target, drop_list in dangerous_drops.items():
        if target in mappings:
            mappings[target] = [p for p in mappings[target] if p not in drop_list]

    # --------------------------------------------------------------------------
    # 2. Case Normalization & Merging
    # --------------------------------------------------------------------------
    canonical_case_map = {
        "adblock": "Adblock",
        "casual": "Casual",
        "challenge": "Challenge",
        "combat": "Combat",
        "fate/extra record": "Fate/EXTRA Record",
        "genshin could never": "Genshin Could Never",
        "lego": "LEGO",
        "looper": "Looper",
        "meeting": "Meeting",
        "power harassment": "Power Harassment",
        "project": "Project",
        "ray tracing": "Ray Tracing",
        "tourist trap": "Tourist trap",
    }

    merged_by_canonical = defaultdict(list)
    for target, pats in list(mappings.items()):
        norm_key = target.lower().strip()
        final_target = canonical_case_map.get(norm_key, target)
        merged_by_canonical[final_target].extend(pats)

    mappings = dict(merged_by_canonical)

    # --------------------------------------------------------------------------
    # 3. Consolidate Near-Duplicate Targets (English vs English+Parenthetical)
    # --------------------------------------------------------------------------
    parenthetical_merges = {
        "พัซเซิล": "พัซเซิล (Puzzle)",
        "Wuthering Waves (WuWa)": "Wuthering Waves",
        "WuWa (Wuthering Waves)": "Wuthering Waves",
        "Zenless Zone Zero (ZZZ)": "Zenless Zone Zero",
        "Archetype Inception (ออร์ดีลคอล)": "Archetype Inception",
        "Interlude (อินเตอร์ลูด)": "Interlude",
        "Klub Outside (คลับเอาต์ไซด์)": "Klub Outside",
        "ลูเซีย": "Lucia",
        "อะชีฟเมนต์": "Achievement",
        "คอนเทนต์": "Content",
        "entropy": "แอนโทรปี (Entropy)",
        "NodusFall": "Nodus Fall",
    }

    for src_t, dst_t in parenthetical_merges.items():
        if src_t in mappings:
            src_pats = mappings.pop(src_t)
            if dst_t not in mappings:
                mappings[dst_t] = []
            mappings[dst_t].extend(src_pats)

    # --------------------------------------------------------------------------
    # 4. Enforce Word Boundaries on Short Pure-ASCII Patterns
    # --------------------------------------------------------------------------
    short_ascii_re = re.compile(r"^[A-Za-z0-9 ]{2,4}$")
    for target in list(mappings.keys()):
        updated_pats = []
        for p in mappings[target]:
            p_clean = p.strip()
            # If pattern is pure alphanumeric, 2-4 chars, and lacks regex boundary
            if short_ascii_re.match(p_clean) and "\\b" not in p_clean:
                bounded = rf"\b{p_clean}\b"
                updated_pats.append(bounded)
            else:
                updated_pats.append(p_clean)
        mappings[target] = updated_pats

    # --------------------------------------------------------------------------
    # 5. Global Deduplication & Clean-up
    # --------------------------------------------------------------------------
    seen_patterns = set()
    cleaned_mappings = {}

    # Sort target keys case-insensitively
    sorted_targets = sorted(mappings.keys(), key=lambda x: x.lower())

    for target in sorted_targets:
        raw_pats = mappings[target]
        unique_pats = []
        for p in raw_pats:
            p_strip = p.strip()
            if not p_strip:
                continue
            # Remove self-identical no-op
            if p_strip.lower() == target.lower():
                continue
            # Ensure pattern is unique across the entire dictionary (first target wins)
            p_norm = p_strip.lower()
            if p_norm in seen_patterns:
                continue
            seen_patterns.add(p_norm)
            unique_pats.append(p_strip)

        if unique_pats:
            # Sort patterns by length descending (longest / most specific first)
            unique_pats.sort(key=lambda x: len(x), reverse=True)
            cleaned_mappings[target] = unique_pats

    # --------------------------------------------------------------------------
    # 6. Save and Synchronize
    # --------------------------------------------------------------------------
    output_payload = {
        "version": 2,
        "description": "Canonical word -> list of garbled phonetic patterns",
        "note": "First-match wins. Within each word, longer/more specific patterns are tried first.",
        "mappings": cleaned_mappings
    }

    total_patterns = sum(len(p) for p in cleaned_mappings.values())
    print(f"[✓] Refactored dictionary: {len(cleaned_mappings)} canonical targets, {total_patterns} unique patterns.")

    for path in TARGET_FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, ensure_ascii=False, indent=2)
        print(f"[+] Saved & Synchronized: {path}")

    # Copy script into plugin's scripts dir as well
    plugin_script_path = PLUGIN_ROOT / "skills" / "cleaning-auto-transcripts" / "scripts" / "clean_garbled_dictionary.py"
    with open(plugin_script_path, "w", encoding="utf-8") as f:
        with open(__file__, "r", encoding="utf-8") as src:
            f.write(src.read())
    os.chmod(plugin_script_path, 0o755)
    print(f"[+] Installed script at: {plugin_script_path}")

    return 0


if __name__ == "__main__":
    sys.exit(clean_dictionary())
