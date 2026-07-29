# Timestamper Quality Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans.

**Goal:** Fix 9 quality gaps in anibon-timestamper pipeline identified from VHsF4Ov5MnM stream analysis.

**Architecture:** 3 script edits (prompt template, pack, merge) + 2 new scripts (validate_tags, detect_boundaries) + 1 test file.

**Tech Stack:** Python 3.14, json, re, argparse, pathlib, collections.Counter

## Files Changed

- `skills/anibon-timestamper/subagent-prompt-template.md` — fix contradiction, add tag examples, activity-change rule
- `skills/anibon-timestamper/scripts/pack_timestamps.py` — topic-label heading support
- `skills/anibon-timestamper/scripts/merge_timestamps.py` — fuzzy dedup
- `skills/anibon-timestamper/scripts/validate_tags.py` — NEW: tag validation + retag
- `skills/anibon-timestamper/scripts/detect_boundaries.py` — NEW: topic boundary detection with n-gram sim + label auto-gen
- `skills/anibon-timestamper/tests/test_validate_tags.py` — NEW: validator tests

## Tasks

### Task 1: Prompt template edits (3 fixes in 1 file)

**File:** `subagent-prompt-template.md`

Edits:
1. Line 44-51: Change "output 0 timestamps" rule → "output 1 with broader summary" for continuing same topic. Remove "0 is allowed" from line 44. Change line 51 from "output 0 timestamps" to "output 1 timestamp with a broader summary covering both chunks".
2. Add tag classification examples: after line 81 (tag list), add usage examples per tag with correct/incorrect patterns.
3. Line 45-49: Add "activity-change rule" bullet: "Activity change within same game (e.g., walking overworld → boss fight) is a valid timestamp trigger, even if game hasn't changed."

### Task 2: validate_tags.py (new)

**File:** `scripts/validate_tags.py`

Logic:
- Load all_timestamps.txt
- For each line: parse HH:MM:SS - [Tag] Description
- Validate tag matches description keywords (boss keywords → [Boss], death keywords → [Death], victory keywords → [Victory])
- If mismatch: retag the line (do NOT split)
- Output corrected timestamps + report stats

Example bad: `00:15:30 - [Gameplay] Fighting god boss` → retag `[Boss]`
Example good: no change

### Task 3: merge_timestamps.py fuzzy dedup

**File:** `scripts/merge_timestamps.py`

Insert after exact dedup (line 29): fuzzy dedup using prefix overlap. If two lines share same HH:MM prefix (first 8 chars) AND first 30 chars of description Levenshtein ratio > 0.85 → keep the first, drop second.

### Task 4: pack_timestamps.py topic-label headings

**File:** `scripts/pack_timestamps.py`

When `--topic-json` is provided AND topic labels exist, the part heading in `_group_to_part()` currently uses generic first-entry desc. Change: if group is the first group for a topic label, use the topic label as heading instead.

This requires passing topic label info through the pipeline: `cluster_by_topic()` already assigns labels to segments → need to store label on group and use it in `_group_to_part()`.

### Task 5: detect_boundaries.py (new, includes label auto-gen)

**File:** `scripts/detect_boundaries.py`

Pipeline:
1. Load chunks dir + signals.json
2. For each adjacent chunk pair: compute character 3-gram Jaccard similarity
3. If similarity < threshold (0.3) AND both chunks have non-zero signal scores → mark boundary
4. Fallback: if signals are flat (both zero), use longest silent gap between transcript items (from timestamps)
5. Output topics.json with `{start, end, label}` per section
6. `--generate-labels` flag: auto-generate label from dominant game signal + top keywords in first chunk

### Task 6: test_validate_tags.py

**File:** `tests/test_validate_tags.py`

Test cases:
- Boss keyword → retag [Gameplay] to [Boss]
- Death keyword → retag [Gameplay] to [Death]
- Victory keyword → retag [Gameplay] to [Victory]
- Already correct tag → unchanged
- Empty input → empty output
- No matching keywords → unchanged
