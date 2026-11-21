---
title: "assembly.py (lib/process/assembly.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/process/assembly.py"
tags: ["python", "script", "assembly", "pass2", "whisper", "parity-gates"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `assembly.py`

- **Source File**: [lib/process/assembly.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[process-chunks-local-py]], [[prompts-py]], [[audit-gaps-and-check-sections]], [[update-garbled-dictionary-py]]

## Purpose & Responsibility
Executes **Stage 3 & Pass 2 Final Assembly** after Pass 1 chunk inference completes. Writes `all_timestamps.txt`, validates dual-side mood, runs the `whisper.cpp` garbled-word collector on YouTube auto-transcripts, optionally verifies vision/reaction cues and prunes non-essential stamps, assembles macro-thematic `ส่วนที่ X` sections into `anibon_timestamps.md`, audits entities against the glossary, and executes parity gates.

## Key Functions & Public Contracts
- `finalize_and_assemble_timestamps(...) -> Tuple[Path, List[str]]` ([assembly.py:123-158](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L123-L158)): Main orchestrator entry called by [[process-chunks-local-py]]. Deduplicates and sorts `all_timestamps` chronologically by `ts_to_sec`, then runs:
  1. `_write_raw_timestamps(workspace, deduped)` ([assembly.py:30-36](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L30-L36)): Applies `clean_caveman_text()` to each line and writes `workspace / "all_timestamps.txt"`.
  2. `run_mood_validation(workspace, raw_ts)` ([assembly.py:141](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L141)): Validates `mood_555.json` alignment against `all_timestamps.txt`.
  3. `_collect_and_clean_garbled(...)` ([assembly.py:57-77](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L57-L77)): Unless `--no-garbled-collector` is set or `is_youtube_auto_transcript(workspace)` is `False`, invokes `run_garbled_collector(...)` and calls `_reload_cleaned_raw_timestamps()` ([assembly.py:39-54](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L39-L54)) to clear `_CLEANER_CACHE`, reload `garbled_replacements.json`, and re-clean `all_timestamps.txt` in-place.
  4. `_prune_and_verify_timestamps(...)` ([assembly.py:80-96](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L80-L96)): Applies `apply_vision_verify()` when `args` is passed, prunes to essential timestamps via `prune_essential()` unless `no_summarizer_pass` is `True`, and runs `apply_reaction_verify()` only when `args.post_reaction_verify` is enabled.
  5. `_assemble_parts_content(...)` ([assembly.py:99-120](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L99-L120)): Calls `run_local_summarizer_pass()` or falls back to heuristic double-border `assemble_parts()`. Enforces `enforce_line_cap(assembled, limit=LINE_WARN_LIMIT)` when the LLM summarizer ran, and optionally `enforce_byte_cap(assembled)` when `byte_cap` is `True`.
  6. Writes `workspace / "anibon_timestamps.md"`, runs `audit_timestamps_against_glossary()` if `glossary` is present ([assembly.py:151-154](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L151-L154)), and invokes `run_parity_gates(workspace, out_md)` ([assembly.py:157](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L157)).

## Error Handling & Invariants
- **Auto-Transcript Gate**: `run_garbled_collector()` is skipped for manual subtitles (`not is_youtube_auto_transcript(workspace)`), preventing unnecessary `whisper.cpp` runs.
- **Cache Busting After Collector**: `_reload_cleaned_raw_timestamps()` explicitly calls `_CLEANER_CACHE.clear()` ([assembly.py:41](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L41)) before `load_replacements()` so rules added by `run_garbled_collector` take effect immediately; if `all_timestamps.txt` is missing or yields no lines, it safely returns `fallback`.
- **Fallback Assembly**: If `run_local_summarizer_pass()` returns `None` or empty, `_assemble_parts_content()` transparently falls back to `assemble_parts(deduped, workspace, block_size)` ([assembly.py:113-115](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L113-L115)).
- **Post-Pass Reaction Verify Opt-In (`d3e997a`)**: `apply_reaction_verify()` is skipped unless `args.post_reaction_verify` is `True` because Pass 1 already receives packed webcam sheets in the Prep-First pipeline.
