---
title: "audio_webcam_cues.py (lib/video/audio_webcam_cues.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/video/audio_webcam_cues.py"
tags: ["python", "script", "audio", "webcam", "rms", "prep-first"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `audio_webcam_cues.py`

- **Source File**: [lib/video/audio_webcam_cues.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[webcam-storyboard-py]], [[obs-layout-py]]

## Purpose & Responsibility
Selects spaced candidate timestamps within a transcript chunk for webcam reaction inspection based on audio energy spikes (loud yells / laughter) and sudden or sustained silence drops. Used by [[chunk-enrichment-py]] during **Stage 2 Prep-First Enrichment** to anchor `webcam_sheets` before Pass 1 inference.

## Key Functions & Public Contracts
- `AudioWebcamCue` ([audio_webcam_cues.py:29-36](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L29-L36)): Frozen dataclass holding `sec: int`, `event_type: str`, `score: float`, and `note: str`.
- `raw_bins_to_z(raw_bins: List[Tuple[int, float]]) -> List[Tuple[int, float, float]]` ([audio_webcam_cues.py:15-26](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L15-L26)): Converts `(sec, rms)` bins into `(sec, z_score, onset_jump_z)` using robust median + MAD statistics (`sigma = max(1.4826 * mad, 0.005)`). Returns `[]` if fewer than 3 bins are supplied.
- `_pick_spaced_cues(events, max_cues) -> Tuple[AudioWebcamCue, ...]` ([audio_webcam_cues.py:39-51](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L39-L51)): Ranks candidate `(sec, kind, score)` tuples by descending score (breaking ties by earlier `sec`), keeps cues separated by at least `_MIN_CUE_GAP` (`15` seconds, [audio_webcam_cues.py:12](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L12)), caps at `max_cues`, and returns the selected `AudioWebcamCue` tuple sorted chronologically.
- `select_audio_webcam_cues(source, bounds: WindowBounds, max_cues: int = 4) -> Tuple[AudioWebcamCue, ...]` ([audio_webcam_cues.py:54-64](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L54-L64)): Extracts 1-second RMS bins via `extract_raw_rms_bins(source, bounds, bin_sec=1.0)`, detects events via `detect_audio_cue_events(raw_bins, bin_sec=1.0, z_thresh=2.5)`, and filters them with `_pick_spaced_cues()`.

## Error Handling & Invariants
- **Early Empty Guard**: Returns `()` immediately when `source` is falsy, `max_cues <= 0`, or `extract_raw_rms_bins()` produces no bins ([audio_webcam_cues.py:58-62](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L58-L62)).
- **Robust Scale Floor**: Clamps MAD-derived `sigma` to at least `0.005` ([audio_webcam_cues.py:22](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/video/audio_webcam_cues.py#L22)) to prevent division-by-zero on silent or near-constant audio windows.
- **Temporal Spacing**: `_MIN_CUE_GAP = 15` ensures adjacent webcam cues do not cluster on the same single yell before downstream `(0, -2, +2)` onset expansion in [[chunk-enrichment-py]].
