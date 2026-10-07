# Vision Verify Ambiguous Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `process_chunks_local.py` verifies vague timestamps against a video frame using the local vision model before Pass 2 runs, so names like "เซเวนกับไหมกีนิด" become "Seven / McGinnis" without manual steps.

**Architecture:** Pass 1 stays text-only. It is cheap, and most chunks are clear. A new post-pass module, `anibon/vision_verify.py`, does four things:
1. Flags ambiguous stamps with heuristics.
2. Grabs one frame per flagged stamp with `ffmpeg` from the local video file.
3. Asks the vision model, via the existing `call_vision`, for a corrected line in JSON.
4. Accepts the correction only if the timestamp and tag are unchanged and confidence is at least 0.6.

The pass is opt-in with `--vision-verify`. It runs at all three assembly sites, just before `run_local_summarizer_pass`.

**Tech Stack:** Python 3 stdlib, `ffmpeg` CLI, LM Studio OpenAI-compatible endpoint, `unittest`/pytest.

**Spec:** User request in this session: "นอกจากช่วงที่ติด [?] แล้ว ให้ใช้กับช่วงที่ Timestamp ไม่ชัดเจนด้วย … implement ให้สามารถทำภายใน process_chunks_local ได้เลย". Reference behaviour: the manual frame check done for `0gZBSZPmMIA`.

## Global Constraints

- No new pip dependencies. Use stdlib plus the `ffmpeg` binary that is already required.
- Vision is opt-in (`--vision-verify`). Default runs must behave exactly as they do today.
- Never change a stamp's `HH:MM:SS` or `[Tag]`. Only the description text may change.
- A vision failure (no video, `ffmpeg` error, HTTP error, bad JSON) must keep the original stamp. It must never drop a stamp or crash the run.
- Run with `python -X utf8`. Thai text is written as UTF-8.

## Review Focus

1. Model returns prose or a hallucinated roast instead of JSON. Keep the original stamp. Test: `test_parse_rejects_non_json`.
2. Model rewrites the timestamp or tag. Reject the correction. Test: `test_parse_rejects_changed_time_or_tag`.
3. Video file is missing. Skip the whole pass with one warning line. Test: `test_verify_skips_without_video`.
4. Webcam-only or static frame, so the model has low confidence. Keep the original. Test: `test_parse_rejects_low_confidence`.
5. A re-run must not call the model again for stamps already checked. Cache in `vision_verify_log.json`. Test: `test_verify_uses_cache`.

---

### Task 1: Ambiguity detector + response parser (pure functions)

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py`
- Test: `skills/anibon-timestamper-local/tests/test_vision_verify.py`

**Interfaces:**
- Produces:
  - `is_ambiguous(stamp: str) -> bool`
  - `stamp_seconds(stamp: str) -> int`
  - `build_verify_prompt(stamp: str, context: str) -> str`
  - `parse_verify_response(raw: str, original: str, min_conf: float = 0.6) -> str`. It returns the corrected stamp or `original`.

`is_ambiguous` returns True if any of these hold:
- The text contains `[?]`.
- The description after `] ` is under 20 characters.
- The description contains a deictic word from `DEICTIC = ("คุณนี้", "ตัวนี้", "อันนี้", "นี่น่ะ", "นี้น่ะ")`.
- The description contains a generic phrase from `GENERIC = ("สู้มอนสเตอร์", "ในเกม", "เล่นเกมจนจบ")` and has no Latin word of 4 or more letters.

- [ ] **Step 1: Write the failing tests**

```python
from anibon.vision_verify import is_ambiguous, stamp_seconds, parse_verify_response

def test_is_ambiguous_cases():
    assert is_ambiguous("03:51:33 - [Donation] ขอบคุณคุณนี้น่ะ")
    assert is_ambiguous("03:28:41 - [Talk] Zelda")
    assert is_ambiguous("04:00:04 - [Gameplay] ปู่บอทสู้มอนสเตอร์ในเกมแล้วไม่ไหวจนเกือบตาย")
    assert not is_ambiguous("02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ")

def test_stamp_seconds():
    assert stamp_seconds("01:02:03 - [Talk] x") == 3723

ORIG = "03:52:49 - [Gameplay] เซเวนกับไหมกีนิด"

def test_parse_accepts_valid():
    raw = '{"corrected": "03:52:49 - [Gameplay] วิเคราะห์ฮีโร่ Seven และ McGinnis ใน Deadlock", "confidence": 0.8}'
    assert parse_verify_response(raw, ORIG).endswith("McGinnis ใน Deadlock")

def test_parse_rejects_non_json():
    assert parse_verify_response("I think this is Deadlock", ORIG) == ORIG

def test_parse_rejects_changed_time_or_tag():
    assert parse_verify_response('{"corrected": "03:53:00 - [Gameplay] x y z", "confidence": 0.9}', ORIG) == ORIG
    assert parse_verify_response('{"corrected": "03:52:49 - [Talk] x y z", "confidence": 0.9}', ORIG) == ORIG

def test_parse_rejects_low_confidence():
    assert parse_verify_response('{"corrected": "03:52:49 - [Gameplay] Seven", "confidence": 0.3}', ORIG) == ORIG
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python -m pytest tests/test_vision_verify.py -v` from `skills/anibon-timestamper-local`. Expected: ImportError / FAIL.
- [ ] **Step 3: Implement the four functions.** Extract JSON with the same `re.search(r"\{.*\}", raw, re.DOTALL)` used in `process_chunks_local.py:212`. The prompt must ask for JSON `{"corrected": str, "confidence": float}` only. It must tell the model to name the game, hero, UI, or website literally visible on screen, keep the same `HH:MM:SS - [Tag]`, and never treat the streamer's hyperbole as image content (rule from `verifying-stream-ground-truth`).
- [ ] **Step 4: Run the tests again.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(timestamper): ambiguity detector and vision response parser"`

---

### Task 2: Frame extraction + verify orchestrator

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py`
- Test: `skills/anibon-timestamper-local/tests/test_vision_verify.py`

**Interfaces:**
- Consumes: Task 1 functions; `anibon.lmstudio.call_vision(endpoint, model, prompt, image_path, max_tokens=500, temperature=0.2, timeout=180) -> str`.
- Produces:
  - `extract_frame(video: Path, sec: int, out: Path) -> Optional[Path]`. It runs `ffmpeg -y -ss <sec> -i <video> -frames:v 1 -q:v 2 <out>` and returns `None` on failure or a missing output.
  - `verify_ambiguous_stamps(stamps: list[str], workspace: Path, video: Optional[Path], endpoint: str, model: str, context_fn: Callable[[int], str] = lambda s: "", call_fn=call_vision, frame_fn=extract_frame) -> list[str]`. It returns a list of the same length and order.

Behaviour:
- Frames go to `<workspace>/frames_verify/frame_HH-MM-SS.jpg`.
- Each decision is appended to `<workspace>/vision_verify_log.json` as `{stamp: {"result": str, "accepted": bool}}`.
- Stamps already in the log reuse `result` and make no model call.
- Each call is wrapped in try/except. On any exception, keep the original stamp.
- Print one line per stamp: `[vision] 03:52:49 ✓ corrected` / `✗ kept`.

- [ ] **Step 1: Write the failing tests** (use `tmp_path`, with fake `call_fn` / `frame_fn`)

```python
def test_verify_corrects_only_ambiguous(tmp_path):
    calls = []
    fake_call = lambda e, m, p, img, **k: (calls.append(img), '{"corrected": "03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock", "confidence": 0.9}')[1]
    fake_frame = lambda v, s, o: (o.write_bytes(b"x"), o)[1]
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    stamps = ["02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ", ORIG]
    out = verify_ambiguous_stamps(stamps, tmp_path, video, "e", "m", call_fn=fake_call, frame_fn=fake_frame)
    assert out[0] == stamps[0] and "McGinnis" in out[1] and len(calls) == 1

def test_verify_skips_without_video(tmp_path):
    assert verify_ambiguous_stamps([ORIG], tmp_path, tmp_path / "missing.mp4", "e", "m") == [ORIG]

def test_verify_keeps_original_on_exception(tmp_path):
    def boom(*a, **k): raise OSError("down")
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    fake_frame = lambda v, s, o: (o.write_bytes(b"x"), o)[1]
    assert verify_ambiguous_stamps([ORIG], tmp_path, video, "e", "m", call_fn=boom, frame_fn=fake_frame) == [ORIG]

def test_verify_uses_cache(tmp_path):
    # run test_verify_corrects_only_ambiguous's setup twice; second run: call_fn that raises -> still returns corrected value
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python -m pytest tests/test_vision_verify.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `extract_frame` and `verify_ambiguous_stamps`.**
- [ ] **Step 4: Run the tests again.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(timestamper): vision verify orchestrator with cache"`

---

### Task 3: Wire into `process_chunks_local.py` + CLI + docs

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`. Change CLI `:583-614` and the three assembly sites, each right before `run_local_summarizer_pass`, at `:341`, `:506`, and `:634`.
- Modify: `skills/anibon-timestamper-local/SKILL.md`. Add a Quick Commands entry and a pipeline-table row for "3.5 Vision Verify".
- Test: `skills/anibon-timestamper-local/tests/test_vision_verify.py`

**Interfaces:**
- Consumes: `verify_ambiguous_stamps` (Task 2).
- Produces: CLI flags.
  - `--vision-verify` (store_true).
  - `--video-file PATH`. Default: `<workspace>/video_360p.mp4`.
  - `--vision-model NAME`. Default: same as the resolved `--model`.

  Helper in `process_chunks_local.py`: `apply_vision_verify(stamps: list[str], workspace: Path, args, model: str) -> list[str]`. It returns `stamps` unchanged when `args.vision_verify` is False.

`context_fn` passed by the helper: it reads the matching `chunks/chunk_XX.txt` and returns the transcript lines within ±30 s of the stamp. Load the lines with `load_chunk_file` and filter by `start`.

- [ ] **Step 1: Write the failing test.** `test_apply_vision_verify_noop_when_disabled`: with `args.vision_verify=False`, it returns the same list object and calls nothing (patch `verify_ambiguous_stamps` and assert it was not called).
- [ ] **Step 2: Run the test and confirm it fails.** Expected: ImportError for `apply_vision_verify`.
- [ ] **Step 3: Implement the helper and the flags.** Replace `deduped` / `stamps` with `apply_vision_verify(...)` at the 3 sites. Rewrite `all_timestamps.txt` after verification so the corrections persist.
- [ ] **Step 4: Run the full suite.** Run `python -m pytest tests -v`. Expected: all PASS.
- [ ] **Step 5: Smoke-test on the real workspace.** Run `python -X utf8 scripts\process_chunks_local.py "$HOME\youtube_0gZBSZPmMIA_workspace" --endpoint http://127.0.0.1:1234/v1/chat/completions --summarize-only --vision-verify`. Expected: `[vision]` lines for 03:51:33, 03:52:49, 04:00:04, and 03:28:41, and `vision_verify_log.json` is created. This requires a vision-capable model with `mmproj` loaded. If the model answers "cannot see image", note it as an environment issue (SKILL.md Common Mistake #4), not a code bug.
- [ ] **Step 6: Commit.** `git commit -m "feat(timestamper): --vision-verify post-pass before summarizer"`
