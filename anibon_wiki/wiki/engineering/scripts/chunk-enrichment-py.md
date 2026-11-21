---
title: "chunk_enrichment.py (lib/process/chunk_enrichment.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/process/chunk_enrichment.py"
tags: ["python", "script", "enrichment", "prep-first", "webcam", "shazam"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `chunk_enrichment.py`

- **Source File**: [lib/process/chunk_enrichment.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_enrichment.py)
- **CLI Wrapper**: [scripts/enrich_chunks.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/enrich_chunks.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-storyboard-prep-py]], [[webcam-storyboard-py]], [[dynamic-chunk-py]], [[process-chunks-local-py]]

## Purpose & Responsibility
Executes **Stage 2 Prep-First Per-Chunk Enrichment** across all chunks in a workspace before Pass 1 LM Studio inference begins. Produces `enrichment/chunk_NN.json` and updates `activity/activity_chunk_NN.txt`.

## Key Functions & Public Contracts
- `enrich_workspace_chunks(cfg: ChunkEnrichConfig) -> int` ([chunk_enrichment.py:238](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_enrichment.py#L238-L253)): Auto-resolves `slides_dir` via `prepare_storyboard_slides(cfg.workspace)` if unset, logs `STAGE 2 :: PREP-FIRST ENRICHMENT`, and enriches every chunk with progress output.
- `enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict` ([chunk_enrichment.py:206](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_enrichment.py#L206-L226)):
  1. Checks `_read_cached_enrichment(cache_path)` — automatically invalidates stale caches missing `"storyboard_frames"` or `"webcam_sheets"`.
  2. Calls `prep_chunk_storyboard()` ([[chunk-storyboard-prep-py]]) to extract up to 10 screen tiles.
  3. Calls `select_audio_webcam_cues()` to locate loud RMS peaks and silence drops.
  4. Expands cues via `_expand_cue_target_secs()` (`(0, -2, +2)` offsets + deictic speech candidates from `collect_situational_candidates` up to `PASS1_WEBCAM_FRAMES = 9`).
  5. Resolves consensus webcam corner box via `_resolve_prep_webcam_box()` across the chunk's `sb_frames`, then crops and packs webcam sheets via `sample_chunk_webcam_frames()`.
  6. Runs `_maybe_recover_chunk_song()` (`Shazam` → `audio.cpp` → `whisper.cpp`) when BGM/music triggers match.

## Modification & Bug-Fix History
- **`2026-11-21` (`5fb37e3`)**: Added `slides_dir` to `ChunkEnrichConfig` and cached `payload["storyboard_frames"]` in `enrichment/chunk_NN.json`.
- **`2026-11-21` (`1d27486`)**: Added per-chunk `[i/N] chunk_NN | sb=... cues=... wc=...` progress logging in `enrich_workspace_chunks()`.
- **`2026-11-21` (`26c7466`)**: Added `_expand_cue_target_secs()` and saved `payload["webcam_sheets"]` (`ts`, `path`, `label`) so Pass 1 retains the full 9-panel grid legend.
- **`2026-11-21` (`2dce04d`)**: Added `_resolve_prep_webcam_box()` (consensus OBS corner detection across `sb_frames`) and schema validation in `_read_cached_enrichment()` so pre-`26c7466` cache files are automatically upgraded ([[post-mortem-scrutinize-cqll7dq35bw]]).
