# Adaptive Scene-Change & Evaluation-Batch Frame Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid 3–5 frame sampler with an adaptive visual scene-change + transcript-cue frame selector that eliminates duplicate static frames and scales up to the LM Studio Evaluation Batch Size (`8,192` tokens).

**Architecture:**
1. Expose `eval_batch_size` (`8192`), `tokens_per_image` (`260`), `scene_delta_threshold` (`0.06`), and `max_chunk_frames` (`16`) in `config.json` and `anibon/config.py`.
2. Add `compute_frame_budget()` and `compute_tile_visual_delta()` in `anibon/multimodal.py` to measure 16×9 downsampled RGB normalized mean absolute difference (`0.0..1.0`) between consecutive `320x180` storyboard tiles.
3. Update `sample_chunk_keyframes()` and `process_chunks_local.py` so static screens send only `1–2` non-redundant frames, while dynamic gameplay/watch-party chunks send every distinct visual scene transition + strong deictic cue up to the `8,192` evaluation batch ceiling (`~12–16` frames).

**Tech Stack:** Python 3.10+, `PIL.Image` (with stdlib fallback), `unittest`.

**Spec:** Agreed design from 2026-10-18 brainstorming session (`Context Length = 262,144`, `Evaluation Batch Size = 8,192`, `Physical Batch Size = 1,120`).

## Global Constraints

- Zero mandatory external dependencies beyond existing environment (`Pillow` optional with deterministic fallback).
- Default `eval_batch_size = 8192`, `tokens_per_image = 260`, `scene_delta_threshold = 0.06`, `max_chunk_frames = 16`.
- Existing callers of `sample_chunk_keyframes(start_sec, end_sec, slides_dir, out_dir, ...)` without `text_tokens` or `scene_dedup` must remain backward-compatible.
- Remove noisy casual interjections (`"เนี่ย"`, `"โห"`, `"โอ้โห"`, `"เฮ้ย"`) from `STRONG_VISUAL_CUES` so pure monologue talk chunks do not falsely force redundant frames on static screens.

## Review Focus

- Identical consecutive tiles (0.0 visual delta) in a chunk with no strong visual cues must deduplicate down to 1 anchor frame when `scene_dedup=True`.
- Distinct visual tiles (delta >= `0.06`) across a chunk must all be kept up to the computed `eval_batch_size` frame budget (e.g. 8–16 frames, exceeding the old hardcoded 5-frame cap).
- Strong deictic cues (`"ดูอันนี้"`, `"ในจอ"`, `"[?]"`) must force-keep the tile at that timestamp even when its visual delta against the previous tile is below `scene_delta_threshold`.
- High `text_tokens` (e.g. `7500` tokens against `eval_batch_size = 8192`) must clamp the frame budget down to `max(min_frames, (8192 - 7500) // 260)` = `2` frames without crashing or returning negative numbers.
- Missing or corrupt tile files in `compute_tile_visual_delta` must safely return `1.0` (treat as distinct) rather than raising unhandled exceptions.

---

### Task 1: Add Evaluation Batch & Scene-Delta Config Parameters

**Files:**
- Modify: `skills/anibon-timestamper-local/config.json:30-36`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/config.py:200-255`
- Test: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Produces:
  - `EVAL_BATCH_SIZE: int = 8192`
  - `TOKENS_PER_IMAGE: int = 260`
  - `SCENE_DELTA_THRESHOLD: float = 0.06`
  - `MAX_CHUNK_FRAMES: int = 16`

- [ ] **Step 1: Write failing test in `skills/anibon-timestamper-local/tests/test_config.py`**

```python
    def test_multimodal_batch_and_scene_config_defaults(self):
        import anibon.config as cfg
        cfg.load_config(override=True)
        self.assertEqual(cfg.EVAL_BATCH_SIZE, 8192)
        self.assertEqual(cfg.TOKENS_PER_IMAGE, 260)
        self.assertAlmostEqual(cfg.SCENE_DELTA_THRESHOLD, 0.06)
        self.assertEqual(cfg.MAX_CHUNK_FRAMES, 16)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py -v`
Expected: FAIL with `AttributeError: module 'anibon.config' has no attribute 'EVAL_BATCH_SIZE'`

- [ ] **Step 3: Add config keys to `config.json` and `anibon/config.py`**

In `skills/anibon-timestamper-local/config.json`, add:
- `"eval_batch_size": 8192`
- `"tokens_per_image": 260`
- `"scene_delta_threshold": 0.06`
- `"max_chunk_frames": 16`

In `skills/anibon-timestamper-local/scripts/anibon/config.py`, declare module-level constants `EVAL_BATCH_SIZE`, `TOKENS_PER_IMAGE`, `SCENE_DELTA_THRESHOLD`, `MAX_CHUNK_FRAMES` and bind them inside `reload_config()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/config.json skills/anibon-timestamper-local/scripts/anibon/config.py skills/anibon-timestamper-local/tests/test_config.py
git commit -m "feat(config): add eval_batch_size, tokens_per_image, and scene_delta_threshold"
```

---

### Task 2: Implement `compute_frame_budget()` and `compute_tile_visual_delta()`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/multimodal.py:125-235`
- Test: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Consumes: `EVAL_BATCH_SIZE`, `TOKENS_PER_IMAGE`, `SCENE_DELTA_THRESHOLD`, `MAX_CHUNK_FRAMES` from `anibon.config`
- Produces:
  - `compute_frame_budget(text_tokens: int, eval_batch_size: int = EVAL_BATCH_SIZE, tokens_per_image: int = TOKENS_PER_IMAGE, min_frames: int = 1, max_frames: int = MAX_CHUNK_FRAMES) -> int`
  - `compute_tile_visual_delta(tile_a: Path, tile_b: Path) -> float`

- [ ] **Step 1: Write failing tests in `skills/anibon-timestamper-local/tests/test_multimodal.py`**

```python
    def test_compute_frame_budget_scales_with_eval_batch(self):
        from anibon.multimodal import compute_frame_budget
        # 2500 text tokens in 8192 batch -> (8192 - 2500) // 260 = 21 -> capped at max_frames=16
        self.assertEqual(compute_frame_budget(2500, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 16)
        # 7500 text tokens in 8192 batch -> (8192 - 7500) // 260 = 2
        self.assertEqual(compute_frame_budget(7500, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 2)
        # Overflowing text tokens -> clamps to min_frames=1
        self.assertEqual(compute_frame_budget(9000, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 1)

    def test_compute_tile_visual_delta_identical_vs_distinct(self):
        import tempfile
        from PIL import Image
        from anibon.multimodal import compute_tile_visual_delta
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "black.jpg"
            p2 = Path(tmp) / "black_copy.jpg"
            p3 = Path(tmp) / "white.jpg"
            Image.new("RGB", (320, 180), (10, 10, 10)).save(p1)
            Image.new("RGB", (320, 180), (10, 10, 10)).save(p2)
            Image.new("RGB", (320, 180), (240, 240, 240)).save(p3)

            self.assertLess(compute_tile_visual_delta(p1, p2), 0.01)
            self.assertGreater(compute_tile_visual_delta(p1, p3), 0.80)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_frame_budget'`

- [ ] **Step 3: Implement `compute_frame_budget` and `compute_tile_visual_delta` in `anibon/multimodal.py`**

1. `compute_frame_budget(text_tokens, eval_batch_size=EVAL_BATCH_SIZE, tokens_per_image=TOKENS_PER_IMAGE, min_frames=1, max_frames=MAX_CHUNK_FRAMES) -> int`:
   - `avail = max(0, eval_batch_size - max(0, text_tokens))`
   - `fit = avail // max(1, tokens_per_image)`
   - `return max(min_frames, min(max_frames, fit))`
2. `compute_tile_visual_delta(tile_a: Path, tile_b: Path) -> float`:
   - Downsample both images to `16x9` RGB via `Image.open(p).convert("RGB").resize((16, 9))` and compute `sum(abs(c1 - c2)) / (16 * 9 * 3 * 255.0)`.
   - On missing `PIL` or exception, fallback to comparing raw file byte histograms or return `1.0` if file is unreadable.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/multimodal.py skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "feat(multimodal): add compute_frame_budget and compute_tile_visual_delta"
```

---

### Task 3: Upgrade `sample_chunk_keyframes()` & `run_recursive_mode()` to Adaptive Scene-Change Selection

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/multimodal.py:130-310`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:433-460`
- Test: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Consumes: `compute_frame_budget`, `compute_tile_visual_delta`, `SCENE_DELTA_THRESHOLD`
- Produces:
  - Updated `sample_chunk_keyframes(..., scene_dedup: bool = False, delta_threshold: float = SCENE_DELTA_THRESHOLD, text_tokens: Optional[int] = None) -> List[Tuple[str, Path, str]]`

- [ ] **Step 1: Write failing tests for scene-change deduplication and cue pinning in `tests/test_multimodal.py`**

```python
    def test_sample_chunk_keyframes_scene_dedup_drops_static_and_keeps_changes(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            slides_dir = Path(tmp) / "slides"
            out_dir = Path(tmp) / "tiles"
            slides_dir.mkdir()
            # Create slide_0001.jpg (960x540 = 3x3 grid of 320x180 tiles)
            # Tiles 0..5 are identical dark gray; Tile 6 (row 2, col 0 -> ~60s) is bright red
            slide = Image.new("RGB", (960, 540), (20, 20, 20))
            red_tile = Image.new("RGB", (320, 180), (240, 20, 20))
            slide.paste(red_tile, (0, 360))  # row 2, col 0 -> tile_idx 6 (~60s)
            slide.save(slides_dir / "slide_0001.jpg")

            # Static chunk (0..50s, all dark gray tiles) -> only 1 frame kept
            res_static = sample_chunk_keyframes(
                0, 50, slides_dir, out_dir, scene_dedup=True, delta_threshold=0.06, text_tokens=3000
            )
            self.assertEqual(len(res_static), 1)

            # Chunk spanning 0..80s (includes red tile at ~60s) -> keeps anchor + red scene change
            res_change = sample_chunk_keyframes(
                0, 80, slides_dir, out_dir, scene_dedup=True, delta_threshold=0.06, text_tokens=3000
            )
            self.assertGreaterEqual(len(res_change), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py -v`
Expected: FAIL (`TypeError: sample_chunk_keyframes() got an unexpected keyword argument 'scene_dedup'`)

- [ ] **Step 3: Implement adaptive scene-change scanning in `sample_chunk_keyframes()` and wire into `process_chunks_local.py`**

1. In `anibon/multimodal.py`:
   - Define `STRONG_VISUAL_CUES = ("ดูอันนี้", "ดูนี่", "เนี่ยดูดิ", "เปิดดู", "ในจอ", "ตรงนี้", "จุดนี้", "นี่ไง", "ดูคลิป", "ตัวละครนี้", "สกินนี้", "การ์ดนี้", "เกมนี้", "หน้านี้", "รูปนี้", "คลิปนี้", "ภาพนี้", "[?]")` (excluding generic filler like `"เนี่ย"`, `"โห"`).
   - When `scene_dedup=True`:
     - Compute `budget = compute_frame_budget(text_tokens or 3000, max_frames=max_frames)` (defaulting `max_frames` to `MAX_CHUNK_FRAMES` when `scene_dedup=True`).
     - Build candidate grid every `int(round(sec_per_tile))` (~10s) from `start_sec` to `end_sec`, plus any timestamp in `items` matching `STRONG_VISUAL_CUES` (pinned set).
     - Crop each candidate tile on demand; keep the first tile as anchor, always keep pinned cue timestamps (spaced $\ge 15\text{s}$), and keep any grid tile whose `compute_tile_visual_delta(last_kept_tile, candidate_tile) >= delta_threshold`.
     - If candidate count exceeds `budget`, prioritize pinned cues + highest visual delta transitions, then sort chronologically.
2. In `process_chunks_local.py` (`run_recursive_mode`, lines 433–455):
   - Estimate base text tokens from `rolling_summary` + `chunk` text (`est_text_tokens = (len(rolling_summary) + len(chunk.get("text", ""))) // 4 + 800`).
   - Call `sample_chunk_keyframes(int(st_sec), int(en_sec), slides_dir, tiles_dir, items=items, scene_dedup=True, text_tokens=est_text_tokens)`.

- [ ] **Step 4: Run full test suite to verify all tests pass**

Run: `PYTHONPATH="skills/anibon-timestamper-local/scripts:lib" python3 -m unittest discover -s skills/anibon-timestamper-local/tests -v`
Expected: PASS (all existing + new unit tests green)

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/multimodal.py skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "feat(multimodal): adaptive scene-change and eval-batch keyframe selection"
```
