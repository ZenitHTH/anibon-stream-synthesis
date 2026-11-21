---
title: "Post-Mortem: Scrutinize Audit of Stream cQlL7DQ35bw & Prep-First Webcam Pipeline"
category: "post-mortem"
updated: "2026-11-21"
tags: ["post-mortem", "scrutinize", "bug-fix", "ffmpeg", "world-identity", "cqll7dq35bw"]
sources: ["[[code-change-prep-first-48k]]", "[[stream-cqll7dq35bw]]"]
status: "active"
---

# Post-Mortem: Scrutinize Audit of Stream `cQlL7DQ35bw` & Prep-First Webcam Pipeline

- **Commits**: `26c7466`, `2dce04d` ([[code-change-prep-first-48k]])
- **Regression Suite**: [tests/test_scrutinize_fixes.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_scrutinize_fixes.py)
- **Touched Scripts**: [[prompts-py]], [[chunk-enrichment-py]], [[dynamic-chunk-py]], [[webcam-storyboard-py]]

## 1. Low-Confidence World Identity Bleed & JIT DB Blocking (`26c7466`)
- **Symptom**: On multi-game livestream [[stream-cqll7dq35bw]], `signals.json` had low confidence (`0.40`) on `Zenless_Zone_Zero.md`. With `WI_SNIPPET_LIMIT = 0`, `load_world_identity_context()` dumped 35 KB of ZZZ lore into every chunk (including FGO and Limbus chunks) while `allowed_sources={"Zenless_Zone_Zero.md"}` blocked `resolve_entities_for_chunk()` from querying `atlas_fgo.db`. This caused the model to hallucinate `"MP5 ในเกม Zenless Zone Zero"` during Boat's NP5 [[sen-no-rikyu]] summon in [[fate-grand-order]].
- **Fix ([prompts.py:118-163](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py#L118-L163))**: Always execute `resolve_entities_for_chunk(chunk_text)` on every chunk regardless of `allowed_sources`, and cap low-confidence (`< 0.65`) WI reference files to `4,000` characters.

## 2. Stale Enrichment Cache & Single-Frame Pre-Chunk Webcam Cues (`26c7466`, `2dce04d`)
- **Symptom**: Pre-`26c7466` `enrichment/chunk_NN.json` caches only stored 1 webcam frame (`webcam_frames: [...]`) and had no `webcam_sheets` key. Re-running without `--force` returned the stale 1-frame cache and short-circuited `_balance_dynamic_chunk_frames()`.
- **Fix ([chunk_enrichment.py:98-176](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/chunk_enrichment.py#L98-L176))**:
  1. `_expand_cue_target_secs()` expands audio peak/silence cues with `(0, -2, +2)` onset/follow-through offsets plus deictic speech cues up to 9 frames.
  2. `_resolve_prep_webcam_box()` resolves the consensus OBS webcam box across the chunk's `storyboard_frames` before cropping.
  3. `_read_cached_enrichment()` returns `None` when `"storyboard_frames"` or `"webcam_sheets"` is missing, automatically upgrading stale caches.

## 3. `ffmpeg` `concat` Exit Code `234` on Mixed Aspect Ratios and SAR (`26c7466`, `2dce04d`)
- **Symptom**: When `reprobe_switched_frames` switched between square (`320x320`, `SAR 1:1`) and rectangular (`FaceBox` scaled to `320x320` with `SAR 539:540`) crops within the same chunk (e.g. `chunk_48`), `ffmpeg` `concat` failed with `Input link in0:v0 parameters (size 320x320, SAR 1:1) do not match (320x320, SAR 539:540)` (`returncode=234`), causing `assemble_webcam_storyboard()` to return `None` and fall back to 9 unpacked individual frames.
- **Fix ([webcam_storyboard.py:32-35](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/webcam_storyboard.py#L32-L35))**: Added per-input `scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}]` before `concat`.

## 4. Ground-Truth Transcript Hallucinations Fixed in `cQlL7DQ35bw`
- Corrected 9 timestamps in [anibon_timestamps.md](file:///Users/zenithth/youtube_cQlL7DQ35bw_workspace/anibon_timestamps.md) and [all_timestamps.txt](file:///Users/zenithth/youtube_cQlL7DQ35bw_workspace/all_timestamps.txt): Evelyn (`เอเวอลิน`) instead of Ellen Joe (`02:03:39`), [[chaotic-plartima]] Star Children PV (`03:26:22`), Utsumi Erice 4★ damage + 5★ Emiya discussion (`04:21:25`), Jack the Ripper ticket exchange (`04:26:53`), [[sunbringer]] 3-body swap (`01:56:25`), [[jing-yuan]] Elation R5 (`05:57:00`), HSR lack of friend borrowing in Apocalyptic Shadow (`06:31:00`), and skipping *Loop Hero* due to HSR burnout (`06:49:02`).
