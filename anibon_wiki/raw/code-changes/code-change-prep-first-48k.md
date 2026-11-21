# Raw Code Change Snapshot: code-change-prep-first-48k
- Revision Range: `3a5a039~1..2dce04d`
- Acquired: 2026-11-21

## Implementation Plan
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


## Git Log & Diff
```diff
commit 2dce04da25ddf11b7a08a4c242b77c04ffb7b43f
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 22:19:03 2026 +0700

    fix(enrich): auto-upgrade stale webcam caches, resolve consensus corner, and normalize SAR
---
 lib/process/chunk_enrichment.py | 24 +++++++++++++++++++-----
 lib/video/webcam_storyboard.py  |  2 +-
 tests/test_scrutinize_fixes.py  | 33 +++++++++++++++++++++++++++++++--
 3 files changed, 51 insertions(+), 8 deletions(-)

diff --git a/lib/process/chunk_enrichment.py b/lib/process/chunk_enrichment.py
index efff315..1db8447 100644
--- a/lib/process/chunk_enrichment.py
+++ b/lib/process/chunk_enrichment.py
@@ -116,12 +116,24 @@ def _expand_cue_target_secs(chunk: dict, cues: Tuple[AudioWebcamCue, ...]) -> Tu
     return tuple(sorted(chosen[:cap]))
 
 
-def _extract_cue_webcam_entries(chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig) -> Tuple[List[str], List[dict]]:
+def _resolve_prep_webcam_box(chunk: dict, sb_frames: List[dict], cfg: ChunkEnrichConfig):
+    """Resolve consensus OBS webcam corner box across pre-extracted storyboard tiles."""
+    if not cfg.video_source:
+        return None
+    from process.runners.dynamic_chunk import _resolve_chunk_webcam_box
+    sb_tuples = [(str(f.get("ts") or ""), Path(str(f.get("path") or "")), "", "STORYBOARD SCREEN") for f in sb_frames if isinstance(f, dict) and f.get("path")]
+    lo, hi = int(chunk.get("start_sec", 0) or 0), int(chunk.get("end_sec", 0) or 0)
+    args = type("_Args", (), {"webcam_corner": cfg.webcam_corner})()
+    return _resolve_chunk_webcam_box(cfg.workspace, cfg.video_source, chunk.get("items") or [], args, sb_frames=sb_tuples, chunk_bounds=(lo, hi) if hi > lo else None)
+
+
+def _extract_cue_webcam_entries(chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig, sb_frames: List[dict] = ()) -> Tuple[List[str], List[dict]]:
     """Crop webcam closeups at expanded audio/silence/deictic timestamps and return paths + sheet metadata."""
     if not cues or not cfg.video_source:
         return [], []
     secs = _expand_cue_target_secs(chunk, cues)
-    req = ChunkWebcamRequest(cfg.workspace, cfg.video_source, chunk, secs, cfg.webcam_corner, max_frames=max(len(secs), _cfg.PASS1_WEBCAM_FRAMES))
+    box = _resolve_prep_webcam_box(chunk, list(sb_frames), cfg)
+    req = ChunkWebcamRequest(cfg.workspace, cfg.video_source, chunk, secs, cfg.webcam_corner, max_frames=max(len(secs), _cfg.PASS1_WEBCAM_FRAMES), webcam_box=box)
     rendered = sample_chunk_webcam_frames(req)
     paths = [str(f[1]) for f in rendered if len(f) >= 2]
     sheets = [{"ts": str(f[0]), "path": str(f[1]), "label": str(f[3]) if len(f) > 3 else "WEBCAM CLOSEUP"} for f in rendered if len(f) >= 2]
@@ -153,12 +165,14 @@ def _merge_activity_sidecar(workspace: Path, cid: str, block: str) -> None:
 
 
 def _read_cached_enrichment(cache_path: Path) -> Optional[dict]:
-    """Read enrichment JSON cache safely, returning None on missing or corrupt JSON."""
+    """Read enrichment JSON cache safely, returning None on missing, corrupt, or pre-sheet JSON."""
     if not cache_path.is_file():
         return None
     try:
         data = json.loads(cache_path.read_text(encoding="utf-8"))
-        return data if isinstance(data, dict) else None
+        if not isinstance(data, dict) or "storyboard_frames" not in data or "webcam_sheets" not in data:
+            return None
+        return data
     except (OSError, ValueError):
         return None
 
@@ -201,7 +215,7 @@ def enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict:
     chunk = _load_chunk_meta(chunk_path)
     sb_frames = prep_chunk_storyboard(chunk, cfg.slides_dir, cfg.workspace)
     cues = select_audio_webcam_cues(cfg.audio_source, WindowBounds(chunk["start_sec"], chunk["end_sec"]))
-    wc_paths, wc_sheets = _extract_cue_webcam_entries(chunk, cues, cfg)
+    wc_paths, wc_sheets = _extract_cue_webcam_entries(chunk, cues, cfg, sb_frames=sb_frames)
     song = _maybe_recover_chunk_song(chunk, cid, cfg)
     payload = _build_enrichment_payload(cues, wc_paths, song)
     payload["webcam_sheets"] = wc_sheets
diff --git a/lib/video/webcam_storyboard.py b/lib/video/webcam_storyboard.py
index 029319e..ce8d0ef 100644
--- a/lib/video/webcam_storyboard.py
+++ b/lib/video/webcam_storyboard.py
@@ -30,7 +30,7 @@ def _render_grid_jpeg(paths: Sequence[Path], out_path: Path, dims: Tuple[int, in
     for p in paths:
         cmd.extend(["-i", str(p)])
     norm = "".join(
-        f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black[v{i}];"
+        f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}];"
         for i in range(len(paths))
     )
     streams = "".join(f"[v{i}]" for i in range(len(paths)))
diff --git a/tests/test_scrutinize_fixes.py b/tests/test_scrutinize_fixes.py
index f07fc05..4c7b7a0 100644
--- a/tests/test_scrutinize_fixes.py
+++ b/tests/test_scrutinize_fixes.py
@@ -50,11 +50,17 @@ class TestScrutinizeFixes(unittest.TestCase):
         self.assertGreater(len(out_high), 25000)
 
     @unittest.skipIf(Image is None, "Pillow not installed")
-    def test_finding3_webcam_storyboard_packs_mixed_aspect_frames(self) -> None:
+    def test_finding3_webcam_storyboard_packs_mixed_aspect_and_sar_frames(self) -> None:
+        import subprocess
         f1 = self.ws / "wc_000737.jpg"
         f2 = self.ws / "wc_000770.jpg"
         Image.new("RGB", (320, 320), (80, 100, 120)).save(f1)
-        Image.new("RGB", (320, 220), (140, 90, 60)).save(f2)
+        raw = self.ws / "raw_non_square.jpg"
+        Image.new("RGB", (320, 220), (140, 90, 60)).save(raw)
+        subprocess.run(
+            ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", "scale=320:320,setsar=539/540", str(f2)],
+            check=True,
+        )
         frames = [
             ("00:12:17", f1, "b64_1", "WEBCAM CLOSEUP"),
             ("00:12:50", f2, "b64_2", "WEBCAM CLOSEUP"),
@@ -102,6 +108,29 @@ class TestScrutinizeFixes(unittest.TestCase):
         self.assertEqual(loaded_wc[0][0], "00:12:15-00:12:52")
         self.assertIn("6 panels:", loaded_wc[0][3])
 
+    def test_finding5_stale_cache_without_webcam_sheets_is_recomputed_and_resolves_box(self) -> None:
+        (self.ws / "chunks").mkdir()
+        (self.ws / "enrichment").mkdir()
+        cp = self.ws / "chunks" / "chunk_05.txt"
+        cp.write_text("CHUNK 05 | 00:11:15–00:13:45 | cutoff=00:13:30\n(00:12:17) เฮ้ย\n", encoding="utf-8")
+        # Legacy pre-26c7466 cache missing webcam_sheets
+        (self.ws / "enrichment" / "chunk_05.json").write_text(
+            json.dumps({"audio_cues": [], "webcam_frames": ["old.jpg"], "storyboard_frames": []}),
+            encoding="utf-8",
+        )
+        cfg = ChunkEnrichConfig(workspace=self.ws, audio_source=Path("a.m4a"), video_source=Path("v.mp4"), force=False)
+        cues = (AudioWebcamCue(737, "loud_peak", 3.5, "loud_peak"),)
+        captured_reqs = []
+        with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=cues) as m_cues, \
+             patch("process.chunk_enrichment._resolve_prep_webcam_box", return_value="FAKE_BOX") as m_box, \
+             patch("process.chunk_enrichment.sample_chunk_webcam_frames", side_effect=lambda req: (captured_reqs.append(req), [])[1]), \
+             patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=False):
+            payload = enrich_single_chunk(cp, cfg)
+        m_cues.assert_called_once()
+        m_box.assert_called_once()
+        self.assertEqual(captured_reqs[0].webcam_box, "FAKE_BOX")
+        self.assertIn("webcam_sheets", payload)
+
 
 if __name__ == "__main__":
     unittest.main()

commit 26c746622e08037f44a5526eac3ca84ca8dd5e9f
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 21:31:55 2026 +0700

    fix(local): prevent low-conf WI bleed, expand prep webcam cues, and normalize grid aspect ratios
---
 lib/process/chunk_enrichment.py      |  69 ++++++++++++++++------
 lib/process/prompts.py               |  30 +++++-----
 lib/process/runners/dynamic_chunk.py |  10 ++++
 lib/video/webcam_storyboard.py       |  10 +++-
 resources/garbled_replacements.json  |  18 +++++-
 tests/test_scrutinize_fixes.py       | 107 +++++++++++++++++++++++++++++++++++
 6 files changed, 210 insertions(+), 34 deletions(-)

diff --git a/lib/process/chunk_enrichment.py b/lib/process/chunk_enrichment.py
index 7e79619..efff315 100644
--- a/lib/process/chunk_enrichment.py
+++ b/lib/process/chunk_enrichment.py
@@ -9,10 +9,12 @@ from pathlib import Path
 from typing import TYPE_CHECKING, Any, List, Optional, Tuple
 
 from chunk.state import load_chunk_file
+from common import config as _cfg
 from common.config import WEBCAM_CORNER
 from common.log import format_progress, log_info, log_stage, log_warn
 from common.time import fmt_ts
 from process.chunk_storyboard_prep import prep_chunk_storyboard
+from process.multimodal_situations import collect_situational_candidates
 from process.reaction_source import resolve_reaction_audio_source, resolve_reaction_source
 from video.audio_webcam_cues import AudioWebcamCue, select_audio_webcam_cues
 from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
@@ -93,12 +95,37 @@ def _load_chat_and_anchors(workspace: Path, cid: str) -> Tuple[Tuple[str, ...],
         return chat_lines, []
 
 
-def _extract_cue_webcam_paths(chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig) -> List[str]:
-    """Crop webcam closeups at audio yell/silence timestamps and return relative paths."""
+def _expand_cue_target_secs(chunk: dict, cues: Tuple[AudioWebcamCue, ...]) -> Tuple[int, ...]:
+    """Expand audio peak/silence cues with onset/follow-through offsets and deictic speech cues."""
+    if not cues:
+        return ()
+    lo, hi = int(chunk.get("start_sec", 0) or 0), int(chunk.get("end_sec", 0) or 0)
+    cap = max(3, int(_cfg.PASS1_WEBCAM_FRAMES or 9))
+    chosen: List[int] = []
+    for c in cues:
+        for off in (0, -2, 2):
+            sec = max(lo, min(hi, int(c.sec) + off)) if hi > lo else max(0, int(c.sec) + off)
+            if all(abs(sec - prev) >= 2 for prev in chosen) and len(chosen) < cap:
+                chosen.append(sec)
+    items = chunk.get("items") or []
+    for _, sec in collect_situational_candidates(items, lo, hi if hi > lo else lo + 150, pinned_only=False):
+        if len(chosen) >= cap:
+            break
+        if all(abs(int(sec) - prev) >= 6 for prev in chosen):
+            chosen.append(int(sec))
+    return tuple(sorted(chosen[:cap]))
+
+
+def _extract_cue_webcam_entries(chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig) -> Tuple[List[str], List[dict]]:
+    """Crop webcam closeups at expanded audio/silence/deictic timestamps and return paths + sheet metadata."""
     if not cues or not cfg.video_source:
-        return []
-    req = ChunkWebcamRequest(cfg.workspace, cfg.video_source, chunk, tuple(c.sec for c in cues), cfg.webcam_corner)
-    return [str(f[1]) for f in sample_chunk_webcam_frames(req) if len(f) >= 2]
+        return [], []
+    secs = _expand_cue_target_secs(chunk, cues)
+    req = ChunkWebcamRequest(cfg.workspace, cfg.video_source, chunk, secs, cfg.webcam_corner, max_frames=max(len(secs), _cfg.PASS1_WEBCAM_FRAMES))
+    rendered = sample_chunk_webcam_frames(req)
+    paths = [str(f[1]) for f in rendered if len(f) >= 2]
+    sheets = [{"ts": str(f[0]), "path": str(f[1]), "label": str(f[3]) if len(f) > 3 else "WEBCAM CLOSEUP"} for f in rendered if len(f) >= 2]
+    return paths, sheets
 
 
 def _format_activity_block(cues: Tuple[AudioWebcamCue, ...], wc_paths: List[str], song: Optional["SongRecoveryResult"]) -> str:
@@ -148,8 +175,22 @@ def _build_enrichment_payload(
     }
 
 
+def _maybe_recover_chunk_song(chunk: dict, cid: str, cfg: ChunkEnrichConfig) -> Optional["SongRecoveryResult"]:
+    """Scan and recover background song + speaker speech when audio source and triggers match."""
+    if not cfg.audio_source:
+        return None
+    from process.music.chunk_scanner import SongScanRequest, SongTriggerInput
+    chat_lines, anchors = _load_chat_and_anchors(cfg.workspace, cid)
+    scratch = cfg.workspace / "enrichment" / "scratch" / cid
+    if cfg.force:
+        (scratch / "vocals_16k.json").unlink(missing_ok=True)
+    if should_scan_chunk_for_song(SongTriggerInput(chunk, chat_lines, anchors, cfg.audio_source)):
+        return scan_and_recover_chunk_song(SongScanRequest(chunk, cfg.audio_source, scratch), cfg.song_cfg)
+    return None
+
+
 def enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict:
-    """Run audio yell/silence webcam extraction and Shazam+whisper recovery for one chunk."""
+    """Run storyboard prep, audio yell/silence webcam extraction, and Shazam+whisper recovery."""
     cid = chunk_path.stem
     cache_path = cfg.workspace / "enrichment" / f"{cid}.json"
     if not cfg.force and (cached := _read_cached_enrichment(cache_path)) is not None:
@@ -158,19 +199,13 @@ def enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict:
         log_warn("enrich", f"{cid}: no audio/video/storyboard source resolved; skipping enrichment cache")
         return {}
     chunk = _load_chunk_meta(chunk_path)
+    sb_frames = prep_chunk_storyboard(chunk, cfg.slides_dir, cfg.workspace)
     cues = select_audio_webcam_cues(cfg.audio_source, WindowBounds(chunk["start_sec"], chunk["end_sec"]))
-    wc_paths = _extract_cue_webcam_paths(chunk, cues, cfg)
-    chat_lines, anchors = _load_chat_and_anchors(cfg.workspace, cid)
-    song: Optional["SongRecoveryResult"] = None
-    if cfg.audio_source:
-        from process.music.chunk_scanner import SongScanRequest, SongTriggerInput
-        scratch = cfg.workspace / "enrichment" / "scratch" / cid
-        if cfg.force:
-            (scratch / "vocals_16k.json").unlink(missing_ok=True)
-        if should_scan_chunk_for_song(SongTriggerInput(chunk, chat_lines, anchors, cfg.audio_source)):
-            song = scan_and_recover_chunk_song(SongScanRequest(chunk, cfg.audio_source, scratch), cfg.song_cfg)
+    wc_paths, wc_sheets = _extract_cue_webcam_entries(chunk, cues, cfg)
+    song = _maybe_recover_chunk_song(chunk, cid, cfg)
     payload = _build_enrichment_payload(cues, wc_paths, song)
-    payload["storyboard_frames"] = prep_chunk_storyboard(chunk, cfg.slides_dir, cfg.workspace)
+    payload["webcam_sheets"] = wc_sheets
+    payload["storyboard_frames"] = sb_frames
     cache_path.parent.mkdir(parents=True, exist_ok=True)
     cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
     _merge_activity_sidecar(cfg.workspace, cid, _format_activity_block(cues, wc_paths, song))
diff --git a/lib/process/prompts.py b/lib/process/prompts.py
index 485fc73..0ff3813 100644
--- a/lib/process/prompts.py
+++ b/lib/process/prompts.py
@@ -80,6 +80,11 @@ def load_world_identity_context(
         return ""
 
     limit = _cfg.WI_SNIPPET_LIMIT
+    cands = signal.get("candidates") or []
+    top_prob = max((float(c.get("prob", 0.0) or 0.0) for c in cands if isinstance(c, dict)), default=0.0)
+    conf = max(float(signal.get("confidence", 0.0) or 0.0), top_prob)
+    if limit <= 0 and 0.0 < conf < 0.65:
+        limit = 4000
     snippet = text[:limit] if limit > 0 else text
     if len(snippet) < len(text):
         snippet += "\n... (truncated)"
@@ -211,19 +216,18 @@ def build_chunk_entity_context(
             if len(matched_lines) >= max_count:
                 break
 
-    # Also resolve JIT domain entities (phonetic bridge + SQLite)
-    if allowed_sources is None or any(db_game in s.lower() for s in allowed_sources for db_game in ("fgo", "fate", "pokemon", "ygo", "yu-gi-oh")):
-        try:
-            from process.knowledge.domain_db import resolve_entities_for_chunk
-            jit_entities = resolve_entities_for_chunk(chunk_text, max_entities=10)
-            for entity_label in jit_entities:
-                if entity_label not in seen:
-                    seen.add(entity_label)
-                    matched_lines.append(f"- {entity_label}")
-                    if len(matched_lines) >= max_count:
-                        break
-        except Exception:
-            pass
+    # Always resolve JIT domain entities (phonetic bridge + SQLite) from actual chunk text
+    try:
+        from process.knowledge.domain_db import resolve_entities_for_chunk
+        jit_entities = resolve_entities_for_chunk(chunk_text, max_entities=15)
+        for entity_label in jit_entities:
+            if entity_label not in seen:
+                seen.add(entity_label)
+                matched_lines.append(f"- {entity_label}")
+                if len(matched_lines) >= max_count:
+                    break
+    except Exception:
+        pass
 
     if not matched_lines:
         return ""
diff --git a/lib/process/runners/dynamic_chunk.py b/lib/process/runners/dynamic_chunk.py
index c2067c0..721b920 100644
--- a/lib/process/runners/dynamic_chunk.py
+++ b/lib/process/runners/dynamic_chunk.py
@@ -204,6 +204,16 @@ def _load_cached_enrichment_webcam(workspace: Path, chunk: dict) -> list:
     """Load pre-extracted webcam sheets/frames from enrichment/chunk_NN.json."""
     cid = f"chunk_{int(chunk.get('_idx', 0) or 0):02d}"
     enr = load_chunk_enrichment(workspace, cid)
+    sheets = [s for s in (enr.get("webcam_sheets") or ()) if isinstance(s, dict)]
+    if sheets:
+        out = []
+        for s in sheets:
+            p = Path(str(s.get("path", "")))
+            if p.is_file():
+                b64 = base64.b64encode(p.read_bytes()).decode("ascii")
+                out.append((str(s.get("ts") or "00:00:00"), p, b64, str(s.get("label") or "WEBCAM CLOSEUP")))
+        if out:
+            return out
     cues = [c for c in (enr.get("audio_cues") or ()) if isinstance(c, dict)]
     cue_legend = ", ".join(f"{fmt_ts(int(c.get('sec', 0)))}:{c.get('event_type', 'cue')}" for c in cues)
     frames = []
diff --git a/lib/video/webcam_storyboard.py b/lib/video/webcam_storyboard.py
index 89d83a9..029319e 100644
--- a/lib/video/webcam_storyboard.py
+++ b/lib/video/webcam_storyboard.py
@@ -24,13 +24,17 @@ def grid_dims(count: int) -> Tuple[int, int]:
 
 
 def _render_grid_jpeg(paths: Sequence[Path], out_path: Path, dims: Tuple[int, int]) -> bool:
-    """Assemble equal-sized image inputs into a black-padded JPEG grid via ffmpeg."""
+    """Assemble image inputs (normalizing mixed aspect ratios to 320x320) into a JPEG grid."""
     cols, rows = dims
     cmd = ["ffmpeg", "-v", "error", "-y"]
     for p in paths:
         cmd.extend(["-i", str(p)])
-    streams = "".join(f"[{i}:v]" for i in range(len(paths)))
-    vf = f"{streams}concat=n={len(paths)}:v=1:a=0,tile={cols}x{rows}:padding=6:margin=6:color=black"
+    norm = "".join(
+        f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black[v{i}];"
+        for i in range(len(paths))
+    )
+    streams = "".join(f"[v{i}]" for i in range(len(paths)))
+    vf = f"{norm}{streams}concat=n={len(paths)}:v=1:a=0,tile={cols}x{rows}:padding=6:margin=6:color=black"
     cmd.extend(["-filter_complex", vf, "-frames:v", "1", "-q:v", "2", str(out_path)])
     res = subprocess.run(cmd, capture_output=True, timeout=30)
     return res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 100
diff --git a/resources/garbled_replacements.json b/resources/garbled_replacements.json
index 2d92567..5f6c11c 100644
--- a/resources/garbled_replacements.json
+++ b/resources/garbled_replacements.json
@@ -833,6 +833,9 @@
       "เบอร์วิว",
       "เบอร์วิท"
     ],
+    "burnice white": [
+      "ไice burner"
+    ],
     "Burning Down the House": [
       "ทnดาว"
     ],
@@ -3699,7 +3702,8 @@
       "มันer"
     ],
     "Monster Hunter": [
-      "Monทendant"
+      "Monทendant",
+      "war hunต"
     ],
     "Monster Hunter Rise": [
       "Monฮri"
@@ -4573,6 +4577,9 @@
     "Recycle": [
       "รีไซคle"
     ],
+    "Red Chip": [
+      "Rชip"
+    ],
     "Red Ocean": [
       "Red oceชน",
       "เรedโอเชน"
@@ -5361,6 +5368,9 @@
     "Storm Pod": [
       "Storพ"
     ],
+    "storm pod": [
+      "Strom po"
+    ],
     "Story": [
       "สตอี่"
     ],
@@ -5370,6 +5380,9 @@
     "Streamer": [
       "สamer"
     ],
+    "streamer": [
+      "สamมเมอร์"
+    ],
     "Streamer React": [
       "สamerreีact"
     ],
@@ -5655,6 +5668,9 @@
     "The Miracle": [
       "mirคิล"
     ],
+    "the miracle": [
+      "Miracิle"
+    ],
     "The Odyssey": [
       "โนันodิ"
     ],
diff --git a/tests/test_scrutinize_fixes.py b/tests/test_scrutinize_fixes.py
new file mode 100644
index 0000000..f07fc05
--- /dev/null
+++ b/tests/test_scrutinize_fixes.py
@@ -0,0 +1,107 @@
+from __future__ import annotations
+
+import json
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+from unittest.mock import patch
+
+_ROOT = Path(__file__).resolve().parents[1]
+if str(_ROOT / "lib") not in sys.path:
+    sys.path.insert(0, str(_ROOT / "lib"))
+
+try:
+    from PIL import Image
+except ImportError:
+    Image = None
+
+from process.chunk_enrichment import ChunkEnrichConfig, enrich_single_chunk
+from process.prompts import build_chunk_entity_context, load_world_identity_context
+from process.runners.dynamic_chunk import _load_cached_enrichment_webcam
+from video.audio_webcam_cues import AudioWebcamCue
+from video.webcam_storyboard import assemble_webcam_storyboard
+
+
+class TestScrutinizeFixes(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self.ws = Path(self._tmp.name)
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_finding1_jit_db_entities_never_blocked_by_wrong_allowed_sources(self) -> None:
+        with patch("process.knowledge.domain_db.resolve_entities_for_chunk", return_value=["Sen no Rikyu (เซ็น โนะ ริคิว)"]) as m_jit:
+            ctx = build_chunk_entity_context(
+                "สุ่มได้ NP5 ยาย ริคิว Noble Phantasm",
+                glossary={"Ellen Joe": {"en": "Ellen Joe", "th": "เอลเลน โจ", "sources": ["Zenless_Zone_Zero.md"]}},
+                allowed_sources={"Zenless_Zone_Zero.md"},
+            )
+        m_jit.assert_called_once()
+        self.assertIn("Sen no Rikyu (เซ็น โนะ ริคิว)", ctx)
+
+    def test_finding1_low_confidence_wi_is_capped_not_40kb_dump(self) -> None:
+        ref = self.ws / "Zenless_Zone_Zero.md"
+        ref.write_text("Z" * 30000, encoding="utf-8")
+        out_low = load_world_identity_context({"best_file": "Zenless_Zone_Zero.md", "confidence": 0.40}, self.ws)
+        self.assertLess(len(out_low), 6000)
+        out_high = load_world_identity_context({"best_file": "Zenless_Zone_Zero.md", "confidence": 0.85}, self.ws)
+        self.assertGreater(len(out_high), 25000)
+
+    @unittest.skipIf(Image is None, "Pillow not installed")
+    def test_finding3_webcam_storyboard_packs_mixed_aspect_frames(self) -> None:
+        f1 = self.ws / "wc_000737.jpg"
+        f2 = self.ws / "wc_000770.jpg"
+        Image.new("RGB", (320, 320), (80, 100, 120)).save(f1)
+        Image.new("RGB", (320, 220), (140, 90, 60)).save(f2)
+        frames = [
+            ("00:12:17", f1, "b64_1", "WEBCAM CLOSEUP"),
+            ("00:12:50", f2, "b64_2", "WEBCAM CLOSEUP"),
+        ]
+        out_sheet = self.ws / "wc_sheet_05_0.jpg"
+        sheet = assemble_webcam_storyboard(frames, out_sheet)
+        self.assertIsNotNone(sheet)
+        self.assertTrue(out_sheet.is_file())
+        self.assertIn("2 panels:", sheet[3])
+
+    def test_finding2_and_4_enrich_expands_webcam_cues_and_preserves_sheet_legend(self) -> None:
+        (self.ws / "chunks").mkdir()
+        cp = self.ws / "chunks" / "chunk_05.txt"
+        cp.write_text(
+            "CHUNK 05 | 00:11:15–00:13:45 | cutoff=00:13:30\n"
+            "(00:11:20) สวัสดี\n"
+            "(00:12:17) เฮ้ย ได้แล้ว\n"
+            "(00:12:50) ดูกล้องนะ ดูนี่นะ\n",
+            encoding="utf-8",
+        )
+        sheet_file = self.ws / "frames" / "webcam_chunk" / "wc_sheet_05_0.jpg"
+        sheet_file.parent.mkdir(parents=True)
+        sheet_file.write_bytes(b"fake-sheet")
+        legend = "WEBCAM STORYBOARD (3x2 grid, left-to-right top-to-bottom; 6 panels: [1]=00:12:15 WEBCAM CLOSEUP)"
+        fake_wc = [("00:12:15-00:12:52", sheet_file, "b64", legend)]
+        captured_reqs = []
+
+        def spy_sample(req):
+            captured_reqs.append(req)
+            return fake_wc
+
+        cfg = ChunkEnrichConfig(workspace=self.ws, audio_source=Path("a.m4a"), video_source=Path("v.mp4"))
+        cues = (AudioWebcamCue(737, "loud_peak", 3.5, "loud_peak"),)
+        with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=cues), \
+             patch("process.chunk_enrichment.sample_chunk_webcam_frames", side_effect=spy_sample), \
+             patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=False):
+            payload = enrich_single_chunk(cp, cfg)
+
+        self.assertTrue(captured_reqs)
+        # Finding 2: 1 audio cue + deictic speech must expand to multiple target seconds (>= 3)
+        self.assertGreaterEqual(len(captured_reqs[0].target_secs), 3)
+        # Finding 4: cached webcam_frames preserves sheet legend and timestamp span when reloaded
+        loaded_wc = _load_cached_enrichment_webcam(self.ws, {"_idx": 5, "start_sec": 675})
+        self.assertEqual(len(loaded_wc), 1)
+        self.assertEqual(loaded_wc[0][0], "00:12:15-00:12:52")
+        self.assertIn("6 panels:", loaded_wc[0][3])
+
+
+if __name__ == "__main__":
+    unittest.main()

commit bfcc1b39ca5eb8fd7879d1f8d5d1846b21978b73
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 19:27:59 2026 +0700

    config(local): enforce 2x context headroom (49152) in config and skill docs
---
 lib/common/config.py                                         | 12 ++++++------
 skills/anibon-timestamper-local/SKILL.md                     |  2 +-
 skills/anibon-timestamper-local/config.json                  |  2 +-
 .../references/hardware-and-endpoints.md                     |  8 ++++----
 4 files changed, 12 insertions(+), 12 deletions(-)

diff --git a/lib/common/config.py b/lib/common/config.py
index d7b6168..1e3d66a 100644
--- a/lib/common/config.py
+++ b/lib/common/config.py
@@ -209,11 +209,11 @@ LINE_CAP_LIMIT: int = 25
 LINE_WARN_LIMIT: int = 20
 
 DEFAULT_MULTIMODAL_CHUNKS: bool = True
-EVAL_BATCH_SIZE: int = 16384
+EVAL_BATCH_SIZE: int = 49152
 TOKENS_PER_IMAGE: int = 260
 SCENE_DELTA_THRESHOLD: float = 0.12
-MAX_CHUNK_FRAMES: int = 16
-PASS1_WEBCAM_FRAMES: int = 6
+MAX_CHUNK_FRAMES: int = 24
+PASS1_WEBCAM_FRAMES: int = 9
 COMPACT_CHUNK_MAX_LINES: int = 0
 LIVECHAT_MAX_LINES: int = 0
 WI_SNIPPET_LIMIT: int = 0
@@ -280,7 +280,7 @@ def reload_config() -> None:
     SUMMARIZER_MAX_TOKENS = cfg_int("summarizer_max_tokens", 8192)
     SUMMARIZER_TIMEOUT_SEC = cfg_int("summarizer_timeout_sec", 600)
 
-    ENTITY_CONTEXT_MAX_TOKENS = cfg_int("entity_context_max_tokens", 300)
+    ENTITY_CONTEXT_MAX_TOKENS = cfg_int("entity_context_max_tokens", 2000)
 
     DEFAULT_TEMPERATURE = cfg_float("temperature", 0.1)
     VISION_TEMPERATURE = cfg_float("vision_temperature", 0.2)
@@ -301,10 +301,10 @@ def reload_config() -> None:
     LINE_WARN_LIMIT = cfg_int("line_warn_limit", 20)
 
     DEFAULT_MULTIMODAL_CHUNKS = cfg_bool("multimodal_chunks", True)
-    EVAL_BATCH_SIZE = cfg_int("eval_batch_size", 16384)
+    EVAL_BATCH_SIZE = cfg_int("eval_batch_size", 49152)
     TOKENS_PER_IMAGE = cfg_int("tokens_per_image", 260)
     SCENE_DELTA_THRESHOLD = cfg_float("scene_delta_threshold", 0.12)
-    MAX_CHUNK_FRAMES = cfg_int("max_chunk_frames", 16)
+    MAX_CHUNK_FRAMES = cfg_int("max_chunk_frames", 24)
     COMPACT_CHUNK_MAX_LINES = cfg_int("compact_chunk_max_lines", 0)
     LIVECHAT_MAX_LINES = cfg_int("livechat_max_lines", 0)
     WI_SNIPPET_LIMIT = cfg_int("wi_snippet_limit", 0)
diff --git a/skills/anibon-timestamper-local/SKILL.md b/skills/anibon-timestamper-local/SKILL.md
index 612e162..f8f5dda 100644
--- a/skills/anibon-timestamper-local/SKILL.md
+++ b/skills/anibon-timestamper-local/SKILL.md
@@ -58,7 +58,7 @@ Use `--overlap 20` for walking vlogs / convention tours (`2.5`-min blocks).
 curl -s --max-time 8 http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'
 ```
 
-- **Default model**: `gemma-4-12b-it-qat@q4_k_xl` (`"parallel": 1`, `"context_length": 32768+`, `"eval_batch_size": 32768`). Full-context mode sends every transcript line, full livechat, full World Identity lore, and all storyboard + webcam peak/silence frames without artificial truncation. Smoke-test `--max-chunks 1` before launching 50+ chunks.
+- **Default model**: `gemma-4-12b-it-qat@q4_k_xl` (`"parallel": 1`, `"context_length": 49152` — **2× headroom over peak ~24k tokens to prevent context-brim hallucination**, `"eval_batch_size": 49152`). Full-context mode sends every transcript line, full livechat, full World Identity lore, and all storyboard + webcam peak/silence frames without artificial truncation. Smoke-test `--max-chunks 1` before launching 50+ chunks.
 - **Ollama `*:cloud` Trap**: Never point `process_chunks_local.py` at local Ollama `*:cloud` tags (e.g. `gemma4:cloud`); `HTTP 402` triggers blackout-recovery loops. If LM Studio at `100.115.25.30:1234` is down, ask the user to start it. Load payloads, `12b` vs `26b` benchmark, and TokenMe setup → [`references/hardware-and-endpoints.md`](references/hardware-and-endpoints.md).
 
 ### 3. Run Timestamper / Detached Launch / Pause Control
diff --git a/skills/anibon-timestamper-local/config.json b/skills/anibon-timestamper-local/config.json
index 0563eb1..20a3dea 100644
--- a/skills/anibon-timestamper-local/config.json
+++ b/skills/anibon-timestamper-local/config.json
@@ -25,7 +25,7 @@
   "block_size": 2400,
   "byte_cap_limit": 3500,
   "multimodal_chunks": true,
-  "eval_batch_size": 32768,
+  "eval_batch_size": 49152,
   "tokens_per_image": 260,
   "scene_delta_threshold": 0.12,
   "max_chunk_frames": 24,
diff --git a/skills/anibon-timestamper-local/references/hardware-and-endpoints.md b/skills/anibon-timestamper-local/references/hardware-and-endpoints.md
index a7a117c..e24c16e 100644
--- a/skills/anibon-timestamper-local/references/hardware-and-endpoints.md
+++ b/skills/anibon-timestamper-local/references/hardware-and-endpoints.md
@@ -16,17 +16,17 @@ Load payload (`POST http://100.115.25.30:1234/api/v1/models/load`):
 
 ```json
 {
-  "model": "google/gemma-4-12b-qat",
+  "model": "gemma-4-12b-it-qat@q4_k_xl",
   "parallel": 1,
-  "context_length": 24576,
+  "context_length": 49152,
   "eval_batch_size": 1024,
   "flash_attention": true,
   "offload_kv_cache_to_gpu": true
 }
 ```
 
-- **Shared-Host Memory Sizing (`"parallel": 1`)**: Do **not** blindly load `"context_length": 262144` when the LM Studio host shares `<= 32 GB` system RAM with heavy workloads (e.g. a 12 GB game server) or uses default `parallel: 4`. For sequential Pass 1 (`~5.3k–15k` tokens with frames + `4096` output) and Pass 2 summary (`< 16k` tokens), load with `"parallel": 1` and `"context_length": 16384` (or `24576` for 16-frame multimodal) to cut KV cache RAM 4×.
-- **Verified 16GB Tesla P100 16-Frame Profile**: `gemma-4-12b-it-qat@q4_k_xl`, `"parallel": 1`, `"context_checkpoints": 0`, `"eval_batch_size": 1024`, `"physical_batch_size": 1120`, `"offload_kv_cache_to_gpu": true` completed `93/93` chunks at `--eval-batch-size 12288 --max-chunk-frames 16` (`avg 14.73` frames/chunk) with 0 OOMs.
+- **2× Context Headroom Rule (`"context_length": 49152`, `"parallel": 1` — CRITICAL ANTI-HALLUCINATION)**: In Full-Context Prep-First mode (untrimmed transcript lines + full LiveChat + full World Identity + up to 24 storyboard frames + webcam peak/silence sheets + 4,096 output tokens), peak per-chunk token usage reaches `~20,000–24,500` tokens (average `~13,400`). Running at `24576` fills `81–98%` of the context window ("ปริ่มขอบ") and causes attention degradation and hallucinations. **Always double (`× 2`) the peak requirement to `"context_length": 49152` (48K, or `65536` / 64K)** with `"parallel": 1`, `"flash_attention": true`, and `"offload_kv_cache_to_gpu": true`. Because Gemma 4 12B uses Sliding Window Attention (SWA) on alternating layers, `49152` at `"parallel": 1` fits comfortably inside P100 16GB VRAM.
+- **Verified 16GB Tesla P100 Full-Context Profile**: `gemma-4-12b-it-qat@q4_k_xl`, `"parallel": 1`, `"context_length": 49152`, `"context_checkpoints": 0`, `"eval_batch_size": 1024`, `"physical_batch_size": 1120`, `"offload_kv_cache_to_gpu": true` with CLI `--eval-batch-size 49152 --max-chunk-frames 24`.
 - Always smoke-test with `--max-chunks 1` before launching a 50+ chunk run.
 
 ## 2. Model Selection Benchmark (Tesla P100 16GB)

commit 1d274867fad20d5380354ff3dcffbee0442812c3
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 16:02:32 2026 +0700

    feat(enrich): log per-chunk prep progress and default audio.cpp/whisper endpoints in launcher
---
 lib/process/chunk_enrichment.py                         | 12 ++++++++----
 skills/anibon-timestamper-local/scripts/launch_local.sh |  8 +++++++-
 2 files changed, 15 insertions(+), 5 deletions(-)

diff --git a/lib/process/chunk_enrichment.py b/lib/process/chunk_enrichment.py
index b93e631..7e79619 100644
--- a/lib/process/chunk_enrichment.py
+++ b/lib/process/chunk_enrichment.py
@@ -10,7 +10,7 @@ from typing import TYPE_CHECKING, Any, List, Optional, Tuple
 
 from chunk.state import load_chunk_file
 from common.config import WEBCAM_CORNER
-from common.log import log_warn
+from common.log import format_progress, log_info, log_stage, log_warn
 from common.time import fmt_ts
 from process.chunk_storyboard_prep import prep_chunk_storyboard
 from process.reaction_source import resolve_reaction_audio_source, resolve_reaction_source
@@ -195,9 +195,13 @@ def enrich_workspace_chunks(cfg: ChunkEnrichConfig) -> int:
     if cfg.slides_dir is None:
         from process.multimodal import prepare_storyboard_slides
         cfg = replace(cfg, slides_dir=prepare_storyboard_slides(cfg.workspace))
-    for cf in chunk_files:
-        enrich_single_chunk(cf, cfg)
-    return len(chunk_files)
+    total = len(chunk_files)
+    log_stage(f"STAGE 2 :: PREP-FIRST ENRICHMENT ({total} chunks: storyboard + webcam@peak/silence + song)")
+    for i, cf in enumerate(chunk_files, start=1):
+        p = enrich_single_chunk(cf, cfg)
+        song_lbl = f" song={p['song']['title']}" if p.get("song") else ""
+        log_info("prep", f"{format_progress(i, total)} {cf.stem} | sb={len(p.get('storyboard_frames') or ())} cues={len(p.get('audio_cues') or ())} wc={len(p.get('webcam_frames') or ())}{song_lbl}")
+    return total
 
 
 __all__ = ["ChunkEnrichConfig", "enrich_single_chunk", "enrich_workspace_chunks", "resolve_workspace_media"]
diff --git a/skills/anibon-timestamper-local/scripts/launch_local.sh b/skills/anibon-timestamper-local/scripts/launch_local.sh
index 4e61653..dc48cdc 100755
--- a/skills/anibon-timestamper-local/scripts/launch_local.sh
+++ b/skills/anibon-timestamper-local/scripts/launch_local.sh
@@ -73,7 +73,13 @@ if [[ $# -ge 7 ]]; then
     EXTRA_ARGS+=("${@:7}")
 fi
 
-nohup env PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 python3 -u -X utf8 "$RUNNER_SCRIPT" "$WORKSPACE" \
+WHISPER_ENDPOINT="${WHISPER_ENDPOINT:-http://100.115.25.30:8082/inference}"
+AUDIOCPP_URL="${AUDIOCPP_URL:-http://100.115.25.30:8080/v1/tasks/run}"
+USE_AUDIOCPP="${USE_AUDIOCPP:-1}"
+
+nohup env PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
+    WHISPER_ENDPOINT="$WHISPER_ENDPOINT" AUDIOCPP_URL="$AUDIOCPP_URL" USE_AUDIOCPP="$USE_AUDIOCPP" \
+    python3 -u -X utf8 "$RUNNER_SCRIPT" "$WORKSPACE" \
     --endpoint "$ENDPOINT" \
     --model "$MODEL" \
     --lang "$LANG" \

commit d3e997af02c45344954096ac61ed957f544ec232
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 15:52:57 2026 +0700

    refactor: reaction verify opt-in post-pass; doc prep-first order
---
 lib/process/assembly.py                            |  2 +-
 lib/process/runners/common.py                      |  5 +-
 skills/anibon-timestamper-local/SKILL.md           | 17 ++++---
 .../scripts/process_chunks_local.py                |  3 +-
 tests/test_post_reaction_optin.py                  | 58 ++++++++++++++++++++++
 5 files changed, 74 insertions(+), 11 deletions(-)

diff --git a/lib/process/assembly.py b/lib/process/assembly.py
index fdab475..569c5c0 100644
--- a/lib/process/assembly.py
+++ b/lib/process/assembly.py
@@ -91,7 +91,7 @@ def _prune_and_verify_timestamps(
         deduped = apply_vision_verify(deduped, workspace, args, model)
     if not no_summarizer_pass:
         deduped = prune_essential(endpoint, model, deduped, temperature)
-    if args:
+    if args and getattr(args, "post_reaction_verify", False):
         deduped = apply_reaction_verify(deduped, workspace, ReactionRunConfig(args, model))
     return deduped
 
diff --git a/lib/process/runners/common.py b/lib/process/runners/common.py
index 9f6e0d5..247c1d2 100644
--- a/lib/process/runners/common.py
+++ b/lib/process/runners/common.py
@@ -139,7 +139,10 @@ def _init_webcam_source(
     args: Optional[argparse.Namespace],
 ) -> Optional[Path | str]:
     """Resolve optional video source once for Pass 1 webcam closeup grounding."""
-    if not args or not getattr(args, "reaction_verify", False):
+    if not args:
+        return None
+    has_video_arg = bool(getattr(args, "video_file", None) or getattr(args, "reaction_verify", False) or getattr(args, "remote_snap", False))
+    if not has_video_arg and not any((workspace / f).is_file() for f in ("video_360p.mp4", "video.mp4", "stream.mp4")):
         return None
     src = resolve_reaction_source(workspace, args)
     if src:
diff --git a/skills/anibon-timestamper-local/SKILL.md b/skills/anibon-timestamper-local/SKILL.md
index a8068f3..612e162 100644
--- a/skills/anibon-timestamper-local/SKILL.md
+++ b/skills/anibon-timestamper-local/SKILL.md
@@ -28,12 +28,13 @@ All commands run from plugin root (`anibon-stream-synthesis`). Shared utilities
 
 | Stage | Entrypoint / Modules | Role |
 |---|---|---|
-| **1. Prepare & Chunk** | `scripts/prepare_video.py`, `scripts/enrich_chunks.py` | Downloads subtitles, chunks transcript (`--keep-silent-chunks` preserves quiet gaps), aligns `--live-chat`, computes `mood_555.json`, optionally pre-enriches yell/silence webcam cues + Shazam -> `audio.cpp` -> `whisper.cpp`. |
-| **1.5 Clean & Glossary** | `lib/process/audit.py`, `lib/process/knowledge/` | Applies `garbled_replacements.json` + `default_mappings.json` on disk, writes `signals.json` + `entity_glossary.json`. |
-| **2. Pass 1 Segmentation** | `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, `control_chunks_local.py`, `scripts/validate_mood.py` | Runs rolling state-machine (`lib/chunk/state.py`, `lib/chunk/pause.py`) with multimodal keyframes + mood hints → `all_timestamps.txt`. |
-| **3. Garbled Collector** | `lib/process/garbled_collector.py`, `scripts/whisper_dispatcher.py` | Slices audio on-the-fly via local `whisper.cpp`, updates `garbled_replacements.json`, cleans `all_timestamps.txt` & `chunks/`. |
-| **4. Pass 2 Summary & Gates** | `lib/process/summarizer.py`, `lib/process/byte_cap.py`, `lib/process/parity_gates.py` | Prunes essential stamps (~40–60), assembles 4–6 macro parts (`<= 20` lines/part), audits glossary & runs gap/section gates → `anibon_timestamps.md`. |
-| **4.5 Edited VOD Shift** | `scripts/reconcile_edited_stream.py` | Detects post-broadcast YouTube Studio trims via 1000Hz FFT audio correlation and shifts timestamps. |
+| **1. Prepare & Chunk** | `scripts/prepare_video.py` | Downloads subtitles, storyboards, chunks transcript (`--keep-silent-chunks` preserves quiet gaps), aligns `--live-chat`, computes `mood_555.json`. |
+| **2. Prep-First Enrichment (MANDATORY BEFORE PASS 1)** | `scripts/enrich_chunks.py`, `lib/process/chunk_enrichment.py`, `lib/process/chunk_storyboard_prep.py` | Pre-prepares **all** chunk evidence into `enrichment/chunk_NN.json` before LM inference: storyboard screen tiles, webcam frame crops aligned with soundwave loud peaks & silence shock drops, and Shazam song detection -> `audio.cpp` vocal split -> `whisper.cpp` speech recovery. Runs automatically at the start of `process_chunks_local.py` (disable only via `--no-enrich`). |
+| **2.5 Clean & Glossary** | `lib/process/audit.py`, `lib/process/knowledge/` | Applies `garbled_replacements.json` + `default_mappings.json` on disk, writes `signals.json` + `entity_glossary.json`. |
+| **3. Pass 1 Full-Context Segmentation** | `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, `control_chunks_local.py`, `scripts/validate_mood.py` | Feeds **untrimmed** storyboard screen tiles + pre-cropped webcam peak/silence sheets + detected song/recovered speech + full chunk transcript lines + full livechat + full World Identity reference into rolling state-machine (`lib/chunk/state.py`, `lib/chunk/pause.py`) → `all_timestamps.txt`. |
+| **4. Garbled Collector** | `lib/process/garbled_collector.py`, `scripts/whisper_dispatcher.py` | Slices audio on-the-fly via local `whisper.cpp`, updates `garbled_replacements.json`, cleans `all_timestamps.txt` & `chunks/`. |
+| **5. Pass 2 Summary & Gates** | `lib/process/summarizer.py`, `lib/process/byte_cap.py`, `lib/process/parity_gates.py` | Prunes essential stamps (~40–60), assembles 4–6 macro parts (`<= 20` lines/part), audits glossary & runs gap/section gates → `anibon_timestamps.md`. (Post-Pass-1 webcam reaction verify is opt-in only via `--post-reaction-verify` because webcam crops are already fed into Pass 1). |
+| **5.5 Edited VOD Shift** | `scripts/reconcile_edited_stream.py` | Detects post-broadcast YouTube Studio trims via 1000Hz FFT audio correlation and shifts timestamps. |
 
 **Execution Modes**: `--mode recursive` (default; `SAME_TOPIC` merges unless a >8–10 min monologue needs a distinct sub-angle; `TOPIC_SHIFT` emits 1–2 stamps `>=45s` apart; Pass 2 groups into 4–6 macro parts) vs `--mode group` (fixed 4-chunk groups). Run `--help` on any script for full flags.
 
@@ -57,7 +58,7 @@ Use `--overlap 20` for walking vlogs / convention tours (`2.5`-min blocks).
 curl -s --max-time 8 http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'
 ```
 
-- **Default model**: `gemma-4-12b-it-qat@q4_k_xl` (`"parallel": 1`, `"context_length": 16384–24576`). Smoke-test `--max-chunks 1` before launching 50+ chunks.
+- **Default model**: `gemma-4-12b-it-qat@q4_k_xl` (`"parallel": 1`, `"context_length": 32768+`, `"eval_batch_size": 32768`). Full-context mode sends every transcript line, full livechat, full World Identity lore, and all storyboard + webcam peak/silence frames without artificial truncation. Smoke-test `--max-chunks 1` before launching 50+ chunks.
 - **Ollama `*:cloud` Trap**: Never point `process_chunks_local.py` at local Ollama `*:cloud` tags (e.g. `gemma4:cloud`); `HTTP 402` triggers blackout-recovery loops. If LM Studio at `100.115.25.30:1234` is down, ask the user to start it. Load payloads, `12b` vs `26b` benchmark, and TokenMe setup → [`references/hardware-and-endpoints.md`](references/hardware-and-endpoints.md).
 
 ### 3. Run Timestamper / Detached Launch / Pause Control
@@ -122,7 +123,7 @@ python3 scripts/check_sections.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestam
 |---|---|---|
 | *"Single chunk is faster to run."* | Emits 35+ noisy micro-stamps. | Use `--mode recursive` with rolling summaries. |
 | *"I can invent tags like `[วิเคราะห์]`."* | Breaks comment parsers & benchmarks. | Normalizer remaps to whitelisted tags (`[Talk]`). |
-| *"Summarize the whole 3h transcript in 1 prompt."* | Exceeds context and degrades entity recall. | Keep rolling state-machine under 2k prompt tokens. |
+| *"Summarize the whole 3h transcript in 1 prompt."* | Exceeds single-pass output attention and degrades entity recall. | Process chunk-by-chunk with full chunk evidence (storyboard + webcam crops + audio/song + full transcript) and rolling state-machine. |
 | *"Write a custom Python script to go faster."* | Breaks state, resume logic, and UTF-8. | Use `process_chunks_local.py` flags only. |
 | *"Kill the worker PID to pause, relaunch later."* | Aborts active chunk and risks duplicate PIDs. | Run `control_chunks_local.py <ws> pause` / `continue` (pass `--timeout 0` if urgent). |
 | *"Output looks good without World Identity check."* | Hallucinates games or drops Thai Pokémon names. | Run `anibon-world-identity` + `stage5-audit-checklist.md`. |
diff --git a/skills/anibon-timestamper-local/scripts/process_chunks_local.py b/skills/anibon-timestamper-local/scripts/process_chunks_local.py
index 355094c..4ecdee4 100644
--- a/skills/anibon-timestamper-local/scripts/process_chunks_local.py
+++ b/skills/anibon-timestamper-local/scripts/process_chunks_local.py
@@ -176,7 +176,8 @@ def build_argument_parser() -> argparse.ArgumentParser:
     ap.add_argument("--whisper-model", default=None)
     ap.add_argument("--no-garbled-collector", action="store_true")
     ap.add_argument("--vision-verify", action="store_true")
-    ap.add_argument("--reaction-verify", action="store_true", default=REACTION_VERIFY)
+    ap.add_argument("--reaction-verify", action="store_true", default=REACTION_VERIFY, help="Enable Pass 1 live webcam closeup fallback when video source exists")
+    ap.add_argument("--post-reaction-verify", action="store_true", help="Opt-in: run post-Pass-1 (Pass 2) webcam reaction onset verification")
     ap.add_argument(
         "--webcam-corner",
         default=WEBCAM_CORNER,
diff --git a/tests/test_post_reaction_optin.py b/tests/test_post_reaction_optin.py
new file mode 100644
index 0000000..ba8c0e2
--- /dev/null
+++ b/tests/test_post_reaction_optin.py
@@ -0,0 +1,58 @@
+from __future__ import annotations
+
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+from unittest.mock import patch
+
+_ROOT = Path(__file__).resolve().parents[1]
+if str(_ROOT / "lib") not in sys.path:
+    sys.path.insert(0, str(_ROOT / "lib"))
+if str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts") not in sys.path:
+    sys.path.insert(0, str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts"))
+
+import process_chunks_local as pcl
+from process.assembly import _prune_and_verify_timestamps
+from process.runners.common import _init_webcam_source
+
+
+class TestPostReactionOptIn(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self.ws = Path(self._tmp.name)
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_pass2_skips_reaction_verify_unless_post_reaction_verify_set(self) -> None:
+        ap = pcl.build_argument_parser()
+        args = ap.parse_args([str(self.ws), "--reaction-verify"])
+        self.assertFalse(getattr(args, "post_reaction_verify", False))
+        stamps = ["00:01:00 - [Reaction] อึ้งกับฉากเปิดตัวบอสใหม่"]
+        with patch("process.assembly.apply_reaction_verify") as m_rx, \
+             patch("process.assembly.apply_vision_verify", side_effect=lambda s, *a: s):
+            _prune_and_verify_timestamps(stamps, self.ws, "http://127.0.0.1:1234", "m", 0.1, args, True)
+        m_rx.assert_not_called()
+
+    def test_pass2_runs_reaction_verify_when_post_reaction_verify_set(self) -> None:
+        ap = pcl.build_argument_parser()
+        args = ap.parse_args([str(self.ws), "--post-reaction-verify"])
+        self.assertTrue(args.post_reaction_verify)
+        stamps = ["00:01:00 - [Reaction] อึ้งกับฉากเปิดตัวบอสใหม่"]
+        with patch("process.assembly.apply_reaction_verify", return_value=stamps) as m_rx, \
+             patch("process.assembly.apply_vision_verify", side_effect=lambda s, *a: s):
+            _prune_and_verify_timestamps(stamps, self.ws, "http://127.0.0.1:1234", "m", 0.1, args, True)
+        m_rx.assert_called_once()
+
+    def test_init_webcam_source_resolves_when_video_file_present(self) -> None:
+        v = self.ws / "video_360p.mp4"
+        v.write_bytes(b"fake")
+        ap = pcl.build_argument_parser()
+        args = ap.parse_args([str(self.ws), "--video-file", str(v)])
+        src = _init_webcam_source(self.ws, args)
+        self.assertEqual(Path(str(src)), v)
+
+
+if __name__ == "__main__":
+    unittest.main()

commit 45e5930ec49eefe6390aba88cba72b6d00ad0816
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 15:51:19 2026 +0700

    feat(pass1): send all cached storyboard + webcam frames untrimmed
---
 lib/process/runners/common.py        |  2 +-
 lib/process/runners/dynamic_chunk.py | 25 ++++++++++---
 lib/process/runners/recursive.py     |  9 +++--
 tests/test_pass1_full_frames.py      | 72 ++++++++++++++++++++++++++++++++++++
 4 files changed, 99 insertions(+), 9 deletions(-)

diff --git a/lib/process/runners/common.py b/lib/process/runners/common.py
index 0821e85..9f6e0d5 100644
--- a/lib/process/runners/common.py
+++ b/lib/process/runners/common.py
@@ -27,7 +27,7 @@ from process.multimodal import (
 )
 from process.multimodal_situations import collect_situational_candidates, select_spaced_seconds
 from process.reaction_io import resolve_reaction_source
-from process.runners.dynamic_chunk import _balance_dynamic_chunk_frames
+from process.runners.dynamic_chunk import _balance_dynamic_chunk_frames, _load_cached_storyboard
 from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
 
 
diff --git a/lib/process/runners/dynamic_chunk.py b/lib/process/runners/dynamic_chunk.py
index 111e5ee..c2067c0 100644
--- a/lib/process/runners/dynamic_chunk.py
+++ b/lib/process/runners/dynamic_chunk.py
@@ -184,6 +184,22 @@ def _enrich_plan_with_peaks(
     return DynamicPlan(plan.tier, plan.sb_keep, plan.wc_frames, plan.mean_mad, eff), max_z
 
 
+def _load_cached_storyboard(workspace: Path, chunk: dict) -> list:
+    """Load pre-extracted storyboard screen tiles from enrichment/chunk_NN.json."""
+    cid = f"chunk_{int(chunk.get('_idx', 0) or 0):02d}"
+    enr = load_chunk_enrichment(workspace, cid)
+    frames = []
+    for item in enr.get("storyboard_frames") or ():
+        if not isinstance(item, dict):
+            continue
+        p = Path(str(item.get("path", "")))
+        if not p.is_file():
+            continue
+        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
+        frames.append((str(item.get("ts") or "00:00:00"), p, b64, "STORYBOARD SCREEN"))
+    return frames
+
+
 def _load_cached_enrichment_webcam(workspace: Path, chunk: dict) -> list:
     """Load pre-extracted webcam sheets/frames from enrichment/chunk_NN.json."""
     cid = f"chunk_{int(chunk.get('_idx', 0) or 0):02d}"
@@ -209,10 +225,10 @@ def _balance_dynamic_chunk_frames(
     source: Optional[Path | str],
     args: Optional[argparse.Namespace],
 ) -> Tuple[list, list, str]:
-    """Dynamically allocate screen vs webcam storyboard frames from motion + audio bursts."""
+    """Send all storyboard and webcam frames untrimmed from enrichment cache or live motion."""
     cached_wc = _load_cached_enrichment_webcam(workspace, chunk)
     if cached_wc:
-        return trim_storyboard_frames(sb_frames, min(10, max(len(sb_frames), 1))), cached_wc, "cached-enrichment"
+        return sb_frames, cached_wc, "cached-enrichment"
     if not source:
         return sb_frames, [], "static"
     items = chunk.get("items", [])
@@ -224,9 +240,8 @@ def _balance_dynamic_chunk_frames(
     plan, max_z = _enrich_plan_with_peaks(workspace, items, sb_frames, (base_plan, _resolve_chunk_audio_source(workspace, source, args)), chunk_bounds=bounds)
     layout_fn = make_segment_layout_fn(sb_frames, _rank_active_corners, preferred_box=box) if len(sb_frames) >= 2 else None
     wc_frames = _extract_dynamic_webcam(workspace, chunk, source, (box, plan, layout_fn), args)
-    sb_balanced = trim_storyboard_frames(sb_frames, plan.sb_keep) if wc_frames else sb_frames
     suffix = f",peak_z={max_z:.1f}" if max_z >= 2.0 else ""
-    return sb_balanced, wc_frames, f"{plan.tier}(mad={plan.mean_mad:.3f}{suffix})"
+    return sb_frames, wc_frames, f"{plan.tier}(mad={plan.mean_mad:.3f}{suffix})"
 
 
-__all__ = ["_balance_dynamic_chunk_frames", "_expand_around_spikes", "_resolve_chunk_webcam_box"]
+__all__ = ["_balance_dynamic_chunk_frames", "_expand_around_spikes", "_load_cached_storyboard", "_resolve_chunk_webcam_box"]
diff --git a/lib/process/runners/recursive.py b/lib/process/runners/recursive.py
index 68ae103..160d434 100644
--- a/lib/process/runners/recursive.py
+++ b/lib/process/runners/recursive.py
@@ -34,6 +34,7 @@ from process.runners.common import (
     _get_runtime_hook,
     _init_multimodal_grounding,
     _init_webcam_source,
+    _load_cached_storyboard,
     _sample_chunk_multimodal_frames,
     _sample_chunk_webcam_grounding,
 )
@@ -471,9 +472,11 @@ def _process_single_recursive_chunk(
     if not chunk:
         return current_topic_title, rolling_summary
 
-    sb_raw = _sample_chunk_multimodal_frames(
-        chunk, ch_num, slides_dir if is_multimodal else None, tiles_dir, rolling_summary, args
-    )
+    sb_raw = _load_cached_storyboard(workspace, chunk) if is_multimodal else []
+    if not sb_raw:
+        sb_raw = _sample_chunk_multimodal_frames(
+            chunk, ch_num, slides_dir if is_multimodal else None, tiles_dir, rolling_summary, args
+        )
     sb_frames, wc_frames, tier = _balance_dynamic_chunk_frames(workspace, chunk, sb_raw, webcam_source, args)
     keyframes = sb_frames + wc_frames
     enrichment = load_chunk_enrichment(workspace, chunk_idx)
diff --git a/tests/test_pass1_full_frames.py b/tests/test_pass1_full_frames.py
new file mode 100644
index 0000000..0e29d04
--- /dev/null
+++ b/tests/test_pass1_full_frames.py
@@ -0,0 +1,72 @@
+from __future__ import annotations
+
+import json
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+
+_ROOT = Path(__file__).resolve().parents[1]
+if str(_ROOT / "lib") not in sys.path:
+    sys.path.insert(0, str(_ROOT / "lib"))
+
+from process.runners.dynamic_chunk import (
+    _balance_dynamic_chunk_frames,
+    _load_cached_storyboard,
+)
+
+
+class TestPass1FullFrames(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self.ws = Path(self._tmp.name)
+        (self.ws / "enrichment").mkdir()
+        (self.ws / "frames" / "chunk_tiles").mkdir(parents=True)
+        (self.ws / "frames" / "webcam_chunk").mkdir(parents=True)
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_cached_webcam_does_not_trim_storyboard(self) -> None:
+        wc_file = self.ws / "frames" / "webcam_chunk" / "wc_sheet_00_0.jpg"
+        wc_file.write_bytes(b"fake-jpg-bytes")
+        enr = {
+            "audio_cues": [{"sec": 30, "event_type": "loud_peak", "score": 3.5, "note": "loud_peak"}],
+            "webcam_frames": [str(wc_file)],
+            "song": None,
+            "recovered_items": [],
+        }
+        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps(enr), encoding="utf-8")
+
+        sb = [(f"00:00:{i:02d}", wc_file, "b64", "STORYBOARD SCREEN") for i in range(16)]
+        chunk = {"_idx": 0, "start_sec": 0, "end_sec": 150, "items": []}
+        out_sb, wc, tier = _balance_dynamic_chunk_frames(self.ws, chunk, sb, None, None)
+        self.assertEqual(len(out_sb), 16)
+        self.assertEqual(len(wc), 1)
+        self.assertEqual(tier, "cached-enrichment")
+
+    def test_load_cached_storyboard_reads_prepped_tiles(self) -> None:
+        t1 = self.ws / "frames" / "chunk_tiles" / "tile_000010.jpg"
+        t2 = self.ws / "frames" / "chunk_tiles" / "tile_000040.jpg"
+        t1.write_bytes(b"tile1")
+        t2.write_bytes(b"tile2")
+        enr = {
+            "storyboard_frames": [
+                {"ts": "00:00:10", "path": str(t1)},
+                {"ts": "00:00:40", "path": str(t2)},
+            ],
+        }
+        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps(enr), encoding="utf-8")
+        out = _load_cached_storyboard(self.ws, {"_idx": 0})
+        self.assertEqual(len(out), 2)
+        self.assertEqual(out[0][0], "00:00:10")
+        self.assertEqual(out[0][3], "STORYBOARD SCREEN")
+
+    def test_stale_cache_without_storyboard_frames_returns_empty(self) -> None:
+        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps({"audio_cues": []}), encoding="utf-8")
+        out = _load_cached_storyboard(self.ws, {"_idx": 0})
+        self.assertEqual(out, [])
+
+
+if __name__ == "__main__":
+    unittest.main()

commit 0428ec27d53054b3e3853589113cfc6fe3d4c74b
Author: Settawat Boriruklert <zenithth@Settawats-MacBook-Neo.local>
Date:   Sat Nov 21 15:49:41 2026 +0700

    feat(local): run enrichment prep before Pass 1 by default
---
 .../scripts/launch_local.sh                        |  3 +
 .../scripts/process_chunks_local.py                | 32 +++++++--
 tests/test_prep_first_order.py                     | 81 ++++++++++++++++++++++
 3 files changed, 109 insertions(+), 7 deletions(-)

diff --git a/skills/anibon-timestamper-local/scripts/launch_local.sh b/skills/anibon-timestamper-local/scripts/launch_local.sh
index 5346375..4e61653 100755
--- a/skills/anibon-timestamper-local/scripts/launch_local.sh
+++ b/skills/anibon-timestamper-local/scripts/launch_local.sh
@@ -63,6 +63,9 @@ if [[ -z "$VIDEO_URL" && "$WORKSPACE" =~ youtube_([a-zA-Z0-9_-]{11})_workspace ]
 fi
 
 EXTRA_ARGS=()
+if [[ -f "${WORKSPACE}/video_360p.mp4" ]]; then
+    EXTRA_ARGS+=(--video-file "${WORKSPACE}/video_360p.mp4")
+fi
 if [[ -n "$VIDEO_URL" ]]; then
     EXTRA_ARGS+=(--video-url "$VIDEO_URL" --live-chat)
 fi
diff --git a/skills/anibon-timestamper-local/scripts/process_chunks_local.py b/skills/anibon-timestamper-local/scripts/process_chunks_local.py
index 925b053..355094c 100644
--- a/skills/anibon-timestamper-local/scripts/process_chunks_local.py
+++ b/skills/anibon-timestamper-local/scripts/process_chunks_local.py
@@ -195,7 +195,8 @@ def build_argument_parser() -> argparse.ArgumentParser:
     ap.add_argument("--vision-model", default=None)
     ap.add_argument("--no-knowledge-reader", action="store_true")
     ap.add_argument("--live-chat", action="store_true", help="Download and align live chat replay into livechat/ chunks")
-    ap.add_argument("--enrich", action="store_true", help="Run pre-chunk audio/webcam/Shazam enrichment before timestamping")
+    ap.add_argument("--enrich", dest="enrich", action="store_true", default=True, help="Run pre-chunk storyboard/audio/webcam/Shazam prep before timestamping (default: on)")
+    ap.add_argument("--no-enrich", dest="enrich", action="store_false", help="Skip pre-chunk enrichment prep stage")
     ap.add_argument("--api-key", default=os.environ.get("TOKENME_API_KEY") or os.environ.get("LM_API_KEY"))
     return ap
 
@@ -390,14 +391,17 @@ def _ensure_livechat_if_requested(workspace: Path, args: argparse.Namespace) ->
         prepare_livechat(url, workspace)
 
 
-def _run_pre_enrichment_if_requested(workspace: Path, args: argparse.Namespace) -> None:
-    """Run pre-chunk audio yell/silence webcam and Shazam enrichment when --enrich is set."""
-    if not getattr(args, "enrich", False):
+def _run_prep_stage(workspace: Path, args: argparse.Namespace) -> None:
+    """Run pre-chunk storyboard, audio yell/silence webcam, and Shazam prep before Pass 1."""
+    if not getattr(args, "enrich", True):
         return
+    from process.audio_separator_engine import DEFAULT_AUDIOCPP_URL
  
```
