---
title: "chunk_scanner.py (lib/process/music/chunk_scanner.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "lib/process/music/chunk_scanner.py"
tags: ["python", "script", "music", "shazam", "audiocpp", "whisper", "prep-first"]
sources: ["[[code-change-prep-first-48k]]"]
status: "active"
---

# `chunk_scanner.py`

- **Source File**: [lib/process/music/chunk_scanner.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[process-chunks-local-py]]

## Purpose & Responsibility
Implements pre-chunk music and vocal-drowned dialogue recovery during **Stage 2 Prep-First Enrichment**. Determines whether a chunk contains BGM/music (via transcript anchors, livechat surge, or spectral flatness), identifies the track with `shazamio`, separates vocals from accompaniment via the `audio.cpp` HTTP API, and transcribes masked speaker dialogue via `whisper.cpp`.

## Key Functions & Public Contracts
- **Configuration & Data Contracts** ([chunk_scanner.py:22-60](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L22-L60)):
  - `SongScanConfig`: `audiocpp_url` (default `DEFAULT_AUDIOCPP_URL`), `shazam_timeout_sec=15.0`, `whisper_bin`, `whisper_model`, `shazam_slice_sec=20`.
  - `SongTriggerInput`: `chunk`, `chat_lines`, `anchors`, `audio_source`.
  - `SongScanRequest`: `chunk`, `audio_source`, `work_dir`.
  - `SongRecoveryResult`: `title`, `artist`, `recovered_items: Tuple[dict, ...]`, `vocals_path`.
- `should_scan_chunk_for_song(inp: SongTriggerInput) -> bool` ([chunk_scanner.py:104-111](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L104-L111)): Evaluates three triggers in order:
  1. `_anchor_overlaps(anchors, start_sec, end_sec)` ([chunk_scanner.py:76-82](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L76-L82)): Checks if any `music_anchors.json` timestamp falls in `[start_sec, end_sec)`.
  2. `has_music_chat_surge(inp.chat_lines)`: Detects music-related viewer chat surges.
  3. `_probe_spectral_music(audio_source, start_sec, end_sec)` ([chunk_scanner.py:85-101](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L85-L101)): Extracts a 5-second 16kHz mono `s16le` slice around the chunk midpoint via `ffmpeg` (`timeout=20`) and checks `is_music_spectral(analyze_acoustic_features(samples, 16000).flatness)`.
- `scan_and_recover_chunk_song(req: SongScanRequest, cfg: SongScanConfig) -> Optional[SongRecoveryResult]` ([chunk_scanner.py:173-193](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L173-L193)):
  1. Slices a `shazam_slice_sec` (`20s`) 44.1kHz stereo WAV (`shazam_probe.wav`) via `_slice_wav_range()` ([chunk_scanner.py:114-125](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L114-L125)) and runs `_run_shazam_with_timeout()` ([chunk_scanner.py:128-135](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L128-L135)). Returns `None` if no track matches.
  2. Slices the full chunk mix (`chunk_mix.wav`) and separates stems via `separate_via_audiocpp_api(..., server_url=cfg.audiocpp_url)`.
  3. Calls `_transcribe_vocals(vocals_wav, req, cfg)` ([chunk_scanner.py:153-170](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L153-L170)) to resample vocals to 16kHz mono (`convert_audio_to_16k_mono`), transcribe with `run_whisper_slice()`, and offset segments to absolute stream timestamps via `_segments_to_items()` ([chunk_scanner.py:138-150](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L138-L150)).

## Error Handling & Invariants
- **Graceful Degradation**: If Shazam succeeds (`track` found) but full-chunk slicing fails, `separate_via_audiocpp_api()` raises, or Whisper is unavailable (`not os.environ.get("WHISPER_ENDPOINT") and not (w_bin and w_mod)`), `scan_and_recover_chunk_song()` logs a warning and still returns `SongRecoveryResult(track.title, track.artist, (), ...)` so Pass 1 retains the identified song metadata.
- **Bounded Subprocesses & Async Calls**: `shazamio` is bounded by `asyncio.wait_for(..., timeout=cfg.shazam_timeout_sec)`, spectral `ffmpeg` probes use `timeout=20`, and WAV slicing uses `timeout=45`.
- **Empty-Chunk Bound Fallback**: `_chunk_bounds()` ([chunk_scanner.py:62-73](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/chunk_scanner.py#L62-L73)) derives bounds from `start_sec`/`end_sec`, falling back to item timestamps or `[s, s + 150]` when empty.
