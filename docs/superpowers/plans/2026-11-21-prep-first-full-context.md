# Prep-First, Full-Context Local Timestamper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `anibon-timestamper-local` finish all evidence prep (storyboard screen tiles, webcam crops at audio peaks/silence, song detection) before Pass 1. Then send that evidence to the local LM in full, with no trimming done to save context.

**Architecture:** `enrich_chunks` becomes the single prep stage. It writes `enrichment/chunk_NN.json` with storyboard tile paths, webcam crop paths, audio cues and song data. `process_chunks_local.py` runs enrichment by default before Pass 1 and gates on it. Pass 1 reads the cache and sends all frames and all lines untrimmed. The Pass 2 webcam reaction verify becomes opt-in.

**Tech Stack:** Python 3 stdlib, pytest, ffmpeg, existing `lib/` packages (`process`, `video`, `chunk`, `common`).

**Spec:** User request (2026-11-21) plus the approved proposal in this conversation: prep-first ordering, full context, and "RAM is plentiful, do not limit LM context".

## Global Constraints

- Work on branch `dev`. The repo is currently on `main`. Run `git checkout -b dev` (or `git checkout dev`) before Task 1. Never push to `main`.
- Clean Code: functions ≤ 20 lines, files ≤ 200 lines, ≤ 3 args (bundle into dataclasses).
- Run all commands from the plugin root `anibon-stream-synthesis`, with `python3 -X utf8`.
- Never kill the worker PID. Pause and resume semantics stay unchanged.
- Existing enrichment cache keys (`audio_cues`, `webcam_frames`, `song`, `recovered_items`) stay as they are. New keys are additive only.

## Review Focus

1. A chunk with an empty transcript (silent window) still gets storyboard tiles and enrichment. Test lives in Task 2.
2. No video or audio source: prep must warn and Pass 1 must still run text-only, not crash. Test lives in Task 3.
3. A stale enrichment cache without `storyboard_frames` (an old workspace) must fall back to live sampling. Test lives in Task 4.
4. Resume after pause must not re-run enrichment for chunks that are already cached. Covered by the existing cache check plus the Task 3 test.
5. `compact_chunk_max_lines = 0` must keep every transcript line with its own timestamp. Test lives in Task 1.

---

### Task 1: Full-context config (no transcript coalescing, full livechat, larger WI/entity limits)

**Files:**
- Modify: `skills/anibon-timestamper-local/config.json`
- Modify: `lib/common/config.py:174-305` (add `LIVECHAT_MAX_LINES`, `WI_SNIPPET_LIMIT`; reload them)
- Modify: `lib/process/prompts.py:28` (`_WI_SNIPPET_LIMIT` → `config.WI_SNIPPET_LIMIT`), `:209` (cap of 15 entities → `ENTITY_MAX_COUNT`), `:353-365` (`coalesce_chunk_items`)
- Modify: `lib/chunk/state.py:42` (`load_chunk_livechat` default `max_lines`)
- Test: `tests/test_full_context_config.py`

**Interfaces:**
- Produces: `common.config.LIVECHAT_MAX_LINES: int` (0 = unlimited), `WI_SNIPPET_LIMIT: int` (0 = unlimited), `ENTITY_MAX_COUNT: int` (0 = unlimited). `coalesce_chunk_items(items, max_lines)` returns one line per item when `max_lines <= 0`.

New config values: `"compact_chunk_max_lines": 0`, `"livechat_max_lines": 0`, `"wi_snippet_limit": 0`, `"entity_context_max_tokens": 2000`, `"entity_max_count": 60`, `"max_chunk_frames": 24`, `"pass1_webcam_frames": 9`, `"eval_batch_size": 32768`.

- [ ] **Step 1: Write failing tests**

```python
def test_coalesce_keeps_every_line_when_unlimited():
    items = [{"timestamp": f"00:00:{i:02d}", "text": f"t{i}"} for i in range(100)]
    assert len(coalesce_chunk_items(items, max_lines=0)) == 100

def test_livechat_unlimited(tmp_path):
    (tmp_path / "livechat").mkdir()
    (tmp_path / "livechat" / "livechat_chunk_00.txt").write_text("\n".join(f"m{i}" for i in range(50)), encoding="utf-8")
    assert len(load_chunk_livechat(tmp_path, "chunk_00", max_lines=0).splitlines()) == 50

def test_wi_snippet_unlimited(tmp_path, monkeypatch):
    # reference file of 5000 chars must not be truncated when WI_SNIPPET_LIMIT == 0
    ...
    assert "(truncated)" not in out
```

- [ ] **Step 2: Run** `pytest tests/test_full_context_config.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `max_lines <= 0` means return all lines. Read limits from `common.config` at call time, not at import time.
- [ ] **Step 4: Run** the new tests plus `pytest tests -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(local): full-context defaults for transcript, livechat, WI, entities`

---

### Task 2: Prep stage caches storyboard screen tiles per chunk

**Files:**
- Create: `lib/process/chunk_storyboard_prep.py` (≤ 80 lines)
- Modify: `lib/process/chunk_enrichment.py:164-189` (call prep; add payload key)
- Test: `tests/test_chunk_storyboard_prep.py`

**Interfaces:**
- Consumes: `process.multimodal.prepare_storyboard_slides(workspace, video_url) -> Optional[Path]` and `sample_chunk_keyframes(...)`.
- Produces: `prep_chunk_storyboard(chunk: dict, slides_dir: Optional[Path], workspace: Path) -> List[dict]`. Each dict looks like `{"ts": "HH:MM:SS", "path": str}`. Tiles go in `frames/chunk_tiles/`. Uses `scene_dedup=True` and `num_frames=MAX_CHUNK_FRAMES`. Takes the window from chunk `start_sec`/`end_sec`, so it still works when `items` is empty.
- `ChunkEnrichConfig` gains `slides_dir: Optional[Path] = None`. `enrich_workspace_chunks` resolves it once via `prepare_storyboard_slides`.
- The enrichment payload gains `"storyboard_frames": List[dict]`.

- [ ] **Step 1: Failing tests**

```python
def test_prep_storyboard_returns_tiles_for_silent_chunk(tmp_path, fake_slides):
    chunk = {"_idx": 3, "start_sec": 450, "end_sec": 600, "items": []}
    out = prep_chunk_storyboard(chunk, fake_slides, tmp_path)
    assert out and all(Path(f["path"]).is_file() for f in out)

def test_enrich_payload_has_storyboard_frames(tmp_path, fake_slides, monkeypatch):
    payload = enrich_single_chunk(chunk_path, ChunkEnrichConfig(workspace=tmp_path, video_source=..., slides_dir=fake_slides))
    assert "storyboard_frames" in payload
```

(`fake_slides`: write 3 grey 960×540 `slide_000N.jpg` with PIL.)

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Do not return the base64 here. Pass 1 loads the bytes later.
- [ ] **Step 4: Run** `pytest tests/test_chunk_storyboard_prep.py tests/test_chunk_enrichment.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(enrich): cache storyboard screen tiles in pre-chunk enrichment`

---

### Task 3: Prep-first ordering and gate in `process_chunks_local.py`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:198,393-412,426-445`
- Modify: `skills/anibon-timestamper-local/scripts/launch_local.sh:65-68` (pass `--video-file "$WORKSPACE/video_360p.mp4"` when that file exists)
- Test: `tests/test_prep_first_order.py`

**Interfaces:**
- Replace `--enrich` (default False) with `--no-enrich` (default False). Enrichment runs by default.
- `_run_pre_enrichment_if_requested` is renamed `_run_prep_stage(workspace, args) -> None`. It is called **before** `_prepare_transcript_mappings` / signals / glossary inside `_run_active_pipeline`. It also passes `audiocpp_url` from the `AUDIOCPP_URL` env var into `SongScanConfig`.
- Add `_assert_prep_complete(workspace, chunk_files) -> None`. It logs a warning listing chunk ids that are missing `enrichment/<id>.json`. It never exits, so text-only runs still work when there is no media.

- [ ] **Step 1: Failing tests**

```python
def test_prep_runs_before_pass1(monkeypatch, tmp_ws):
    calls = []
    monkeypatch.setattr(pcl, "_run_prep_stage", lambda *a: calls.append("prep"))
    monkeypatch.setattr(pcl, "run_recursive_mode", lambda **k: calls.append("pass1"))
    ...run main with argv [ws]...
    assert calls == ["prep", "pass1"]

def test_no_enrich_skips_prep(...):
    assert "prep" not in calls

def test_no_media_warns_not_crash(tmp_ws, caplog):
    pcl._run_prep_stage(tmp_ws, args_without_video)  # must not raise
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/test_prep_first_order.py tests/test_enrich_chunks_cli.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(local): run enrichment prep before Pass 1 by default`

---

### Task 4: Pass 1 consumes the full cache with no frame trimming

**Files:**
- Modify: `lib/process/runners/dynamic_chunk.py:187-229`
- Modify: `lib/process/runners/recursive.py:474-479`
- Test: `tests/test_pass1_full_frames.py`

**Interfaces:**
- Consumes: the Task 2 payload key `storyboard_frames`.
- Produces: `_load_cached_storyboard(workspace, chunk) -> list` of 4-tuples `(ts, Path, b64, "STORYBOARD SCREEN")`. The list is empty if the key is missing or the files are gone.
- In `_process_single_recursive_chunk`: use the cached storyboard when it is non-empty. Otherwise call `_sample_chunk_multimodal_frames` (stale-cache fallback).
- In `_balance_dynamic_chunk_frames`: the cached webcam branch returns `sb_frames` **untrimmed**. The live branch also stops trimming: drop the `trim_storyboard_frames` call at line 227 and keep `trim_storyboard_frames` itself for other callers.

- [ ] **Step 1: Failing tests**

```python
def test_cached_webcam_does_not_trim_storyboard(tmp_ws_with_enrichment):
    sb = [(f"00:00:{i:02d}", p, "b64", "STORYBOARD SCREEN") for i in range(16)]
    out_sb, wc, tier = _balance_dynamic_chunk_frames(ws, chunk, sb, None, None)
    assert len(out_sb) == 16 and wc and tier == "cached-enrichment"

def test_stale_cache_falls_back(tmp_ws_old_enrichment):
    assert _load_cached_storyboard(ws, chunk) == []
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(pass1): send all cached storyboard + webcam frames untrimmed`

---

### Task 5: Pass 2 reaction verify becomes opt-in, docs reordered

**Files:**
- Modify: `lib/process/assembly.py:94-95` (run `apply_reaction_verify` only when `args.post_reaction_verify`)
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py` (add `--post-reaction-verify`, `store_true`)
- Modify: `lib/process/runners/common.py:137-147` (`_init_webcam_source`: resolve the source when `--video-file` is set **or** `--reaction-verify` is set)
- Modify: `skills/anibon-timestamper-local/SKILL.md` (Pipeline table + Golden Path. The new order is: 1 Prepare → 2 Enrich prep (storyboard, webcam@peak/silence, song) → 3 Pass 1 → 4 Garbled → 5 Pass 2. State the full-context defaults and remove "keep rolling state-machine under 2k prompt tokens".)
- Test: `tests/test_post_reaction_optin.py`

- [ ] **Step 1: Failing test**: `finalize_and_assemble_timestamps` with `args.reaction_verify=True, post_reaction_verify=False` must not call `apply_reaction_verify` (monkeypatch spy).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the code changes and update the SKILL.md.
- [ ] **Step 4: Run** `pytest tests -q` and `python3 -X utf8 skills/anibon-timestamper-local/scripts/process_chunks_local.py <ws> --dry-run`. Expected: PASS, and the dry-run lists the chunks.
- [ ] **Step 5: Commit** `refactor: reaction verify opt-in post-pass; doc prep-first order`

---

## Final Verification

- [ ] Smoke test on a real workspace: `process_chunks_local.py <ws> --video-file <ws>/video_360p.mp4 --max-chunks 2 --no-resume`. The log must show the enrich prep stage **before** `PASS 1`. Each chunk line must show `storyboard=N webcam=…` with N not trimmed, and `~tok` may exceed 16k.
- [ ] Confirm LM Studio has the model loaded with `context_length` ≥ 32768. The user says RAM is plentiful; 24576 is too small for the new defaults.
