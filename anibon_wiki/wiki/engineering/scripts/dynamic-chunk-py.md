---
title: "dynamic_chunk.py (lib/process/runners/dynamic_chunk.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/process/runners/dynamic_chunk.py"
tags: ["python", "script", "pass1", "multimodal", "webcam", "storyboard"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `dynamic_chunk.py`

- **Source File**: [lib/process/runners/dynamic_chunk.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/runners/dynamic_chunk.py)
- **Unit Tests**: [tests/test_pass1_full_frames.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_pass1_full_frames.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[webcam-storyboard-py]], [[process-chunks-local-py]]

## Purpose & Responsibility
Loads cached storyboard screen tiles and packed webcam sheets from `enrichment/chunk_NN.json` (or falls back to live motion/audio peak extraction) and feeds **both** untrimmed into Pass 1 VLM inference.

## Key Functions & Public Contracts
- `_load_cached_storyboard(workspace: Path, chunk: dict) -> list` ([dynamic_chunk.py:187](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/runners/dynamic_chunk.py#L187-L200)): Reads `storyboard_frames` from `enrichment/chunk_NN.json` and encodes them as base64 `"STORYBOARD SCREEN"` 4-tuples.
- `_load_cached_enrichment_webcam(workspace: Path, chunk: dict) -> list` ([dynamic_chunk.py:203](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/runners/dynamic_chunk.py#L203-L228)): Prioritizes `webcam_sheets` (`ts`, `path`, `label` with `[1]=HH:MM:SS...` panel legend) from `enrichment/chunk_NN.json`.
- `_balance_dynamic_chunk_frames(...) -> Tuple[list, list, str]` ([dynamic_chunk.py:231](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/runners/dynamic_chunk.py#L231-L254)): Returns all `sb_frames` alongside `wc_frames` without calling `trim_storyboard_frames`.

## Modification & Bug-Fix History
- **`2026-11-21` (`45e5930`)**: Added `_load_cached_storyboard()` and removed `trim_storyboard_frames()` from `_balance_dynamic_chunk_frames()` so Pass 1 receives all 10 screen tiles + webcam sheet simultaneously.
- **`2026-11-21` (`26c7466`)**: Updated `_load_cached_enrichment_webcam()` to load `webcam_sheets` metadata first, preserving multi-panel grid timestamp legends.
