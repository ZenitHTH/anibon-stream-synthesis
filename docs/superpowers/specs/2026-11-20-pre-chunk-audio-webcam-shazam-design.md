# Pre-Chunk Audio, Webcam, and Shazam Enrichment Design

**Date:** 2026-11-20
**Status:** Approved for planning

## Intent and Why

Transcript-only chunking misses two frequent livestream moments in Anibon broadcasts:
1. **Non-verbal reactions:** Pu Boat yells very loud at a peak moment (`rms_z` spike) or goes completely silent in disbelief (`silence_drop` / sustained silence) while staring at the screen. Without visual webcam context, the timestamper has no text to anchor a stamp.
2. **Background music / songs drowning out speech:** When a commercial song or BGM plays while Pu Boat comments, YouTube auto-transcripts either transcribe song lyrics as if Pu Boat said them or drop his speech altogether.

Running a single pre-timestamp enrichment pass over each chunk's window resolves both problems **before** cloud (`anibon-timestamper`) or local (`anibon-timestamper-local`) inference begins.

## Goals, Non-Goals, and Anti-Goals

- **Goals:**
  - Detect **both** loud shout peaks and sudden/sustained silence drops per chunk from audio RMS envelopes, and capture cropped webcam frames around those timestamps before timestamping.
  - Detect suspected music windows per chunk, run Shazam (`shazamio`) to identify commercial tracks, and when a song is detected, split vocals/speaker via `audio.cpp` (`htdemucs`) and transcribe real speech via `whisper.cpp` (`whisper-cli`).
  - Persist per-chunk enrichment sidecars (`enrichment/chunk_NN.json`, `activity/activity_chunk_NN.txt`, `frames/webcam_chunk/wc_*.jpg`) and inject them into both local (`process_chunks_local.py`) and cloud (`build_subagent_prompts.py`) chunk prompts.
  - Support silent-window placeholder chunks in `prepare_video.py` when `--keep-silent-chunks` is enabled so 2.5-minute silent disbelief spans are not dropped.
- **Non-Goals:**
  - Replacing `whisper-corruption-recovery` (`fix_hallucinations.py`) for post-hoc tail loop repair.
  - Separating Pu Boat's voice from a background singer's vocal track when no studio reference exists (still mitigated by stripping instrumental stems via `audio.cpp` and tagging `[Detected Song: Title - Artist]` so the LLM distinguishes lyrics from Pu Boat's speech).
  - Running `shazamio` on every non-music talk chunk.
- **Anti-Goals:**
  - Mutating raw `chunks/chunk_NN.*` lines with non-transcript prose that breaks `detect_signals.py` TF-IDF, `clean_garbled_english.py`, or `_parse_chunk_items` in `lib/chunk/state.py`.
  - Blocking or hanging the pipeline when `shazamio`, `audio.cpp`, `whisper-cli`, or remote `yt-dlp` streams are unreachable (every external dependency must degrade gracefully).

## Constraints

- **Code quality (`Clean Code`):** Files `< 200` lines, functions `<= 20` lines, max `3` arguments per function (bundle via dataclasses), no boolean flag arguments on public library functions (split into named functions or config fields), guard clauses (`<= 2` indentation levels), isolated error-handling boundaries.
- **Parser invariant:** `lib/chunk/state.py:_parse_chunk_items` ignores lines not matching `(HH:MM:SS) ...`; `build_subagent_prompts.py` reads `<item>` tags plus sidecar files. All pre-chunk enrichments must travel through sidecars (`activity/activity_chunk_NN.txt`, `enrichment/chunk_NN.json`) and prompt injection, never raw unparsed text inside `chunks/`.
- **Timeouts & offline safety:** `shazamio` calls must use `asyncio.wait_for(..., timeout=15.0)` (per `media-verification.md`). `audio.cpp` (`DEFAULT_AUDIOCPP_URL`) and `whisper-cli` failures log warnings and fall back cleanly without aborting chunk prep.
- **Test runner:** `python3 -m unittest` (standard library `unittest`, `pytest` is not installed in the host environment).

## Approaches Considered

1. **Pre-pass sidecar enrichment (Chosen):** Run a single pre-timestamp pass (`scripts/enrich_chunks.py` + `lib/process/chunk_enrichment.py`) after `prepare_video.py` + livechat. Writes `enrichment/chunk_NN.json` and appends formatted cues to `activity/activity_chunk_NN.txt`, while caching cropped webcam frames in `frames/webcam_chunk/`. Both local (`prompts.py` + `dynamic_chunk.py`) and cloud (`build_subagent_prompts.py`) read these sidecars.
   - *Why chosen:* Leaves raw `chunks/chunk_NN.*` pure for TF-IDF and existing `.txt`/`.xml`/`.json` parsers, works across both cloud and local pipelines, and avoids per-chunk `ffmpeg` seeks during inference.
2. **Inline headers inside `chunks/chunk_NN.*`:** Rejected because `_parse_chunk_items` drops non-timestamp lines, `build_subagent_prompts.py` parses XML `<item>` nodes, and inline song/webcam notes pollute `detect_signals.py` TF-IDF scores.
3. **Local-only Pass 1 hooks:** Rejected because the cloud `anibon-timestamper` pipeline (`build_subagent_prompts.py`) would never see yell/silence webcam cues or Shazam+`whisper.cpp` recovered speech.

## Architecture & Data Flow

```
audio/video source + chunks/ + livechat/ + music_anchors.json
   │
   ▼
[1] Audio Envelope Scan (lib/video/audio_envelope.py + audio_webcam_cues.py)
    ├── shout spike (rms_z >= 2.5) ──────────────┐
    └── silence drop / sustained silence (>=6s) ─┼─► crop webcam frames -> frames/webcam_chunk/
                                                 │
[2] Music & Shazam Gate (lib/process/music/chunk_scanner.py)
    ├── trigger: music_anchors OR has_music_chat_surge OR is_music_spectral
    ├── slice 20s 44.1kHz stereo WAV -> shazamio (timeout 15s)
    └── if song detected:
          └── separate_via_audiocpp_api (audio.cpp htdemucs)
              -> resample vocals 16k mono
              -> timed whisper-cli (-oj) -> recovered speech items [(ts, text)]
   │
   ▼
[3] Persist Sidecars (lib/process/chunk_enrichment.py)
    ├── enrichment/chunk_NN.json  (cues, webcam_paths, song, recovered_items)
    └── activity/activity_chunk_NN.txt  (formatted [AUDIO_PEAK], [SILENCE_SHOCK], [SHAZAM_SONG], webcam frame note)
   │
   ▼
[4] Prompt & Runner Consumption
    ├── Local: prompts.py (injects recovered speech + song guard + activity) & dynamic_chunk.py (reuses cached webcam frames)
    └── Cloud: build_subagent_prompts.py (injects activity + enrichment recovered speech)
```

## Decisions Made

- **Silence thresholds:** Reuse `_find_silence_drop` (`pre_mean >= 0.025`, drop to `<= 0.25 * pre_mean` and `<= 0.012` for `>= 2s`) and add sustained dead-silence detection (`rms <= 0.012` for `>= 6s` continuous) in `lib/video/audio_envelope.py`.
- **Music trigger before Shazam:** Run `recognize_shazam_slice` only when a chunk has a `music_anchors.json` hit, `has_music_chat_surge`, or spectral flatness `is_music_spectral` (`flatness < 0.010`), avoiding unnecessary network calls on talk chunks.
- **Timed `whisper.cpp` output:** When `audio.cpp` returns `vocals.wav` after a Shazam match, transcribe via `whisper-cli -oj` and offset each segment by `chunk_start_sec` so recovered lines carry exact `(HH:MM:SS)` timestamps.
- **Idempotent caching:** `enrich_chunks.py` skips chunks that already have `enrichment/chunk_NN.json` unless `--force` is passed.
- **Silent placeholder chunks:** `scripts/prepare_video.py` gets `--keep-silent-chunks` (default off so existing behavior/tests stay unchanged) to emit empty-item chunks for quiet windows instead of dropping them, and `_compute_chunk_time_window` honors `chunk["start_sec"]`/`chunk["end_sec"]` when `items` is empty.

## Left to Builder

- Exact CLI wording and log formatting in `scripts/enrich_chunks.py`.
- Exact formatting of `[RECOVERED SPEECH]` blocks inside `build_recursive_prompt`, `build_group_prompt`, and `build_subagent_prompts.py`.
