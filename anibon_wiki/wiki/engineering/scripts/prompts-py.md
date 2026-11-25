---
title: "prompts.py (lib/process/prompts.py)"
category: "engineering-script"
updated: "2026-11-25"
script_path: "lib/process/prompts.py"
tags: ["python", "script", "prompts", "world-identity", "glossary", "guards"]
sources: ["[[code-change-prep-first-48k]]", "[[code-change-stage5-guards-fgo-np-2026-11-25]]"]
status: "active"
---

# `prompts.py`

- **Source File**: [lib/process/prompts.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py)
- **Unit Tests**: [tests/test_full_context_config.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_full_context_config.py), [tests/test_scrutinize_fixes.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_scrutinize_fixes.py#L34-L50), [tests/test_stage5_pipeline_guards.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_stage5_pipeline_guards.py)
- **Pipeline & DB**: [[prep-first-full-context-48k]], [[domain-db-and-fgo-py]]

## Purpose & Responsibility
Builds Pass 1 and Pass 2 prompts for `anibon-timestamper-local`, merging full-context chunk transcripts, recovered song speech (`enrichment/chunk_NN.json`), livechat reactions, multimodal activity sidecars, confidence-gated World Identity references, and JIT SQLite domain entities (`atlas_fgo.db`, `hoyowiki.db`, `prts_arknights.db`).

## Key Functions & Public Contracts
- `format_chunk_for_prompt(chunk, max_lines=MAX_TRANSCRIPT_LINES)` ([prompts.py:56](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L56-L78)): When `max_lines <= 0` (the default), skips `_coalesce_items()` and emits 100% of transcript lines plus recovered song speech.
- `load_world_identity_context(signals, refs_dir, max_chars=WI_SNIPPET_LIMIT)` ([prompts.py:118](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L118-L133)): Caps low-confidence (`0.0 < conf < 0.65`) reference files to `_LOW_CONF_WI_CAP = 4000` characters while allowing high-confidence (`>= 0.65`) reference files to load in full when `max_chars == 0`.
- `build_chunk_entity_context(chunk_text, glossary, allowed_sources=None)` ([prompts.py:136](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L136-L163)): Always runs `resolve_entities_for_chunk(chunk_text)` against local SQLite domain DBs regardless of `allowed_sources`, preventing wrong-game `signals.json` from blocking FGO/HSR/Arknights entity injection.
- `_extract_donor_mentions(transcript_block)` ([prompts.py:347](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L347)) & `_build_game_switch_hint(signal, current_topic, rolling_summary)` ([prompts.py:362](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L362)): Extracts viewer/donor handles (`ขอบคุณ / donate / ซุป ... คุณ <Name>`) and high-confidence (`>= 0.65`, non-`Knowledge`) game-switch hints into `build_recursive_prompt()` `## CONTEXT METRICS` ([prompts.py:513-520](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L513-L520)), paired with the updated `GROUNDING:` prompt rule ([prompts.py:558](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L558)) so donor handles are never misclassified as game factions.

## Modification & Bug-Fix History
- **`2026-11-21` (`3a5a039`)**: Enabled full-context (`0` = uncapped) defaults for transcript lines, livechat, World Identity, and entity glossary.
- **`2026-11-21` (`26c7466`)**: Added `_LOW_CONF_WI_CAP = 4000` for `conf < 0.65` and decoupled `resolve_entities_for_chunk()` from `allowed_sources` ([[post-mortem-scrutinize-cqll7dq35bw]]).
- **`2026-11-25` (uncommitted `dev`)**: Added Stage 5 donor mention guard (`_extract_donor_mentions`) and `conf >= 0.65` domain switch hints (`_build_game_switch_hint`), plus `MH`/ASR homophone grounding rules ([[code-change-stage5-guards-fgo-np-2026-11-25]]).
