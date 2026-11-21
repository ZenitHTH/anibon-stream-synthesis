---
title: "chunk_storyboard_prep.py (lib/process/chunk_storyboard_prep.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/process/chunk_storyboard_prep.py"
tags: ["python", "script", "storyboard", "prep-first"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `chunk_storyboard_prep.py`

- **Source File**: [lib/process/chunk_storyboard_prep.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_storyboard_prep.py)
- **Unit Tests**: [tests/test_chunk_storyboard_prep.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_chunk_storyboard_prep.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Caller**: [[chunk-enrichment-py]]

## Purpose & Responsibility
Extracts and caches up to `STORYBOARD_MAX_FRAMES` (`10`) full-screen storyboard JPEG tiles per chunk during Stage 2 Prep-First Enrichment, including silent/gameplay-only chunks that have zero transcript items.

## Key Functions & Public Contracts
- `prep_chunk_storyboard(chunk: dict, slides_dir: Optional[Path], workspace: Path, max_frames: int = STORYBOARD_MAX_FRAMES) -> List[Dict[str, str]]` ([chunk_storyboard_prep.py:21](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_storyboard_prep.py#L21-L43)):
  - Synthesizes evenly spaced probe items across `[start_sec, end_sec]` via `_synth_window_items()` when `chunk["items"]` is empty.
  - Crops individual tiles from `slides_clean` into `frames/storyboard_tiles/` via `sample_chunk_frames()` and returns `[{"ts": "HH:MM:SS", "path": "/abs/path/tile_NNNNNN.jpg"}, ...]`.

## Modification & Bug-Fix History
- **`2026-11-21` (`5fb37e3`)**: Created module to move storyboard tile extraction from Pass 1 into Stage 2 Prep-First Enrichment.
