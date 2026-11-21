---
title: "obs_layout.py (lib/video/obs_layout.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/video/obs_layout.py"
tags: ["python", "script", "obs", "webcam", "ffmpeg", "layout"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `obs_layout.py`

- **Source File**: [lib/video/obs_layout.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[webcam-storyboard-py]], [[audio-webcam-cues-py]]

## Purpose & Responsibility
Classifies OBS webcam placement (`top-right`, `mid-right`, `lower-right`, `mid-left`, `bottom-right`, `bottom-left`, `top-left`, `none`, or arbitrary PIP position via `track_webcam_any_position`) and isolates clean sub-windows across OBS scene cuts or mid-window Picture-in-Picture (PIP) webcam relocations.

## Key Functions & Public Contracts
- `resolve_webcam_and_face_boxes(layout: str) -> Tuple[Optional[FaceBox], Optional[FaceBox]]` ([obs_layout.py:19-23](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L19-L23)): Looks up a named preset in `WEBCAM_BOX_PRESETS` and derives the inner tight face crop via `w_box.derive_tight_face()`.
- `detect_layout_cuts(full_frames, fps=2.0, cut_mad_floor=0.22) -> List[int]` ([obs_layout.py:26-35](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L26-L35)): Flags frame indices where consecutive full-frame `compute_frame_delta()[0]` meets or exceeds `cut_mad_floor` (`0.22`).
- `split_around_cuts(total_frames, cut_indices, fps=2.0) -> Tuple[int, int]` ([obs_layout.py:51-65](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L51-L65)): Blocks `±1.5s` (`pad = max(1, int(round(1.5 * fps)))`) around every cut index and returns the `(lo, hi)` of the longest unblocked run via `_longest_clear_span()` ([obs_layout.py:38-48](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L38-L48)), falling back to `(0, total_frames)` if `< 2` frames remain.
- `classify_layout_from_frames(full_frames, sample_size=48, fps=1.0) -> LayoutSegment` ([obs_layout.py:125-137](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L125-L137)): Pure in-memory classifier over RGB24 buffers; detects cuts, isolates the largest clean span, checks `_match_fixed_corner()` ([obs_layout.py:98-105](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L98-L105)) using weighted corner + inner-face MAD (`0.35 * c_mad + 0.65 * i_mad` in `_corner_score`, [obs_layout.py:91-95](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L91-L95)), and falls back to `track_webcam_any_position()`.
- `detect_obs_layout(source, bounds: WindowBounds, preferred: str = "auto") -> LayoutSegment` ([obs_layout.py:172-190](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L172-L190)):
  1. Probes sparse `48x48` RGB24 frames at `1 fps` via `_probe_full_frames()` (`ffmpeg` with `timeout=45`, [obs_layout.py:140-153](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L140-L153)).
  2. Falls back to `preferred` (if in `WEBCAM_BOX_PRESETS`) or `"top-right"` when `< 2` frames are probed.
  3. Splits around scene cuts and calls `_split_pip_relocation()` ([obs_layout.py:156-169](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L156-L169)), which checks if first-half vs second-half webcam boxes have `box_iou(box_a, box_b) < 0.30` and isolates the post-switch half.
  4. Resolves the final `(layout, wb)` via `_resolve_from_clean()` ([obs_layout.py:108-122](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L108-L122)) and attaches narrowed `sub_span` timestamps whenever cuts or PIP switches occurred.

## Error Handling & Invariants
- **Trackable Face Threshold**: `_has_trackable_face()` ([obs_layout.py:83-88](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L83-L88)) probes `_CENTER_PROBE` (`FaceBox(0.28, 0.08, 0.44, 0.65, "center")`) for full-screen boxes (`box.w >= 0.99`) and requires consecutive region MAD `>= 0.010`.
- **Corner Dominance Gate**: `_match_fixed_corner()` requires the top corner's weighted score to meet `max(0.012, 1.45 * max(med_sc, 0.002))` before accepting a preset over arbitrary-position tracking.
- **Safe Source Check**: `_probe_full_frames()` skips `ffmpeg` execution and returns `[]` if `source` is neither an existing local file nor an `http(s)://` URL ([obs_layout.py:143-144](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/obs_layout.py#L143-L144)), or if `ffmpeg` returns a non-zero exit code.
