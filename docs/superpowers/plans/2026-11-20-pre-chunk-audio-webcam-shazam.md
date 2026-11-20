# Pre-Chunk Audio, Webcam, and Shazam Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pre-enrich each livestream chunk before timestamping by detecting loud yells and silence shocks to extract webcam closeups, and running Shazam + `audio.cpp` + `whisper.cpp` on music-flagged chunks to recover Pu Boat's real spoken words.

**Architecture:** A pre-timestamp enrichment pass (`scripts/enrich_chunks.py` backed by `lib/process/chunk_enrichment.py`) scans chunk audio once for RMS shout spikes, sudden silence drops, and sustained dead silence, crops webcam frames for triggered moments, and runs `shazamio` -> `audio.cpp` (`htdemucs`) -> `whisper.cpp` on music-flagged chunks. Results are cached in `enrichment/chunk_NN.json` and `activity/activity_chunk_NN.txt` sidecars so both `anibon-timestamper-local` (`prompts.py`, `dynamic_chunk.py`) and cloud `anibon-timestamper` (`build_subagent_prompts.py`) consume them without mutating raw `chunks/chunk_NN.*`.

**Tech Stack:** Python 3, stdlib `unittest`, `ffmpeg`, `shazamio`, `audio.cpp` HTTP API (`htdemucs`), `whisper.cpp` (`whisper-cli -oj` / `WHISPER_ENDPOINT`).

**Spec:** `docs/superpowers/specs/2026-11-20-pre-chunk-audio-webcam-shazam-design.md`

## Global Constraints

- Files `< 200` lines; functions `<= 20` lines; max `3` arguments per function (bundle via dataclasses); no boolean flag arguments on library functions.
- Guard clauses first (`<= 2` indentation levels); isolate `subprocess`/`urllib`/`asyncio` error handling in boundary functions.
- Never write non-`(HH:MM:SS)` prose inside `chunks/chunk_NN.*` (`_parse_chunk_items` drops it and TF-IDF `detect_signals.py` degrades).
- `shazamio` calls must use `asyncio.wait_for(..., timeout=15.0)` and degrade gracefully on timeout or offline hosts.
- Test runner is `python3 -m unittest` (`pytest` is not installed).

## Review Focus

- `shazamio` hanging indefinitely on slow/blocked network -> Task 2 pins `asyncio.wait_for` timeout handling.
- `audio.cpp` server unreachable or `whisper-cli` absent on host -> Task 2 pins graceful fallback preserving `TrackMetadata` with empty `recovered_items`.
- Re-running enrichment over existing `activity/activity_chunk_NN.txt` storyboard output -> Task 3 pins idempotent marker replacement and cache skip.
- Empty-transcript silent chunk (`items == []`) with silence shock -> Task 4 pins `_compute_chunk_time_window` honoring `start_sec`/`end_sec` and prompt injection.
- Raw `chunks/chunk_NN.txt` untouched while both local (`build_recursive_prompt`) and cloud (`build_subagent_prompts.py`) receive cues -> Task 4 pins prompt injection parity.

---

### Task 1: Silence-Aware Audio Envelope & Webcam Cue Selector

**Files:**
- Modify: `lib/video/audio_envelope.py:96-125`
- Create: `lib/video/audio_webcam_cues.py`
- Modify: `lib/video/chunk_peak_select.py:68-118`
- Test: `skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py`

**Interfaces:**
- Consumes: `WindowBounds` from `video.motion_types`; `_decode_mono_pcm`, `_pcm_rms_bins`, `_find_silence_drop` from `video.audio_envelope`.
- Produces:
  - `extract_raw_rms_bins(source: Path | str, bounds: WindowBounds, bin_sec: float = 1.0) -> List[Tuple[int, float]]` in `lib/video/audio_envelope.py`
  - `detect_audio_cue_events(raw_bins: List[Tuple[int, float]], bin_sec: float = 1.0, z_thresh: float = 2.5) -> List[Tuple[int, str, float]]` in `lib/video/audio_envelope.py`
  - `AudioWebcamCue(sec: int, event_type: str, score: float, note: str)` and `select_audio_webcam_cues(source: Optional[Path | str], bounds: WindowBounds, max_cues: int = 4) -> Tuple[AudioWebcamCue, ...]` in `lib/video/audio_webcam_cues.py`

- [ ] **Step 1: Write the failing tests**

Create `skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_LIB = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from video.audio_envelope import detect_audio_cue_events
from video.audio_webcam_cues import select_audio_webcam_cues
from video.chunk_peak_select import PeakSearchInput, detect_chunk_reaction_peaks
from video.motion_types import WindowBounds


class TestAudioWebcamCues(unittest.TestCase):
    def test_detect_audio_cue_events_captures_loud_peak_silence_drop_and_sustained_silence(self) -> None:
        # 6s normal speech (0.08), sudden silence drop for 8s (0.002), then loud shout (0.45)
        raw_bins = (
            [(100 + i, 0.08) for i in range(6)]
            + [(106 + i, 0.002) for i in range(8)]
            + [(114, 0.45), (115, 0.08)]
        )
        events = detect_audio_cue_events(raw_bins, bin_sec=1.0, z_thresh=2.5)
        kinds = {kind for _, kind, _ in events}
        self.assertIn("loud_peak", kinds)
        self.assertIn("silence_drop", kinds)
        self.assertIn("sustained_silence", kinds)

    def test_select_audio_webcam_cues_spaces_results_by_15s(self) -> None:
        raw_bins = [(10, 0.45), (15, 0.42), (35, 0.002)] + [(36 + i, 0.002) for i in range(6)]
        with patch("video.audio_webcam_cues.extract_raw_rms_bins", return_value=raw_bins):
            cues = select_audio_webcam_cues(Path("dummy.m4a"), WindowBounds(0, 60), max_cues=4)
        secs = [c.sec for c in cues]
        self.assertIn(10, secs)
        self.assertNotIn(15, secs)
        self.assertTrue(any(c.event_type in ("silence_drop", "sustained_silence") for c in cues))

    def test_detect_chunk_reaction_peaks_promotes_on_silence_drop(self) -> None:
        items = [{"start": 100, "text": "hello"}, {"start": 130, "text": ""}]
        raw_bins = [(100 + i, 0.08) for i in range(5)] + [(105 + i, 0.002) for i in range(8)]
        with patch("video.chunk_peak_select.extract_raw_rms_bins", return_value=raw_bins):
            peaks, _, promote = detect_chunk_reaction_peaks(PeakSearchInput(Path("."), items, "audio.m4a"))
        self.assertTrue(promote)
        self.assertTrue(len(peaks) >= 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py -v`
Expected: FAIL with `ImportError` (`cannot import name 'detect_audio_cue_events'` / `No module named 'video.audio_webcam_cues'`).

- [ ] **Step 3: Implement `extract_raw_rms_bins`, `detect_audio_cue_events`, `audio_webcam_cues.py`, and silence promotion in `chunk_peak_select.py`**

1. In `lib/video/audio_envelope.py`: add `extract_raw_rms_bins(source, bounds, bin_sec=1.0)` (decodes via `_decode_mono_pcm` + `_pcm_rms_bins`) and `detect_audio_cue_events(raw_bins, bin_sec=1.0, z_thresh=2.5)` emitting `(abs_sec, "loud_peak", z)`, `(abs_sec, "silence_drop", 3.0)` via `_find_silence_drop`, and `(abs_sec, "sustained_silence", 2.5)` when consecutive bins stay `<= 0.012` for `>= 6.0` seconds. Keep functions `<= 20` lines.
2. In `lib/video/audio_webcam_cues.py`: define `AudioWebcamCue` dataclass and `select_audio_webcam_cues(source, bounds, max_cues=4)` sorting candidates by descending score and enforcing `abs(a - b) >= 15` spacing.
3. In `lib/video/chunk_peak_select.py`: update `_collect_audio_candidates` (or add silence branch in `detect_chunk_reaction_peaks`) to call `extract_raw_rms_bins` + `detect_audio_cue_events`, adding silence events into `cands` and setting `should_promote = True` whenever a `silence_drop` or `sustained_silence` event is present. Preserve existing `extract_chunk_rms_bins` mock compatibility in `test_live_corner_and_peaks.py` by falling back to `extract_chunk_rms_bins` if `extract_raw_rms_bins` returns empty or is patched in tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py skills/anibon-timestamper-local/tests/test_audio_envelope.py skills/anibon-timestamper-local/tests/test_live_corner_and_peaks.py -v`
Expected: PASS (all tests OK).

- [ ] **Step 5: Commit**

```bash
git add lib/video/audio_envelope.py lib/video/audio_webcam_cues.py lib/video/chunk_peak_select.py skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py
git commit -m "feat(video): add silence-drop and sustained-silence triggers for webcam cues"
```

---

### Task 2: Shazam + `audio.cpp` + `whisper.cpp` Chunk Song Scanner

**Files:**
- Create: `lib/process/music/chunk_scanner.py`
- Test: `tests/test_chunk_song_scanner.py`

**Interfaces:**
- Consumes: `has_music_chat_surge`, `recognize_shazam_slice`, `TrackMetadata` from `process.music.sensor`; `analyze_acoustic_features`, `is_music_spectral` from `process.music.acoustic`; `DEFAULT_AUDIOCPP_URL`, `separate_via_audiocpp_api`, `convert_audio_to_16k_mono` from `process.audio_separator_engine`; `find_whisper_cli`, `find_whisper_model`, `run_whisper_slice` from `process.whisper_dispatcher`; `fmt_ts` from `common.time`.
- Produces:
  - `SongScanConfig(audiocpp_url: str = DEFAULT_AUDIOCPP_URL, shazam_timeout_sec: float = 15.0, whisper_bin: Optional[str] = None, whisper_model: Optional[str] = None, shazam_slice_sec: int = 20)`
  - `SongTriggerInput(chunk: dict, chat_lines: Sequence[str] = (), anchors: Sequence[dict] = (), audio_source: Optional[Path | str] = None)`
  - `SongScanRequest(chunk: dict, audio_source: Path | str, work_dir: Path)`
  - `SongRecoveryResult(title: str, artist: str, recovered_items: Tuple[dict, ...], vocals_path: Optional[Path])`
  - `should_scan_chunk_for_song(inp: SongTriggerInput) -> bool`
  - `scan_and_recover_chunk_song(req: SongScanRequest, cfg: SongScanConfig) -> Optional[SongRecoveryResult]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunk_song_scanner.py`:

```python
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_LIB = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.music.chunk_scanner import (
    SongScanConfig,
    SongScanRequest,
    SongTriggerInput,
    scan_and_recover_chunk_song,
    should_scan_chunk_for_song,
)
from process.music.sensor import TrackMetadata


class TestChunkSongScanner(unittest.TestCase):
    def test_should_scan_triggers_on_anchor_or_chat_surge(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 450, "items": []}
        self.assertTrue(should_scan_chunk_for_song(SongTriggerInput(chunk, (), [{"offset_ms": 350000}])))
        self.assertFalse(should_scan_chunk_for_song(SongTriggerInput(chunk, ("สวัสดี", "เล่นเกมต่อ"), ())))

    def test_scan_runs_shazam_then_audiocpp_then_whisper_and_offsets_timestamps(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        segs = [{"offsets": {"from": 4500, "to": 7000}, "text": "อันนี้เพลงโปรดเลย"}]
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            vocals = work_dir / "vocals.wav"
            vocals.write_bytes(b"RIFF")
            req = SongScanRequest(chunk, Path("audio.m4a"), work_dir)
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Bury the Light", "Casey Edwards"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", return_value=(vocals, work_dir / "inst.wav")) as mock_sep, \
                 patch("process.music.chunk_scanner.convert_audio_to_16k_mono"), \
                 patch("process.music.chunk_scanner.find_whisper_cli", return_value="/usr/bin/whisper-cli"), \
                 patch("process.music.chunk_scanner.find_whisper_model", return_value="/models/ggml.bin"), \
                 patch("process.music.chunk_scanner.run_whisper_slice", return_value=("อันนี้เพลงโปรดเลย", segs)):
                res = scan_and_recover_chunk_song(req, SongScanConfig())
        self.assertIsNotNone(res)
        mock_sep.assert_called_once()
        self.assertEqual(res.title, "Bury the Light")
        self.assertEqual(res.recovered_items[0]["timestamp"], "00:05:04")
        self.assertEqual(res.recovered_items[0]["text"], "อันนี้เพลงโปรดเลย")

    def test_scan_returns_none_when_shazam_times_out(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        async def slow_shazam(_path: str):
            await asyncio.sleep(0.5)
            return TrackMetadata("Slow", "Artist")
        with tempfile.TemporaryDirectory() as tmp:
            req = SongScanRequest(chunk, Path("audio.m4a"), Path(tmp))
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=slow_shazam):
                res = scan_and_recover_chunk_song(req, SongScanConfig(shazam_timeout_sec=0.05))
        self.assertIsNone(res)

    def test_scan_degrades_gracefully_when_audiocpp_or_whisper_unavailable(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        with tempfile.TemporaryDirectory() as tmp:
            req = SongScanRequest(chunk, Path("audio.m4a"), Path(tmp))
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Ao no Sumika", "Tatsuya Kitani"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", side_effect=RuntimeError("connection refused")):
                res = scan_and_recover_chunk_song(req, SongScanConfig())
        self.assertIsNotNone(res)
        self.assertEqual(res.title, "Ao no Sumika")
        self.assertEqual(res.recovered_items, ())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_chunk_song_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.music.chunk_scanner'`.

- [ ] **Step 3: Implement `lib/process/music/chunk_scanner.py`**

Implement `SongScanConfig`, `SongRecoveryResult`, `should_scan_chunk_for_song`, `_run_shazam_with_timeout`, `_separate_and_transcribe_speech`, and `scan_and_recover_chunk_song`:
- `_slice_wav_range(source, start_sec, duration_sec, out_wav)`: slices 44.1kHz stereo PCM WAV via `ffmpeg`.
- `_run_shazam_with_timeout(slice_wav, timeout_sec)`: executes `asyncio.wait_for(recognize_shazam_slice(str(slice_wav)), timeout=timeout_sec)` inside `asyncio.run(...)` with isolated `try/except` returning `None` on timeout/error.
- `_transcribe_vocals_with_offsets(vocals_wav, work_dir, chunk_start_sec, cfg)`: resamples via `convert_audio_to_16k_mono`, checks `find_whisper_cli` / `find_whisper_model` (or `WHISPER_ENDPOINT`), calls `run_whisper_slice`, and maps each segment's `offsets.from` (ms) + `chunk_start_sec` to `{"start": abs_sec, "timestamp": fmt_ts(abs_sec), "text": text}`.
- Keep file `< 160` lines, every function `<= 20` lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_chunk_song_scanner.py -v`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add lib/process/music/chunk_scanner.py tests/test_chunk_song_scanner.py
git commit -m "feat(music): add pre-chunk Shazam + audio.cpp + whisper.cpp scanner"
```

---

### Task 3: Unified Pre-Chunk Enrichment Orchestrator & Silent Chunks

**Files:**
- Modify: `scripts/prepare_video.py:44-146`
- Create: `lib/process/chunk_enrichment.py`
- Create: `scripts/enrich_chunks.py`
- Test: `tests/test_chunk_enrichment.py`

**Interfaces:**
- Consumes: `select_audio_webcam_cues` (`video.audio_webcam_cues`), `ChunkWebcamRequest`, `sample_chunk_webcam_frames` (`video.chunk_webcam`), `SongScanConfig`, `SongScanRequest`, `SongTriggerInput`, `should_scan_chunk_for_song`, `scan_and_recover_chunk_song` (`process.music.chunk_scanner`), `resolve_reaction_audio_source`, `resolve_reaction_source` (`process.reaction_source`), `load_chunk_file`, `load_chunk_activity` (`chunk.state`).
- Produces:
  - `ChunkBuildOptions(block: int = 150, overlap: int = 15, fmt: str = "json")` and `chunk_transcript_with_silent_windows(workspace: Path, opts: ChunkBuildOptions) -> int` in `scripts/prepare_video.py`
  - `ChunkEnrichConfig(workspace: Path, audio_source: Optional[Path | str] = None, video_source: Optional[Path | str] = None, webcam_corner: str = WEBCAM_CORNER, song_cfg: SongScanConfig = SongScanConfig(), force: bool = False)`
  - `resolve_workspace_media(workspace: Path, args: Any = None) -> Tuple[Optional[Path | str], Optional[Path | str]]`
  - `enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict`
  - `enrich_workspace_chunks(cfg: ChunkEnrichConfig) -> int`
  - CLI `scripts/enrich_chunks.py` and `scripts/prepare_video.py --keep-silent-chunks`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunk_enrichment.py`:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import prepare_video
from process.chunk_enrichment import ChunkEnrichConfig, enrich_single_chunk, enrich_workspace_chunks
from process.music.chunk_scanner import SongRecoveryResult
from video.audio_webcam_cues import AudioWebcamCue


class TestChunkEnrichment(unittest.TestCase):
    def test_prepare_video_keep_silent_chunks_emits_empty_window(self) -> None:
        transcript = [
            {"start": 5.0, "duration": 2.0, "text": "เปิดไลฟ์"},
            {"start": 320.0, "duration": 2.0, "text": "กลับมาพูดต่อ"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with patch("prepare_video.load_transcript", return_value=transcript), \
                 patch("prepare_video.load_default_mappings", return_value=[]), \
                 patch("prepare_video.load_replacements", return_value=[]):
                n = prepare_video.chunk_transcript_with_silent_windows(
                    ws, prepare_video.ChunkBuildOptions(block=150, overlap=15, fmt="txt")
                )
            self.assertEqual(n, 3)
            self.assertTrue((ws / "chunks" / "chunk_01.txt").is_file())

    def test_enrich_single_chunk_writes_sidecars_and_preserves_existing_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "activity").mkdir()
            chunk_path = ws / "chunks" / "chunk_00.txt"
            chunk_path.write_text("CHUNK 00 | 00:00:00–00:02:30 | cutoff=00:02:15\n(00:00:10) เริ่ม", encoding="utf-8")
            (ws / "activity" / "activity_chunk_00.txt").write_text("- 00:00:00 - 00:02:30: Elden Ring [Gameplay]", encoding="utf-8")

            cues = (AudioWebcamCue(45, "silence_drop", 3.0, "silence_drop"),)
            wc_fake = [("00:00:45", ws / "frames" / "webcam_chunk" / "wc_000045.jpg", "b64", "WEBCAM CLOSEUP")]
            song = SongRecoveryResult("Idol", "YOASOBI", ({"start": 60.0, "timestamp": "00:01:00", "text": "พูดแทรก"},), None)
            cfg = ChunkEnrichConfig(workspace=ws, audio_source=Path("a.m4a"), video_source=Path("v.mp4"))

            with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=cues), \
                 patch("process.chunk_enrichment.sample_chunk_webcam_frames", return_value=wc_fake), \
                 patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=True), \
                 patch("process.chunk_enrichment.scan_and_recover_chunk_song", return_value=song):
                data = enrich_single_chunk(chunk_path, cfg)

            self.assertEqual(data["song"]["title"], "Idol")
            act_text = (ws / "activity" / "activity_chunk_00.txt").read_text(encoding="utf-8")
            self.assertIn("Elden Ring [Gameplay]", act_text)
            self.assertIn("[SILENCE_SHOCK] 00:00:45", act_text)
            self.assertIn("[SHAZAM_SONG] Idol - YOASOBI", act_text)
            self.assertTrue((ws / "enrichment" / "chunk_00.json").is_file())
            self.assertIn("(00:00:10) เริ่ม", chunk_path.read_text(encoding="utf-8"))
            self.assertNotIn("YOASOBI", chunk_path.read_text(encoding="utf-8"))

            # Idempotent re-run skips recomputation when cache exists
            with patch("process.chunk_enrichment.select_audio_webcam_cues", side_effect=AssertionError("should use cache")):
                count = enrich_workspace_chunks(cfg)
            self.assertEqual(count, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_chunk_enrichment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.chunk_enrichment'`.

- [ ] **Step 3: Implement `chunk_transcript_with_silent_windows`, `lib/process/chunk_enrichment.py`, and `scripts/enrich_chunks.py`**

1. In `scripts/prepare_video.py`: add `ChunkBuildOptions(block: int = 150, overlap: int = 15, fmt: str = "json")`, extract shared `_write_chunk_windows` helper, add `chunk_transcript_with_silent_windows(workspace, opts)` (no boolean flag args on public functions), and add `--keep-silent-chunks` CLI option.
2. In `lib/process/chunk_enrichment.py`:
   - `resolve_workspace_media(workspace, args=None)`: checks `audio.m4a`/`audio.opus`/`audio.wav` before `resolve_reaction_audio_source`; uses `resolve_reaction_source` for video.
   - `enrich_single_chunk(chunk_path, cfg)`: parses chunk via `load_chunk_file` (or XML fallback via `chunk_io`), checks `enrichment/{cid}.json` cache unless `cfg.force`, runs `select_audio_webcam_cues` + `sample_chunk_webcam_frames` when cues exist, runs `should_scan_chunk_for_song` + `scan_and_recover_chunk_song`, writes `enrichment/{cid}.json`, and merges into `activity/activity_{cid}.txt` using a `--- PRE-CHUNK AUDIO/SONG ---` marker so existing visual storyboard lines remain intact on re-runs.
   - `enrich_workspace_chunks(cfg)`: discovers `chunk_*` in `workspace/chunks/` and enriches all chunks.
3. In `scripts/enrich_chunks.py`: thin CLI parsing `workspace`, `--video-file`, `--video-url`, `--remote-snap`, `--webcam-corner`, `--audiocpp-url`, `--force`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_chunk_enrichment.py tests/test_prepare_video_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/prepare_video.py lib/process/chunk_enrichment.py scripts/enrich_chunks.py tests/test_chunk_enrichment.py
git commit -m "feat(enrich): add pre-chunk audio, webcam, and Shazam enrichment pass"
```

---

### Task 4: Local & Cloud Prompt/Runner Integration (Including Silent Chunks)

**Files:**
- Modify: `lib/chunk/state.py:71-100`
- Modify: `lib/process/runners/common.py:40-46`
- Modify: `lib/process/runners/dynamic_chunk.py:139-197`
- Modify: `lib/process/runners/recursive.py:183-206,467-484`
- Modify: `lib/process/prompts.py:390-462,531-600`
- Modify: `skills/anibon-timestamper/scripts/build_subagent_prompts.py:66-121`
- Test: `tests/test_chunk_enrichment_integration.py`

**Interfaces:**
- Consumes: `enrichment/chunk_NN.json` written by Task 3.
- Produces:
  - `load_chunk_enrichment(workspace: Path, chunk_idx: str) -> dict` in `lib/chunk/state.py`
  - `format_enrichment_context(enrichment: dict) -> str` in `lib/process/prompts.py`
  - Updated `_compute_chunk_time_window` honoring `chunk.get("start_sec")` / `chunk.get("end_sec")` when `items` is empty.
  - Updated `build_recursive_prompt(..., enrichment: Optional[dict] = None)` and `build_group_prompt(..., enrichment_loader=None)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunk_enrichment_integration.py`:

```python
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))
_CLOUD_SCRIPTS = str(_ROOT / "skills" / "anibon-timestamper" / "scripts")
if _CLOUD_SCRIPTS not in sys.path:
    sys.path.insert(0, _CLOUD_SCRIPTS)

import build_subagent_prompts
from chunk.state import load_chunk_enrichment
from process.prompts import build_group_prompt, build_recursive_prompt
from process.runners.common import _compute_chunk_time_window


class TestChunkEnrichmentIntegration(unittest.TestCase):
    def test_silent_chunk_time_window_uses_chunk_bounds(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 450, "items": []}
        self.assertEqual(_compute_chunk_time_window(chunk, 1), (300, 450))

    def test_recursive_and_group_prompts_inject_song_and_recovered_speech(self) -> None:
        enrichment = {
            "audio_cues": [{"sec": 310, "event_type": "silence_drop", "note": "silence_drop"}],
            "song": {"title": "Unravel", "artist": "TK"},
            "recovered_items": [{"start": 315.0, "timestamp": "00:05:15", "text": "อึ้งเลยฉากนี้"}],
        }
        chunk = {"_idx": 1, "start_sec": 300, "end_sec": 450, "items": []}
        rec = build_recursive_prompt(chunk, "Gaming", "summary", enrichment=enrichment)
        self.assertIn("Unravel - TK", rec)
        self.assertIn("(00:05:15) อึ้งเลยฉากนี้", rec)
        self.assertIn("silence_drop", rec)

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "enrichment").mkdir()
            (ws / "enrichment" / "chunk_01.json").write_text(json.dumps(enrichment, ensure_ascii=False), encoding="utf-8")
            grp = build_group_prompt(
                [chunk], 0, "", "th", {}, ws, enrichment_loader=load_chunk_enrichment
            )
            self.assertIn("Unravel - TK", grp)
            self.assertIn("(00:05:15) อึ้งเลยฉากนี้", grp)

    def test_cloud_build_subagent_prompts_injects_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "enrichment").mkdir()
            (ws / "signals.json").write_text(json.dumps({"chunks": {"chunk_00": {"primary_topic": "Music"}}}), encoding="utf-8")
            (ws / "chunks" / "chunk_00.xml").write_text('<chunk id="0" start_sec="0" end_sec="150"></chunk>', encoding="utf-8")
            (ws / "enrichment" / "chunk_00.json").write_text(
                json.dumps({"song": {"title": "Idol", "artist": "YOASOBI"}, "recovered_items": [{"timestamp": "00:00:30", "text": "เพลงดีมาก"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            build_subagent_prompts.build_prompts(str(ws))
            out = (ws / "prompts_by_chunk" / "chunk_00.txt").read_text(encoding="utf-8")
            self.assertIn("Idol - YOASOBI", out)
            self.assertIn("(00:00:30) เพลงดีมาก", out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_chunk_enrichment_integration.py -v`
Expected: FAIL (`ImportError: cannot import name 'load_chunk_enrichment'` / unexpected keyword `'enrichment'`).

- [ ] **Step 3: Implement prompt, runner, and cloud prompt injection updates**

1. `lib/chunk/state.py`: add `load_chunk_enrichment(workspace, chunk_idx) -> dict`.
2. `lib/process/runners/common.py`: in `_compute_chunk_time_window`, use `chunk.get("start_sec")` / `chunk.get("end_sec")` when `items` is empty and bounds exist.
3. `lib/process/runners/dynamic_chunk.py`: add cached webcam fallback loader checking `enrichment/{chunk_idx}.json` (`webcam_frames`) so cached yell/silence frames load directly without re-running `ffmpeg`.
4. `lib/process/prompts.py`: add `format_enrichment_context(enrichment)` formatting `DETECTED SONG`, `RECOVERED SPEAKER SPEECH (audio.cpp + whisper.cpp)`, and `AUDIO/SILENCE WEBCAM CUES`; wire optional `enrichment` into `build_recursive_prompt` and `enrichment_loader` into `build_group_prompt`.
5. `lib/process/runners/recursive.py` & `group.py`: pass `load_chunk_enrichment` to `build_recursive_prompt` and `build_group_prompt`.
6. `skills/anibon-timestamper/scripts/build_subagent_prompts.py`: read `enrichment/{cid}.json` if present and append `ENRICHMENT (SONG / RECOVERED SPEECH / AUDIO CUES)` to `prompts_by_chunk/{cid}.txt`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_chunk_enrichment_integration.py skills/anibon-timestamper-local/tests/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/chunk/state.py lib/process/runners/common.py lib/process/runners/dynamic_chunk.py lib/process/runners/recursive.py lib/process/runners/group.py lib/process/prompts.py skills/anibon-timestamper/scripts/build_subagent_prompts.py tests/test_chunk_enrichment_integration.py
git commit -m "feat(prompts): inject pre-chunk audio, webcam, and Shazam+whisper enrichment"
```

---

### Task 5: Public Exports, CLI `--enrich` Wiring, and Skill Docs

**Files:**
- Modify: `lib/interface.py:100-140,275-325`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:175-198,350-380`
- Modify: `skills/anibon-timestamper/SKILL.md:117-140`
- Modify: `skills/anibon-timestamper-local/SKILL.md` (document pre-pass `scripts/enrich_chunks.py` / `--enrich`)
- Test: `tests/test_enrich_chunks_cli.py`

**Interfaces:**
- Consumes: `ChunkEnrichConfig`, `enrich_workspace_chunks`, `resolve_workspace_media` (`process.chunk_enrichment`); `load_chunk_enrichment` (`chunk.state`).
- Produces: `enrich_workspace_chunks` and `load_chunk_enrichment` exported on `lib/interface.py`; `--enrich` CLI flag on `process_chunks_local.py`; `scripts/enrich_chunks.py --help` contract.

- [ ] **Step 1: Write the failing test**

Create `tests/test_enrich_chunks_cli.py`:

```python
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts"))

import interface
import process_chunks_local


class TestEnrichChunksCLI(unittest.TestCase):
    def test_interface_exports_enrichment_symbols(self) -> None:
        self.assertTrue(callable(interface.enrich_workspace_chunks))
        self.assertTrue(callable(interface.load_chunk_enrichment))

    def test_enrich_cli_help_and_local_runner_flag(self) -> None:
        res = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "enrich_chunks.py"), "--help"],
            capture_output=True, text=True, cwd=str(_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--audiocpp-url", res.stdout)
        ap = process_chunks_local.build_argument_parser()
        args = ap.parse_args(["/tmp/ws", "--enrich"])
        self.assertTrue(args.enrich)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_enrich_chunks_cli.py -v`
Expected: FAIL (`AttributeError: module 'interface' has no attribute 'enrich_workspace_chunks'`).

- [ ] **Step 3: Wire exports, `--enrich`, and skill docs**

1. Export `enrich_workspace_chunks` and `load_chunk_enrichment` in `lib/interface.py`.
2. Add `--enrich` to `build_argument_parser()` in `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, and run `enrich_workspace_chunks` before `_dispatch_pipeline_mode` when `--enrich` is passed.
3. Add Step 3.65 (`python3 scripts/enrich_chunks.py <workspace>`) in `skills/anibon-timestamper/SKILL.md` and document `--enrich` / `scripts/enrich_chunks.py` in `skills/anibon-timestamper-local/SKILL.md`.

- [ ] **Step 4: Run full relevant test suite to verify everything passes**

Run: `python3 -m unittest tests/test_enrich_chunks_cli.py tests/test_chunk_enrichment_integration.py tests/test_chunk_enrichment.py tests/test_chunk_song_scanner.py skills/anibon-timestamper-local/tests/test_audio_webcam_cues.py skills/anibon-timestamper-local/tests/test_audio_envelope.py tests/test_audio_separator_engine.py tests/test_prepare_video_cli.py -v`
Expected: PASS (all tests OK).

- [ ] **Step 5: Commit**

```bash
git add lib/interface.py skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper/SKILL.md skills/anibon-timestamper-local/SKILL.md tests/test_enrich_chunks_cli.py
git commit -m "feat: wire pre-chunk enrichment into local runner, exports, and skill docs"
```
