# Production Adaptive Multimodal Keyframe Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the adaptive visual scene-change and evaluation-batch keyframe selector from prototype to production default with 16×9 RGB thumbnail sidecar caching (eliminating repeated `ffmpeg` subprocess overhead), CLI parameter overrides, clean-slate `--no-resume` output purging, multi-timestamp resume restoration, per-chunk visual telemetry, and full `SKILL.md` documentation.

**Architecture:**
1. **16×9 RGB Thumbnail Sidecar & Memory Cache (`anibon/multimodal.py`)**: Cache the 432-byte downsampled RGB buffer in memory (`_THUMB_CACHE`) and on disk (`tile_XXXXXX.rgb` next to `tile_XXXXXX.jpg`) inside `_get_tile_downsampled_bytes()` so each tile is decoded at most once ever, cutting 88-chunk scan CPU overhead from ~4 minutes to milliseconds on repeat runs and cutting first-run `ffmpeg` calls by $>50\%$.
2. **Production Default & CLI Overrides (`anibon/multimodal.py`, `process_chunks_local.py`)**: Set `scene_dedup: bool = True` by default in `sample_chunk_keyframes()`, expose `--eval-batch-size`, `--max-chunk-frames`, `--scene-delta-threshold`, and `--no-scene-dedup` on the CLI, and record selected keyframe timestamps (`keyframe_timestamps`, `keyframe_count`) in `recursive_outputs/chunk_XX.json`.
3. **Clean-Slate `--no-resume` & Multi-Stamp Resume Integrity (`process_chunks_local.py`)**: Purge stale `recursive_outputs/chunk_*.json` (and `group_outputs/group_*_output.md`) when `--no-resume` is passed so partial test runs never contaminate subsequent resumed runs, and restore the full `timestamps` list (not just the first `timestamp`) when resuming across chunks.
4. **Documentation (`skills/anibon-timestamper-local/SKILL.md`)**: Update pipeline architecture and CLI reference to reflect the production adaptive scene-change keyframe selector.

**Tech Stack:** Python 3.9+, `unittest`, optional `Pillow (PIL)` with `ffmpeg` rawvideo fallback.

**Spec:** Derived from production benchmark findings on `youtube_O8D4bpcvA9s_workspace` (88 chunks, 6.5h livestream) and [`docs/superpowers/plans/2026-10-18-adaptive-scene-frame-selector.md`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/plans/2026-10-18-adaptive-scene-frame-selector.md).

## Global Constraints

- Zero mandatory third-party packages (`PIL` remains optional; `ffmpeg` fallback must remain 100% functional).
- Default `scene_dedup: bool = True` in `sample_chunk_keyframes()`, with `scene_dedup=False` preserved for legacy fixed 3–5 frame behavior (`--no-scene-dedup`).
- Thumbnail sidecar files (`.rgb`) must be exactly `432` bytes (`16 * 9 * 3`); corrupted or partial `.rgb` files must be ignored and regenerated.
- Passing `--no-resume` must unlink stale `chunk_*.json` files in `recursive_outputs/` before starting the loop.

## Review Focus

1. **Corrupted or truncated `.rgb` sidecar file**: If `tile_000010.rgb` exists on disk with size $\ne 432$ bytes, `_get_tile_downsampled_bytes()` must ignore it, re-extract from the `.jpg`, and overwrite the `.rgb` sidecar.
2. **Elimination of duplicate `ffmpeg`/PIL decodes**: Comparing `last_kept_tile` against 10 candidate tiles in a chunk must decode `last_kept_tile` only once (served from `_THUMB_CACHE` / `.rgb` sidecar on subsequent comparisons).
3. **`--no-resume` stale chunk purge**: Running `run_recursive_mode(..., no_resume=True, max_chunks=2)` on a workspace containing `chunk_00.json`..`chunk_05.json` must delete `chunk_02.json`..`chunk_05.json` so a subsequent resumed run does not skip them.
4. **Multi-timestamp resume restoration**: When `chunk_01.json` has `"timestamps": ["00:07:40 - [Talk] A", "00:08:52 - [News] B"]`, resuming must restore both timestamps into `all_timestamps`, not just the first one.
5. **CLI overrides plumbed to `sample_chunk_keyframes`**: Passing `--no-scene-dedup`, `--max-chunk-frames 8`, `--scene-delta-threshold 0.10`, or `--eval-batch-size 4096` must forward those exact parameters to `sample_chunk_keyframes()`.

---

### Task 1: 16×9 RGB Thumbnail Sidecar & Memory Cache + Default `scene_dedup=True`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/multimodal.py:135-190, 295-380`
- Test: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Consumes: `EVAL_BATCH_SIZE`, `TOKENS_PER_IMAGE`, `SCENE_DELTA_THRESHOLD`, `MAX_CHUNK_FRAMES` from `anibon.config`
- Produces:
  - `_THUMB_CACHE: dict[str, bytes]`
  - `_get_tile_downsampled_bytes(tile_path: Path) -> Optional[bytes]` (with `.rgb` 432-byte sidecar persistence and memory caching)
  - `sample_chunk_keyframes(..., scene_dedup: bool = True, delta_threshold: float = SCENE_DELTA_THRESHOLD, text_tokens: Optional[int] = None, eval_batch_size: int = EVAL_BATCH_SIZE) -> List[Tuple[str, Path, str]]`

- [ ] **Step 1: Write failing tests for `.rgb` sidecar caching, corrupted sidecar recovery, and `scene_dedup=True` default in `skills/anibon-timestamper-local/tests/test_multimodal.py`**

```python
    def test_get_tile_downsampled_bytes_writes_and_reuses_rgb_sidecar(self):
        import subprocess, tempfile
        from anibon.multimodal import _get_tile_downsampled_bytes, _THUMB_CACHE, Image
        with tempfile.TemporaryDirectory() as tmp:
            tile_path = Path(tmp) / "tile_000010.jpg"
            sidecar = Path(tmp) / "tile_000010.rgb"
            if Image is not None:
                Image.new("RGB", (320, 180), (30, 60, 90)).save(tile_path)
            else:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1e3c5a:s=320x180", "-frames:v", "1", str(tile_path)],
                    check=True,
                )

            # Write corrupted 10-byte sidecar first -> must be ignored and overwritten with 432 bytes
            sidecar.write_bytes(b"corrupted!")
            _THUMB_CACHE.clear()

            raw1 = _get_tile_downsampled_bytes(tile_path)
            self.assertIsNotNone(raw1)
            self.assertEqual(len(raw1), 432)
            self.assertTrue(sidecar.is_file())
            self.assertEqual(sidecar.stat().st_size, 432)

            # Remove source .jpg but clear memory cache -> should load directly from valid .rgb sidecar
            _THUMB_CACHE.clear()
            raw2 = _get_tile_downsampled_bytes(tile_path)
            self.assertEqual(raw1, raw2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py -v`
Expected: FAIL with `ImportError: cannot import name '_THUMB_CACHE'`

- [ ] **Step 3: Implement `_THUMB_CACHE`, `.rgb` sidecar persistence, `eval_batch_size` forwarding, and `scene_dedup: bool = True` default in `anibon/multimodal.py`**

1. Define `_THUMB_CACHE: dict[str, bytes] = {}` above `_get_tile_downsampled_bytes()`.
2. In `_get_tile_downsampled_bytes(tile_path: Path) -> Optional[bytes]`:
   - Check `key = str(p.resolve())` in `_THUMB_CACHE`.
   - Check `sidecar = p.with_suffix(".rgb")`: if `sidecar.is_file()` and `sidecar.stat().st_size == 432`, read `data = sidecar.read_bytes()`, store `_THUMB_CACHE[key] = data`, and return `data`.
   - If `not p.is_file()`, return `None`.
   - Decode `raw: Optional[bytes]` via `PIL` or `ffmpeg`. If `raw` and `len(raw) == 432`, write `sidecar.write_bytes(raw)` (inside `try/except OSError: pass`), store `_THUMB_CACHE[key] = raw`, and return `raw`.
3. In `sample_chunk_keyframes()`:
   - Change default `scene_dedup: bool = True` and add `eval_batch_size: int = EVAL_BATCH_SIZE`.
   - Pass `eval_batch_size=eval_batch_size` to `compute_frame_budget(text_tokens if text_tokens is not None else 3000, eval_batch_size=eval_batch_size, max_frames=effective_max)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/multimodal.py skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "perf(multimodal): add 16x9 RGB sidecar cache and default scene_dedup=True"
```

---

### Task 2: Clean-Slate `--no-resume`, Multi-Stamp Resume Restoration, CLI Overrides & Chunk Telemetry

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:370-465, 560-578, 635-655, 900-925`
- Create: `skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`

**Interfaces:**
- Consumes: `sample_chunk_keyframes`, `EVAL_BATCH_SIZE`, `MAX_CHUNK_FRAMES`, `SCENE_DELTA_THRESHOLD`
- Produces:
  - CLI flags on `process_chunks_local.py`: `--eval-batch-size`, `--max-chunk-frames`, `--scene-delta-threshold`, `--no-scene-dedup`
  - Clean-slate purge of `recursive_outputs/chunk_*.json` and `group_outputs/group_*_output.md` when `no_resume=True`
  - Multi-timestamp restoration from `saved_res.get("timestamps")` on resume
  - `keyframe_timestamps` and `keyframe_count` persisted in `recursive_outputs/chunk_XX.json`

- [ ] **Step 1: Write failing tests in `skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import process_chunks_local as pcl


class TestProcessChunksResumeAndCleanSlate(unittest.TestCase):
    def test_no_resume_purges_stale_recursive_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] สวัสดีครับ\n", encoding="utf-8")

            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()
            stale_file = out_dir / "chunk_05.json"
            stale_file.write_text('{"chunk": "chunk_05", "timestamps": ["00:25:00 - [Talk] Stale"]}', encoding="utf-8")

            with patch.object(pcl, "call_local", return_value='{"is_continuation": false, "timestamps": ["00:00:00 - [Talk] เริ่มสตรีม"], "chunk_summary": "เริ่ม", "updated_summary": "เริ่ม", "new_topic_title": "เริ่ม"}'), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", ["00:00:00 - [Talk] เริ่มสตรีม"])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertFalse(stale_file.exists(), "Stale chunk_05.json must be deleted when no_resume=True")
            self.assertTrue((out_dir / "chunk_00.json").exists())

    def test_resume_restores_multiple_timestamps_from_chunk_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] A\n", encoding="utf-8")

            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()
            (out_dir / "chunk_00.json").write_text(json.dumps({
                "chunk": "chunk_00",
                "timestamps": [
                    "00:01:00 - [Talk] ประเด็นแรก",
                    "00:03:00 - [News] ประเด็นสอง",
                ],
                "timestamp": "00:01:00 - [Talk] ประเด็นแรก",
                "current_topic_title": "ข่าว",
                "rolling_summary": "สรุป",
            }), encoding="utf-8")

            captured = {}
            def fake_finalize(workspace, all_timestamps, **kwargs):
                captured["stamps"] = list(all_timestamps)
                return workspace / "anibon_timestamps.md", list(all_timestamps)

            with patch.object(pcl, "finalize_and_assemble_timestamps", side_effect=fake_finalize):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=False,
                    max_chunks=None,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertEqual(
                captured.get("stamps"),
                ["00:01:00 - [Talk] ประเด็นแรก", "00:03:00 - [News] ประเด็นสอง"],
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_process_chunks_resume.py -v`
Expected: FAIL (`stale_file.exists()` is True, and only 1 timestamp restored instead of 2)

- [ ] **Step 3: Implement clean-slate `--no-resume`, multi-stamp resume, CLI flags, and chunk keyframe telemetry in `process_chunks_local.py`**

1. In `run_recursive_mode()`:
   - When `no_resume` is True, unlink all `output_dir.glob("chunk_*.json")`.
   - When resuming from `out_path.exists()`, read `saved_ts_list = saved_res.get("timestamps") or ([saved_res.get("timestamp")] if saved_res.get("timestamp") else [])` and append each non-duplicate stamp to `all_timestamps`.
   - Read CLI overrides from `args`:
     - `scene_dedup = not getattr(args, "no_scene_dedup", False)`
     - `delta_threshold = getattr(args, "scene_delta_threshold", SCENE_DELTA_THRESHOLD)`
     - `max_chunk_frames = getattr(args, "max_chunk_frames", None)`
     - `eval_batch_size = getattr(args, "eval_batch_size", EVAL_BATCH_SIZE)`
   - Pass `scene_dedup=scene_dedup`, `delta_threshold=delta_threshold`, `num_frames=max_chunk_frames`, `eval_batch_size=eval_batch_size`, `text_tokens=est_text_tokens` to `sample_chunk_keyframes()`.
   - Include `"keyframe_count": len(keyframes)` and `"keyframe_timestamps": [kf[0] for kf in keyframes]` in the JSON written to `out_path`.
2. In `run_group_mode()`:
   - When `no_resume` is True, unlink all `output_dir.glob("group_*_output.md")`.
3. In `main()` argument parser:
   - Add `--eval-batch-size` (`type=int, default=EVAL_BATCH_SIZE`)
   - Add `--max-chunk-frames` (`type=int, default=None`)
   - Add `--scene-delta-threshold` (`type=float, default=SCENE_DELTA_THRESHOLD`)
   - Add `--no-scene-dedup` (`action="store_true"`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest discover -s skills/anibon-timestamper-local/tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper-local/tests/test_process_chunks_resume.py
git commit -m "feat(timestamper-local): clean-slate no-resume, multi-stamp resume, and adaptive CLI flags"
```

---

### Task 3: Update `SKILL.md` Production Documentation

**Files:**
- Modify: `skills/anibon-timestamper-local/SKILL.md:35-46, 125-175`

**Interfaces:**
- Consumes: CLI flags and config keys from Tasks 1–2
- Produces: Updated `skills/anibon-timestamper-local/SKILL.md`

- [ ] **Step 1: Update `skills/anibon-timestamper-local/SKILL.md` with Adaptive Scene-Change & Evaluation-Batch Keyframe Selector documentation**

Update:
1. Line 38 (`anibon/multimodal.py` summary): replace `3-keyframe sampling per chunk bounds` with `Adaptive scene-change & evaluation-batch keyframe selector (1–16 frames per chunk, 16×9 RGB sidecar caching, Thai deictic cue pinning)`.
2. Section `2. Process Chunks`: document `--eval-batch-size` (`8192`), `--max-chunk-frames` (`16`), `--scene-delta-threshold` (`0.06`), and `--no-scene-dedup`.

- [ ] **Step 2: Run full test suite to verify nothing is broken**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest discover -s skills/anibon-timestamper-local/tests -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skills/anibon-timestamper-local/SKILL.md
git commit -m "docs(skill): document production adaptive scene-change keyframe selector"
```
