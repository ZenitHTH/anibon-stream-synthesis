---
title: "Code Change: Prep-First & Full-Context 48K Pipeline Overhaul (3a5a039..2dce04d)"
category: "source"
updated: "2026-11-21"
commits: "3a5a039..2dce04d"
tags: ["engineering", "prep-first", "full-context", "lm-studio", "python", "commits"]
sources: []
status: "active"
---

# Code Change: Prep-First & Full-Context 48K Pipeline Overhaul (`3a5a039..2dce04d`)

- **Git Range**: `3a5a039~1..2dce04d` (pushed to `origin/dev` and merged fast-forward into `origin/main`)
- **Implementation Plan**: [2026-11-21-prep-first-full-context.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/plans/2026-11-21-prep-first-full-context.md)
- **Raw Snapshot**: [code-change-prep-first-48k.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/raw/code-changes/code-change-prep-first-48k.md)
- **Architecture Synthesis**: [[prep-first-full-context-48k]]
- **Post-Mortem & Scrutinize Audit**: [[post-mortem-scrutinize-cqll7dq35bw]]

## Commit Ledger (9 Commits)

1. **`3a5a039` — `feat(local): full-context defaults for transcript, livechat, WI, entities`**
   - Removed artificial prompt truncation in [config.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/common/config.py) and [prompts.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py) (`MAX_TRANSCRIPT_LINES=0`, `LIVECHAT_MAX_LINES=0`, `WI_SNIPPET_LIMIT=0`, `ENTITY_CONTEXT_CAP=0`).
   - Updated [[process-chunks-local-py]] and [[prompts-py]].
2. **`5fb37e3` — `feat(enrich): cache storyboard screen tiles in pre-chunk enrichment`**
   - Created [[chunk-storyboard-prep-py]] (`prep_chunk_storyboard`) and wired [[chunk-enrichment-py]] to cache 10 screen tiles per chunk into `enrichment/chunk_NN.json`.
3. **`0428ec2` — `feat(local): run enrichment prep before Pass 1 by default`**
   - Enabled `--enrich` by default (`True`, `--no-enrich` to disable) in [[process-chunks-local-py]] so `_run_prep_stage` executes before signals detection and Pass 1 inference.
4. **`45e5930` — `feat(pass1): send all cached storyboard + webcam frames untrimmed`**
   - Updated [[dynamic-chunk-py]] (`_load_cached_storyboard`, `_balance_dynamic_chunk_frames`) to stop calling `trim_storyboard_frames` when webcam sheets exist.
5. **`d3e997a` — `refactor: reaction verify opt-in post-pass; doc prep-first order`**
   - Made post-Pass-1 reaction verify opt-in via `--post-reaction-verify` in [assembly.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/assembly.py#L43).
6. **`1d27486` — `feat(enrich): log per-chunk prep progress and default audio.cpp/whisper endpoints in launcher`**
   - Added `[i/N] chunk_NN | sb=... cues=... wc=...` logging in [[chunk-enrichment-py]] and default `AUDIOCPP_URL` / `WHISPER_URL` in [launch_local.sh](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/launch_local.sh).
7. **`bfcc1b3` — `config(local): enforce 2x context headroom (49152) in config and skill docs`**
   - Doubled LM Studio `context_length` from `24576` to **`49152` (48K)** (`parallel: 1`) across [config.json](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/config.json) and [config.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/common/config.py#L22).
8. **`26c7466` — `fix(local): prevent low-conf WI bleed, expand prep webcam cues, and normalize grid aspect ratios`**
   - Capped low-confidence (`< 0.65`) World Identity snippets to `4,000` chars while keeping JIT DB entity lookup (`resolve_entities_for_chunk`) active on every chunk in [[prompts-py]].
   - Expanded webcam cues with `(0, -2, +2)` offsets and deictic speech candidates in [[chunk-enrichment-py]].
   - Added `320x320` aspect-ratio normalization in [[webcam-storyboard-py]].
9. **`2dce04d` — `fix(enrich): auto-upgrade stale webcam caches, resolve consensus corner, and normalize SAR`**
   - Auto-invalidated pre-`26c7466` enrichment JSON caches lacking `webcam_sheets` or `storyboard_frames` in [[chunk-enrichment-py]].
   - Added `_resolve_prep_webcam_box()` using multi-tile `pick_consensus_corner` in [[chunk-enrichment-py]].
   - Added `,setsar=1` to `_render_grid_jpeg()` in [[webcam-storyboard-py]] to prevent `ffmpeg` `concat` exit code `234` (`SAR 1:1` vs `SAR 539:540`).
