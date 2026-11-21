---
title: "process_chunks_local.py (skills/anibon-timestamper-local/scripts/process_chunks_local.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "skills/anibon-timestamper-local/scripts/process_chunks_local.py"
tags: ["python", "script", "entrypoint", "pass1", "pass2", "local"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `process_chunks_local.py`

- **Source File**: [skills/anibon-timestamper-local/scripts/process_chunks_local.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py)
- **Unit Tests**: [tests/test_prep_first_order.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_prep_first_order.py), [tests/test_post_reaction_optin.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_post_reaction_optin.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[dynamic-chunk-py]], [[prompts-py]]

## Purpose & Responsibility
Main CLI orchestrator for `anibon-timestamper-local`. Coordinates Stage 2 Prep-First Enrichment (`_run_prep_stage`), domain signal/glossary loading, Pass 1 VLM chunk timestamping, Stage 3 acoustic garbled verification (`whisper.cpp`), and Pass 2 macro-thematic pruning/assembly.

## Key CLI Flags & Functions
- `--enrich` (default `True`) / `--no-enrich` ([process_chunks_local.py:67](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py#L67-L70)): Runs Stage 2 Prep-First Enrichment before Pass 1 by default.
- `--post-reaction-verify` (default `False`) ([process_chunks_local.py:72](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py#L72-L74)): Opt-in post-Pass-1 reaction verification pass (disabled by default because webcam sheets are now fed directly into Pass 1).
- `_run_prep_stage(workspace, args)` & `_assert_prep_complete(workspace, chunk_files)` ([process_chunks_local.py:130](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py#L130-L157)): Resolves audio/video media, forwards `AUDIOCPP_URL` and `WHISPER_URL` to `SongScanConfig`, and calls `enrich_workspace_chunks()`.

## Modification & Bug-Fix History
- **`2026-11-21` (`0428ec2`)**: Switched `--enrich` to default `True` and re-ordered `_run_active_pipeline()` so `_run_prep_stage()` executes before `_load_or_detect_signals()` and Pass 1.
- **`2026-11-21` (`d3e997a`)**: Added `--post-reaction-verify` opt-in flag.
