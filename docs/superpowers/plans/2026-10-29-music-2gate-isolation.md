# 2-Gate Music Detection & Vocal Isolation Integration Plan for anibon-timestamper-local

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the 2-Gate Music Detection and DSP Vocal Isolation pipeline directly into `anibon-timestamper-local` so background music is proactively detected in Stage 0/1.5 (before Pass 1 LLM) and reactively caught in Stage 4 (Whisper Dispatcher).

**Architecture:** 
1. **Proactive Gate (Stage 0 & 1.5):** Stage 0 extracts `[เพลง]` / `♪` markers to `music_anchors.json`. Stage 1.5 scans LiveChat keyword density and Spectral Flatness. Flagged chunks are immediately isolated via Reference Phase Subtraction (or Demucs) and re-transcribed with Whisper, injecting the clean speech and `[Song Context Briefing]` into `chunks/chunk_XX.txt` before Stage 2 (Pass 1 Local LLM).
2. **Reactive Gate (Stage 4):** Post-pass `whisper_dispatcher.py` detects surviving Whisper repetition loops (`คุณคุณคุณ`, `เฮ้ย เฮ้ย`, `มมมม`), automatically triggers DSP Subtraction, and patches `anibon_timestamps.md`.

**Tech Stack:** Python 3.11+, `numpy`, `scipy`, `soundfile`, `shazamio`, `whisper-cli`, Clean Code architecture (<200 lines/file, <20 lines/function).

**Spec:** `/Users/zenithth/.gemini/antigravity/brain/27ac3a67-d0df-465d-b07d-358aab0907f5/stealth_music_detection_research.md` and [SKILL.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/SKILL.md)

## Global Constraints

- Files must stay under 200 lines; functions must stay under 20 lines (Robert C. Martin Clean Code standard).
- No boolean flag arguments; use distinct, descriptive functions instead.
- Use early returns and guard clauses (nesting $\le 2$ levels).
- Plugin codebase located at `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/`.
- All CLI utilities must support `-X utf8` and run cleanly on macOS (Apple Silicon MPS) and Linux/Windows.

## Review Focus

1. **Non-destructive Transcript Denoising:** Capturing `[เพลง]` in Stage 0 must not leave broken symbols in `chunks/*.txt` that would confuse the LLM prompt.
2. **Offline-safe Shazam Fallback:** In environments without internet, `shazamio` timeouts must gracefully degrade to local LiveChat keywords and `resources/song_lore.json`.
3. **Pre-Pass Chunk Replacement Boundary:** Replacing chunk text with isolated Boat dialogue in `chunks/chunk_XX.txt` must preserve the original chunk's time header (`[HH:MM:SS - HH:MM:SS]`).
4. **Negative Time Offset in Long Streams:** Streamers playing YouTube clips starting in the middle must compute valid slices without array out-of-bounds error.
5. **Whisper Dispatcher Loop Trigger:** ASR loop detection must recognize both single-token stutter (`คุณคุณคุณ...`) and multi-token phrase loops (`เกิดไปโร่ของเมืองไทย...`).

---

### Task 1: Package Music Pipeline into Plugin Library (`lib/process/music/`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/__init__.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/acoustic.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/sensor.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/subtractor.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/music/lore.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/resources/song_lore.json`
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_music_subsystem.py`

**Interfaces:**
- Produces: `AcousticFeatures`, `TrackMetadata`, `SongContextBrief`
- Functions: `analyze_acoustic_features`, `scan_chat_music_density`, `process_subtraction_files`, `fetch_song_lore_summary`

- [ ] **Step 1: Write failing test in `tests/test_music_subsystem.py`**

```python
# tests/test_music_subsystem.py
import unittest
import numpy as np
from process.music.acoustic import analyze_acoustic_features, is_music_spectral
from process.music.lore import fetch_song_lore_summary

class TestMusicSubsystem(unittest.TestCase):
    def test_spectral_flatness_pure_sine(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        feats = analyze_acoustic_features(tone, sr)
        self.assertTrue(is_music_spectral(feats.flatness))

    def test_lore_lookup_mairom(self):
        brief = fetch_song_lore_summary("พี่ไม่ได้ดักเจ้า")
        self.assertIn("ไม้ร่ม", brief.artist)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_music_subsystem.py`
Expected: FAIL (module not found)

- [ ] **Step 3: Port tested clean modules to `lib/process/music/` and add `resources/song_lore.json`**

Deploy `acoustic.py`, `sensor.py`, `subtractor.py`, `lore.py` into plugin lib keeping functions $< 20$ lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_music_subsystem.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/process/music/ resources/song_lore.json tests/test_music_subsystem.py
git commit -m "feat(music): package core music detection and subtraction into plugin lib"
```

---

### Task 2: Stage 0 Music Anchor Extractor (`lib/process/signals/detector.py`)

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/signals/detector.py:35-55`
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_music_anchors.py`

**Interfaces:**
- Consumes: Raw subtitle text or XML events with `[เพลง]` or `♪`
- Produces: `music_anchors.json` in workspace containing `[{"start_ms": int, "symbol": str}]`
- Function: `extract_and_clean_music_anchors(text: str, offset_ms: int = 0) -> tuple[str, list[dict]]`

- [ ] **Step 1: Write failing test in `tests/test_music_anchors.py`**

```python
# tests/test_music_anchors.py
import unittest
from process.signals.detector import extract_and_clean_music_anchors

class TestMusicAnchors(unittest.TestCase):
    def test_extract_music_brackets_preserves_anchor(self):
        raw = "สวัสดีครับ [เพลง] วันนี้มาเล่นเกม ♪ เพลงเพราะมาก"
        clean, anchors = extract_and_clean_music_anchors(raw, offset_ms=10000)
        self.assertNotIn("[เพลง]", clean)
        self.assertNotIn("♪", clean)
        self.assertEqual(len(anchors), 2)
        self.assertEqual(anchors[0]["symbol"], "[เพลง]")
        self.assertEqual(anchors[0]["offset_ms"], 10000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_music_anchors.py`
Expected: FAIL (`extract_and_clean_music_anchors` not defined)

- [ ] **Step 3: Implement `extract_and_clean_music_anchors` in `lib/process/signals/detector.py`**

Update `clean_transcript_noise()` to use `extract_and_clean_music_anchors()` and persist anchors when workspace path is provided.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_music_anchors.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/process/signals/detector.py tests/test_music_anchors.py
git commit -m "feat(signals): extract music anchors during Stage 0 noise cleaning"
```

---

### Task 3: Stage 1.5 Proactive Music Slicer & Chunk Patching (`scripts/patch_music_chunks.py`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/patch_music_chunks.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/align_live_chat.py` (add `--scan-music` flag)
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_patch_music_chunks.py`

**Interfaces:**
- Consumes: `<workspace>/chunks/`, `<workspace>/livechat/`, `<workspace>/music_anchors.json`, Stream video URL
- Produces: Patched `chunks/chunk_XX.txt` prepended with `[Song Context Briefing]` and isolated Boat speech
- Function: `patch_chunk_with_song_lore(chunk_path: Path, brief: SongContextBrief, clean_speech: str) -> None`

- [ ] **Step 1: Write failing test in `tests/test_patch_music_chunks.py`**

```python
# tests/test_patch_music_chunks.py
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from process.music.lore import SongContextBrief
from scripts.patch_music_chunks import patch_chunk_with_song_lore

class TestPatchMusicChunks(unittest.TestCase):
    def test_patch_chunk_replaces_speech_and_prepends_lore(self):
        with TemporaryDirectory() as tmpdir:
            chunk_file = Path(tmpdir) / "chunk_01.txt"
            chunk_file.write_text("[03:45:00 - 03:50:00]\nข้อความติดลูปคุณคุณคุณคุณ", encoding="utf-8")
            brief = SongContextBrief(
                title="แอ๊ดคาราบาว",
                artist="GUNNER",
                theme="แร็ปดราม่า",
                meme_lore="แซวยอดวิว",
                keywords=["เนเน่"]
            )
            patch_chunk_with_song_lore(chunk_file, brief, "อันนี้ 4 ล้านแล้วอ่ะ ไอ้เชี่ยเกิดไป")
            content = chunk_file.read_text(encoding="utf-8")
            self.assertIn("[Song Context Briefing]", content)
            self.assertIn("อันนี้ 4 ล้านแล้วอ่ะ", content)
            self.assertNotIn("คุณคุณคุณคุณ", content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_patch_music_chunks.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/patch_music_chunks.py` and hook into Stage 1.5**

Implement `patch_chunk_with_song_lore()`, time header preservation, and CLI entry point.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_patch_music_chunks.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/patch_music_chunks.py tests/test_patch_music_chunks.py
git commit -m "feat(stage1.5): implement proactive music chunk patching with song lore"
```

---

### Task 4: Stage 4 Reactive Safety Net in `whisper_dispatcher.py`

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/whisper_dispatcher.py`
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_whisper_repetition_watchdog.py`

**Interfaces:**
- Consumes: Whisper transcription output text
- Produces: Boolean `is_repetition_loop` and repetition ratio
- Function: `detect_repetition_anomaly(transcript_text: str, max_repeat_ratio: float = 0.20) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_whisper_repetition_watchdog.py`**

```python
# tests/test_whisper_repetition_watchdog.py
import unittest
from process.whisper_dispatcher import detect_repetition_anomaly

class TestWhisperRepetitionWatchdog(unittest.TestCase):
    def test_single_token_loop(self):
        text = "คุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณ"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_multi_token_loop(self):
        text = "เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_normal_speech(self):
        text = "วันนี้เรามาสร้างบ้านกลางลาวาในมายคราฟกันนะครับทุกคน"
        self.assertFalse(detect_repetition_anomaly(text))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_whisper_repetition_watchdog.py`
Expected: FAIL

- [ ] **Step 3: Implement `detect_repetition_anomaly` in `lib/process/whisper_dispatcher.py`**

Add n-gram repetition frequency counter and branch into `vocal_subtractor.py` when an anomaly is triggered.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest tests/test_whisper_repetition_watchdog.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/process/whisper_dispatcher.py tests/test_whisper_repetition_watchdog.py
git commit -m "feat(stage4): implement Whisper repetition watchdog in whisper_dispatcher"
```

---

### Task 5: End-to-End Verification on Livestream Workspace & Documentation

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/SKILL.md`
- Run verification script: `scripts/patch_music_chunks.py` on `youtube_l00khgGzmIg_workspace`

- [ ] **Step 1: Run end-to-end dry run on slice `03:47:45` (อ.ไม้ร่ม) in workspace**

Verify that `patch_music_chunks.py` successfully reads `l00khgGzmIg.live_chat.json`, flags chunk, subtracts reference, and writes lore brief into chunk text.

- [ ] **Step 2: Update `anibon-timestamper-local/SKILL.md`**

Update the Pipeline Architecture table to include:
- `Stage 0`: Music anchor extraction.
- `Stage 1.5`: Proactive music chunk patching (`patch_music_chunks.py`).
- `Stage 4`: Repetition loop watchdog in `whisper_dispatcher.py`.

- [ ] **Step 3: Run full plugin test suite**

Run: `PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib uv run python3 -m unittest discover /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests`
Expected: All tests PASS.

- [ ] **Step 4: Final Commit**

```bash
git add skills/anibon-timestamper-local/SKILL.md
git commit -m "docs(skill): update anibon-timestamper-local with 2-Gate Music Detection architecture"
```
