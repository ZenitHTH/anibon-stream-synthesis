---
title: "webcam_storyboard.py (lib/video/webcam_storyboard.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/video/webcam_storyboard.py"
tags: ["python", "script", "webcam", "ffmpeg", "storyboard"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `webcam_storyboard.py`

- **Source File**: [lib/video/webcam_storyboard.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/webcam_storyboard.py)
- **Unit Tests**: [tests/test_scrutinize_fixes.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_scrutinize_fixes.py#L52-L73)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[dynamic-chunk-py]]

## Purpose & Responsibility
Packs 2–9 sequential cropped webcam closeup JPEGs (`wc_NNNNNN.jpg`) into a single tiled grid JPEG (`wc_sheet_NN_0.jpg`, up to 3×3) with a left-to-right, top-to-bottom panel timestamp legend (`WEBCAM STORYBOARD (3x3 grid...; 9 panels: [1]=HH:MM:SS...)`).

## Key Functions & Public Contracts
- `assemble_webcam_storyboard(frames, out_path) -> Optional[Tuple[str, Path, str, str]]` ([webcam_storyboard.py:50](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/webcam_storyboard.py#L50-L65)): Validates up to 9 frame paths, chooses compact `(cols, rows)` via `grid_dims()`, renders the composite JPEG via `_render_grid_jpeg()`, and returns `(ts_span, out_path, b64, legend)`.
- `_render_grid_jpeg(paths, out_path, dims) -> bool` ([webcam_storyboard.py:26](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/webcam_storyboard.py#L26-L40)): Normalizes every input stream `[i:v]` with `scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}]` before `concat` and `tile`.

## Modification & Bug-Fix History
- **`2026-11-21` (`26c7466`)**: Added `scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black` to fix `ffmpeg` `concat` failure when `reprobe_switched_frames` mixed `320x320` and `320x220` crops within the same chunk.
- **`2026-11-21` (`2dce04d`)**: Added `,setsar=1` after `pad=320:320` to fix `ffmpeg` exit code `234` (`Input link in0:v0 parameters (size 320x320, SAR 1:1) do not match (320x320, SAR 539:540)`) when non-square `FaceBox` crops were pre-scaled to `320x320` ([[post-mortem-scrutinize-cqll7dq35bw]]).
