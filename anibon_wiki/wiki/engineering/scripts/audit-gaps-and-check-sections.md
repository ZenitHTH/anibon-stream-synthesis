---
title: "audit_gaps.py & check_sections.py (scripts/audit_gaps.py, scripts/check_sections.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "scripts/audit_gaps.py"
tags: ["python", "script", "qa", "audit", "timestamps", "sections", "asr-garbles"]
sources: []
status: "active"
---

# `audit_gaps.py` & `check_sections.py`

- **Gap Auditor**: [scripts/audit_gaps.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py)
- **Section & Style Linter**: [scripts/check_sections.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[assembly-py]], [[update-garbled-dictionary-py]]

## Purpose & Responsibility
Post-generation QA validators that enforce Anibon timestamp invariants:
- **`audit_gaps.py`**: Enforces the `"NO GAPS"` rule across `all_timestamps.txt`, flagging chronological intervals exceeding a configurable threshold (default `600s` / 10 min) unless preceded by an intentional AFK/bathroom break.
- **`check_sections.py`**: Audits finalized `anibon_timestamps.md` files (and runs as a Claude/harness PreToolUse/PostToolUse hook) for section timestamp line counts (`LINE_WARN = 20`, `LINE_LIMIT = 25`), ASR garbled patterns, truncated `ส่วนที่ N:` headers, and repetitive opening verbs.

## Key Functions & CLI Contracts

### `scripts/audit_gaps.py`
- **CLI Arguments** ([audit_gaps.py:60-68](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L60-L68)):
  - `input`: Merged timestamp list file (e.g., `all_timestamps.txt`).
  - `--max-gap` (`int`, default `600`): Maximum allowed seconds between consecutive timestamps.
  - `--chunk-span` (`int`, default `300`): Chunk width in seconds for `chunk_for_ts()` gap-to-chunk mapping.
  - `--chunks-dir`: Optional chunks directory argument.
- `parse_timestamps(text)` ([audit_gaps.py:23-32](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L23-L32)): Extracts lines matching `^(\d\d:\d\d:\d\d)\s*-` (`LINE_RE`, [audit_gaps.py:20](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L20)) and sorts them by seconds.
- `is_afk_break_line(line)` ([audit_gaps.py:38-41](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L38-L41)): Checks `_AFK_BREAK_CUES = ("พักเบรก", "เข้าห้องน้ำ", "afk", "ขอพัก", "เบรกชั่วคราว")` ([audit_gaps.py:35](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L35)).
- `find_gaps(ts, max_gap_sec=600)` ([audit_gaps.py:44-51](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L44-L51)): Returns `(gap_sec, prev_line, next_line)` tuples when `g > max_gap_sec` and `prev_line` is not an AFK break.
- `chunk_for_ts(ts_str, chunk_span_sec=300)` ([audit_gaps.py:54-57](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L54-L57)): Maps `HH:MM:SS` to `chunk_{sec // chunk_span_sec:02d}` so orchestrators know which chunk to re-fill.

### `scripts/check_sections.py`
- **CLI Arguments** ([check_sections.py:109-116](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L109-L116)):
  - `file` (optional positional) or `--file` (`dest="file_flag"`, hook invocation): Target timestamp `.md` file.
  - `--no-garbled-check`: Skip scanning against `resources/asr_garbled_patterns.json` (`load_asr_garbled_patterns()`, [check_sections.py:11-18](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L11-L18)).
- **Section Line-Count Gate** ([check_sections.py:39-78](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L39-L78)):
  - Uses line count rather than UTF-8 byte count because Thai characters (~3 bytes/char) distort section balance (`LINE_WARN = 20`, `LINE_LIMIT = 25`).
  - `_full_blocks(text)` ([check_sections.py:45-52](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L45-L52)) parses `═══` + `ส่วนที่` blocks via `BLOCK_RE` ([check_sections.py:42](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L42)); `_evaluate_section_status(line_count)` flags `> 20` (`⚠️ WARN`) or `> 25` (`❌ OVER`) and calls `suggest_split()` ([check_sections.py:60-69](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L60-L69)) to suggest the line-midpoint timestamp.
- **Quality & Diversity Scans** ([check_sections.py:81-106](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L81-L106), [L162-L194](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L162-L194)):
  - `_scan_asr_garbles(text)`: Scans for compiled regexes from `asr_garbled_patterns.json`.
  - Header truncation check ([check_sections.py:173-185](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L173-L185)): Flags `ส่วนที่ N:` titles ending in dangling Thai conjunctions/prepositions or leading vowels (`[เแโใไ็]`).
  - `check_verb_diversity(text)` ([check_sections.py:84-96](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L84-L96)): When `>= 5` timestamp descriptions exist, warns if any opening verb in `_OPENING_VERBS` exceeds `20%` of lines or repeats `3×` consecutively.

## Error Handling & Invariants
- **`audit_gaps.py` Exit Codes**: Returns `0` when `< 2` timestamps exist or zero non-AFK gaps exceed `--max-gap`, and `1` when one or more gaps are found ([audit_gaps.py:72-87](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/audit_gaps.py#L72-L87)).
- **Hook-Safe Exits in `check_sections.py`**: Exits `0` if no file argument is passed, the target file does not yet exist (PreToolUse hook before `write_file`), or no `═══` blocks are found (unrelated `.md` writes) ([check_sections.py:118-133](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L118-L133)). Exits `1` only when a section exceeds `LINE_WARN` (`> 20` lines) ([check_sections.py:145-157](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/check_sections.py#L145-L157)); ASR garble, header truncation, and verb diversity checks emit warnings without failing the exit code.
