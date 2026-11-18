# Reaction Onset Snapping & Webcam Grounding Implementation Plan (v2 — Empirically Revised)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `anibon-stream-synthesis` to ground reaction timestamps across **all ANIBON livestream genres** (gacha/watchalong, unplanned news/podcast commentary, and action gaming) using per-segment OBS layout detection, cut-boundary splitting, Dual-Box kinematics (`F` Tight Face gating + `W` Full Webcam spikes, room/bed visibility & body-play detection), domain-agnostic co-triggers (Audio RMS envelope + `mood_555.json` / LiveChat bursts + universal Thai emotional cues), and telemetry-injected VLM classification (6 core moods + full-body camera antics / lying on the bed behind the chair + true AFK rejection). Highlight cutting (`creating-highlight-video`) stays out of scope.

**Architecture:** Empirical `/swarm` validation across VOD 1 (`tR9jOZVYSj8`), VOD 2 (`McgRhdbJXlU`), and VOD 3 (`XEOPUvpRw60`) proved the original draft's static top-right tight-face design and single-VOD FGO cue list fail across real streams (`VERDICT.md`). v2 replaces them with clean `< 190`-line modules under `lib/`:
- `lib/video/motion_types.py` (`< 95` lines): immutable `@dataclass` contracts (`FaceBox`, `LayoutSegment`, `FaceMotionSample`, `RegimeThresholds`, `MotionRegime`, `KeyframePick`).
- `lib/video/obs_layout.py` (`< 150` lines): per-segment OBS webcam layout classifier (`top-right`, `mid-right`, `mid-left`, `fullscreen`, `none`) + full-frame layout-cut detector splitting windows around `±1.5s` cut spikes (`z_max = 6.37–39.94` suppression).
- `lib/video/audio_envelope.py` (`< 110` lines): pure-stdlib PCM `s16le` (`ffmpeg`) Audio RMS shout/silence envelope detector (`0.5s` bins) for motionless rants (`boss_heal`) and deadpan breaks.
- `lib/video/face_motion_metrics.py` (`< 185` lines): calibrated `2.0 fps` pure-Python kinematics ported from verified `probe/metrics.py` (`#10` + `#12` patches: `0.45*raw + 0.55*struct` delta, `is_talking_head_baseline`, relaxed real-video `is_sustained_angry`, earliest suprathreshold onset snapping, `15s` local `pre_onset_baseline`, **chair-leave / `posture_act` separation from `stunned_freeze`**, and 4 distinct keyframes with extended settled `+3s..+12s` horizon on large body/bed moves). Zero `subprocess`.
- `lib/video/face_motion.py` (`< 175` lines): Dual-Box `F`+`W` raw RGB extractor (`F = derive_inner_face_box(W)` for calm gating; **full uncropped `W` / full-frame on `fullscreen`** for `shock_burst` spikes, close-to-lens poses, desk props, and full visibility of the **bed behind Boat's chair** in VLM strips).
- `lib/process/reaction_verify.py` (`< 190` lines): Dual-Box + domain-agnostic co-trigger gate (Audio RMS + `mood_555.json`/LiveChat velocity + `multimodal_situations`), telemetry-injected VLM prompt (`stunned_freeze`, `calm_talking`, `playful_tease`, `angry`, `joy_flex`, `shock`, `physical_act`, `empty_chair_afk` guard), protected milestone tags, and `45s` monotonic collision resolver.

**Tech Stack:** Python 3.12+ stdlib (`subprocess`, `statistics`, `dataclasses`, `struct`, `math`), `unittest` (`PYTHONPATH="lib"`), `ffmpeg` (`crop`, `scale`, `fps`, `pcm_s16le`), `yt-dlp` (opt-in remote stream seeking only), OpenAI-compatible Vision API (`call_multimodal`).

**Spec & Empirical Basis:** Updated directly from [VERDICT.md](file:///Users/zenithth/.gemini/antigravity/scratch/theory_proof/VERDICT.md) (`tR9jOZVYSj8` `N=34`, `McgRhdbJXlU` `N=15 + 10m block`, `XEOPUvpRw60` `N=15 + 33×30s sweeps + N=4 VLM`, + `11` layout cuts). Every change in v2 addresses a measured failure mode from those runs.

---

## Empirical Deltas From Draft v1 -> v2 (Must Hold Before Shipping)

1. **No Static `WEBCAM_CORNER` Default & No Unsplit Layout Cuts:** VOD 1 (`76.5%` Mid-Right) and VOD 3 (`Mid-Left 0.000,0.386,0.209,0.212` during gameplay; `Fullscreen` on crash rants) caused naive top-right probing to drop to `7.7%–11.8%` accuracy and `83%–100%` false-positive rate. Unsplit OBS layout cuts spiked `z_max = 6.37–39.94` (`100%` FP). Fix: `WEBCAM_CORNER = "auto"` with `obs_layout.py` per-segment detection + `±1.5s` cut suppression and post-cut `anchor_idx` reset.
2. **Dual-Box (`F` + `W`) Instead of Tight-Face-Only (`F`):** Pure `W` had `100%` calm FP across all 3 VODs; `F` suppressed calm news best (`80%` acc / `11.1%` FP / `80%` fewer VLM calls on VOD 2 10m block) **but** had `< 1.0x` mean SNR gain (`0.824x`, `0.638x`, `0.944x`) and amputated hands-on-head (`crash1_headclutch_fs`) and bowed chins (`ponr_stunned`). Fix: `F` drives `calm_news` gating + talking-head baseline normalization; `W` (or upper-body fullscreen box) drives `shock_burst` onset/spike features (`z_max`) and VLM visual strips.
3. **Telemetry Injection + Thai Valence Calibration in VLM Prompt:** Unassisted 4-frame strips erased freeze duration (`stunned_freeze` `0/8` VLM), turned startle-laughs into `joy_flex` (`7/8` VOD 1 `shock_burst`), and misread sarcastic/hand-cropped `angry` clips (`0/7` VOD 2/3 `angry`). Fix: pass `freeze_duration_sec`, `freeze_drop_ratio`, `webcam_z_max`, `burst_width_sec`, `audio_rms_z`, and transcript context directly into `build_face_reaction_prompt()` with explicit Thai disambiguation rules.
4. **Domain-Agnostic Co-Triggers Instead of `DESIGN_REACTION_CUES`:** Hardcoding FGO Rikyu nouns (`"ไฝ"`, `"ซี่โครง"`, `"มัทฉะ"`, `"พาร์เฟต์"`) cannot generalize to news or action-game livestreams and is **removed completely**. Replaced by: (a) universal Thai emotional/exclamation cues in `multimodal_situations.py`, (b) `ffmpeg` Audio RMS shout/silence envelope (`audio_envelope.py`), and (c) existing LiveChat / `mood_555.json` velocity bursts (`livechat.py`, `parity_gates.py`) so motionless rants (`boss_heal`, `med_vel=0.0121`) and subtle verbal teases (`tease_yellow`) bypass `trigger_vlm=False`.
5. **Earliest Burst Onset Snapping & Pre-Window Padding:** Default `ONSET_SNAP_PRE_SEC = 20` (clamped at segment start / `0`) + `_find_onset_index()` snapping backward to the earliest suprathreshold upward inflection (`z >= 3.5` or `vel/pose` ramp), keeping local `pre_onset_baseline` within `15s` before onset.
6. **Pre-Ship Co-Trigger Ablation Gate Before Enabling by Default:** Keep `REACTION_VERIFY = False` until Task 6 offline + real-clip VOD 1/2/3 co-trigger ablation proves Audio RMS + LiveChat + `EMOTION_REACTION_CUES` recovers motionless rants/teases without regressing calm-news FP (`<= 20%`).
7. **Full-Body Camera Antics, Chair-Leave & Bed-Behind-Chair Visibility (`posture_act`):** Boat often moves beyond his chair's head-box — leaning right into the lens, ducking sideways/below the desk, slumping onto the desk, holding props/drinks/figures to camera, or **getting up to lie down on the bed behind his chair** (dramatic despair, comfy bed-chat, or lounging). Tight face `F` sees an **empty chair** when he leaves the chair: without a guard, `_detect_freeze_plateau` mistakes an empty chair for `stunned_freeze`, and a narrow crop hides him on the bed behind! Fix: keep `fullscreen` uncropped `(0.0, 0.0, 1.0, 1.0)` and always feed full OBS webcam `W` to VLM; detect wide `W` posture/room excursions (`posture_act`) separately from `stunned_freeze`, expand settled `post_peak_state` keyframe horizon to `+3s..+12s`, and distinguish `physical_act` (`lie_on_bed`, `lean_into_cam`, `slump_on_desk`, `duck_under_desk`, `show_prop_to_cam`) from true silent `empty_chair_afk`.

---

## Global Constraints

- Follow Clean Code rules: every new file `< 200` lines, every function `<= 20` lines, `<= 3` arguments per function (group bounds/thresholds into `@dataclass`), zero boolean flag traps.
- Zero external imaging/audio packages (`Pillow`, `numpy`, `cv2`, `mediapipe` are NOT installed in runtime `python3`), and do NOT use `ffmpeg` `drawtext` (not compiled on host `ffmpeg`). Use pure Python stdlib + `ffmpeg` (`crop`, `scale`, `fps`, `s16le`) + `build_multimodal_content` timestamp labels.
- Work on a clean feature/dev branch (`git checkout -b feat/reaction-onset-grounding`) and stage ONLY files touched by this plan — never commit pre-existing modified knowledge/config files (`GEMINI.md`, `resources/*`, `skills/anibon-world-identity/*`, `skills/anibon-timestamper-local/SKILL.md`).
- Preserve backwards-compatible defaults inspected by `skills/anibon-timestamper-local/tests/test_config.py` (e.g. `deduplicate_consecutive_timestamps(..., min_gap_sec=DEDUP_MIN_GAP_SEC)`).
- Never overwrite protected milestone tags (`[Gacha]`, `[Victory]`, `[Boss]`, `[Ending]`, `[Donation]`) when enriching descriptions, and preserve `[News]`/`[Talk]` on general commentary (`calm_talking`) or rants unless genuine sharp reaction onset occurs.
- Never couple or invoke `creating-highlight-video` (`plan_highlight.py` / `cut_highlight.py`).
- Verify with `PYTHONPATH="lib" python3 -m unittest ...` and keep `tests/test_interface.py` and `tests/test_skill_structure.py` passing.

---

### File Structure Map

- **Modify:** `lib/common/config.py:198-267` — add `REACTION_MIN_GAP_SEC`, `ONSET_SNAP_PRE_SEC`, `ONSET_SNAP_POST_SEC`, `FACE_MOTION_THRESHOLD`, `FACE_SPIKE_RATIO`, `FACE_POSE_THRESHOLD`, `FACE_MAX_FRAMES`, `WEBCAM_CORNER` (`"auto"`), `AUDIO_RMS_Z_THRESHOLD`, `REACTION_VERIFY` (`False`) + `reload_config()`.
- **Modify:** `lib/process/multimodal_situations.py:1-58` — add domain-agnostic `EMOTION_REACTION_CUES` (universal Thai shock/profanity/hype/laughter markers, zero game-specific nouns), append to `STRONG_VISUAL_CUES`, register `(EMOTION_REACTION_CUES, 2.0)` in `_WEIGHTED_GROUPS`.
- **Modify:** `lib/common/timestamps.py:99-103,225-248` — preserve distinct `[Reaction]` transitions `>= REACTION_MIN_GAP_SEC` (`45s`) when text keyword overlap is low.
- **Modify:** `lib/process/prompts.py:448-470,628-649` — add `REACTION VISUAL ONSET` directive covering all 6 behavioral states without FGO-specific assumptions.
- **Create:** `lib/video/motion_types.py` (`< 95` lines) — `FaceBox`, `LayoutSegment`, `WindowBounds`, `FaceMotionSample`, `RegimeThresholds`, `MotionRegime`, `KeyframePick`.
- **Create:** `lib/video/auto_tracker.py` (`< 125` lines) — `track_webcam_any_position()` spatial-grid temporal activity + contrast tracker that locates an active webcam/face bounding box at ANY arbitrary `(x, y, w, h)` position when fixed presets fail.
- **Create:** `lib/video/obs_layout.py` (`< 165` lines) — `detect_obs_layout()` (**check fixed position(s) first; if fixed check cannot track an active face, call `track_webcam_any_position()`**, else `"none"`), `detect_layout_cuts()`, `resolve_webcam_and_face_boxes()`.
- **Create:** `lib/video/audio_envelope.py` (`< 110` lines) — `AudioBurstMetrics`, `compute_audio_envelope_from_pcm()`, `extract_audio_burst_metrics()`.
- **Create:** `lib/video/face_motion_metrics.py` (`< 185` lines) — `compute_frame_delta()`, `score_motion_series()`, `classify_motion_regime()`, `select_dynamic_keyframes()` (`2.0 fps` calibrated, zero subprocess).
- **Create:** `lib/video/face_motion.py` (`< 175` lines) — Dual-Box `F`+`W` extractor (`extract_dual_motion_series()`, `extract_face_frames_by_secs()`).
- **Create:** `lib/process/reaction_verify.py` (`< 190` lines) — `ReactionVerifyResult`, `CoTriggerSignals`, `needs_reaction_verify()`, `collect_co_triggers()`, `build_face_reaction_prompt()`, `parse_snapped_response()`, `resolve_monotonic_snap()`, `verify_reaction_stamps()`, `apply_reaction_verify()`.
- **Modify:** `lib/process/assembly.py:24,72-87` — wire `apply_reaction_verify()` **after** `prune_essential()` (cost-bounded to surviving 40–60 stamps) and sync snapped lines back into `all_timestamps.txt`.
- **Modify:** `lib/process/__init__.py` & `lib/interface.py` — export `apply_reaction_verify`.
- **Modify:** `skills/anibon-timestamper-local/scripts/process_chunks_local.py:166-178` — add `--reaction-verify`, `--webcam-corner` (choices: `auto`, `top-right`, `mid-right`, `mid-left`, `bottom-right`, `bottom-left`, `top-left`, `fullscreen`, `none`), `--face-threshold`, `--remote-snap`.
- **Create Tests & Fixtures:**
  - `skills/anibon-timestamper-local/tests/test_obs_layout.py`
  - `skills/anibon-timestamper-local/tests/test_audio_envelope.py`
  - `skills/anibon-timestamper-local/tests/test_face_motion.py`
  - `skills/anibon-timestamper-local/tests/test_reaction_verify.py`
  - `skills/anibon-timestamper-local/tests/test_reaction_gold_benchmark.py`
  - `skills/anibon-timestamper-local/tests/fixtures/cross_vod_reaction_gold.json` (VOD 1 `tR9jOZVYSj8` anchors + VOD 2 `McgRhdbJXlU` + VOD 3 `XEOPUvpRw60` calibration metadata)
- **Modify Tests:** `test_config.py`, `test_multimodal.py`, `test_timestamps.py`, `test_prompts.py`.

---

### Task 1: Domain-Agnostic Thai Emotion Cues & Calibrated Config Defaults

**Files:**
- Modify: `lib/common/config.py:198-267`
- Modify: `lib/process/multimodal_situations.py:1-58`
- Test: `skills/anibon-timestamper-local/tests/test_config.py`
- Test: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Consumes: `common.config.cfg_int`, `cfg_float`, `cfg_bool`, `cfg_str`
- Produces:
  - `lib/common/config`: `REACTION_MIN_GAP_SEC: int = 45`, `ONSET_SNAP_PRE_SEC: int = 20`, `ONSET_SNAP_POST_SEC: int = 35`, `FACE_MOTION_THRESHOLD: float = 0.060`, `FACE_SPIKE_RATIO: float = 2.2`, `FACE_POSE_THRESHOLD: float = 0.075`, `FACE_MAX_FRAMES: int = 4`, `WEBCAM_CORNER: str = "auto"`, `AUDIO_RMS_Z_THRESHOLD: float = 2.5`, `REACTION_VERIFY: bool = False`
  - `lib/process/multimodal_situations`: `EMOTION_REACTION_CUES: Tuple[str, ...]` (universal Thai exclamation/shock/anger/hype markers usable across FGO, news, anime, and action games — **no** FGO-specific character/item nouns) included in `STRONG_VISUAL_CUES` and `_WEIGHTED_GROUPS` (`weight = 2.0`).

- [ ] **Step 1: Write the failing tests in `test_config.py` and `test_multimodal.py`**

```python
# In skills/anibon-timestamper-local/tests/test_config.py (new test method):
    def test_reaction_grounding_config_defaults(self):
        from common import config
        self.assertEqual(config.REACTION_MIN_GAP_SEC, 45)
        self.assertEqual(config.ONSET_SNAP_PRE_SEC, 20)
        self.assertEqual(config.ONSET_SNAP_POST_SEC, 35)
        self.assertAlmostEqual(config.FACE_MOTION_THRESHOLD, 0.060)
        self.assertAlmostEqual(config.FACE_SPIKE_RATIO, 2.2)
        self.assertAlmostEqual(config.FACE_POSE_THRESHOLD, 0.075)
        self.assertEqual(config.FACE_MAX_FRAMES, 4)
        self.assertEqual(config.WEBCAM_CORNER, "auto")
        self.assertAlmostEqual(config.AUDIO_RMS_Z_THRESHOLD, 2.5)
        self.assertFalse(config.REACTION_VERIFY)

# In skills/anibon-timestamper-local/tests/test_multimodal.py (new test method):
    def test_score_item_situations_detects_domain_agnostic_emotion_cues(self):
        from process.multimodal_situations import EMOTION_REACTION_CUES, score_item_situations
        self.assertGreaterEqual(score_item_situations("เห้ย เชี่ย อะไรวะเนี่ย แคชอีกแล้ว"), 2.0)
        self.assertGreaterEqual(score_item_situations("โอ้โห โคตรโหด ขนลุกเลย"), 2.0)
        self.assertGreaterEqual(score_item_situations("เอาจริงดิ แม่งออกแบบบอสพังจัด"), 2.0)
        self.assertEqual(score_item_situations("วันนี้อากาศดีครับ รายงานข่าวต่อ"), 0.0)
        # Ensure single-VOD FGO design nouns are never reintroduced
        for banned in ("ไฝ", "ซี่โครง", "พาร์เฟต์", "มัทฉะ"):
            self.assertNotIn(banned, EMOTION_REACTION_CUES)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py skills/anibon-timestamper-local/tests/test_multimodal.py`
Expected: FAIL with missing `REACTION_MIN_GAP_SEC` and `EMOTION_REACTION_CUES`.

- [ ] **Step 3: Implement config defaults in `lib/common/config.py` and `EMOTION_REACTION_CUES` in `lib/process/multimodal_situations.py`**

- In `lib/common/config.py`: add module constants and `reload_config()` bindings using `cfg_int` / `cfg_float` / `cfg_str` / `cfg_bool`.
- In `lib/process/multimodal_situations.py`: add `EMOTION_REACTION_CUES` (`"เห้ย"`, `"เชี่ย"`, `"แม่ง"`, `"ว้าว"`, `"โอ้โห"`, `"ห๊ะ"`, `"ตกใจ"`, `"ขนลุก"`, `"ขิง"`, `"เกลือ"`, `"เอาจริงดิ"`, `"โคตรโหด"`, `"หัวร้อน"`, `"เดือดจัด"`, `"ฟิวส์ขาด"`, `"บ้าไปแล้ว"`, `"พัง"`, `"บัค"`), append to `STRONG_VISUAL_CUES`, and insert `(EMOTION_REACTION_CUES, 2.0)` into `_WEIGHTED_GROUPS`. Note: check line count `< 160`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py skills/anibon-timestamper-local/tests/test_multimodal.py`
Expected: PASS (`OK`).

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/reaction-onset-grounding
git add lib/common/config.py lib/process/multimodal_situations.py \
  skills/anibon-timestamper-local/tests/test_config.py \
  skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "feat: add calibrated reaction config and domain-agnostic emotion cues"
```

---

### Task 2: Rapid Distinct `[Reaction]` Preservation & Generic Visual Onset Prompting

**Files:**
- Modify: `lib/common/timestamps.py:99-103,227-246`
- Modify: `lib/process/prompts.py:448-470,628-649`
- Test: `skills/anibon-timestamper-local/tests/test_timestamps.py`
- Test: `skills/anibon-timestamper-local/tests/test_prompts.py`

**Interfaces:**
- Consumes: `common.config.STAMP_COLLISION_SEC`, `REACTION_MIN_GAP_SEC`, existing `deduplicate_consecutive_timestamps(stamps, min_gap_sec=DEDUP_MIN_GAP_SEC, ...)` signature
- Produces: Updated `parse_timestamps()` and `deduplicate_consecutive_timestamps()` preserving consecutive distinct `[Reaction]` beats spaced `>= REACTION_MIN_GAP_SEC` (`45s`) when keyword overlap is low; updated prompt directives in `build_recursive_prompt()` and `build_group_prompt()`.

- [ ] **Step 1: Write the failing tests in `test_timestamps.py` and `test_prompts.py`**

```python
# In skills/anibon-timestamper-local/tests/test_timestamps.py:
    def test_rapid_distinct_reactions_preserved_above_collision_floor(self):
        stamps = [
            "03:36:15 - [Reaction] อึ้งหลังซูมดูรายละเอียดตัวละครใหม่แบบใกล้ชิด",
            "03:37:24 - [Reaction] ตบมือกุมหัวร้องลั่นหลังเปิดภาพร่างสุดท้ายจนโดเนทเด้ง",
            "03:44:23 - [Reaction] หัวเราะลั่นท่าลอยตัวกลางอากาศของร่างหนึ่ง",
            "03:45:34 - [Reaction] ตาโตเห็นตุ๊กตาจิ๋วกับเอฟเฟกต์น้ำแข็งไสสุดล้ำ",
        ]
        deduped = deduplicate_consecutive_timestamps(stamps, min_gap_sec=120, max_dedup_gap_sec=600)
        self.assertEqual(len(deduped), 4)

    def test_duplicate_banter_reactions_within_150s_still_collapsed(self):
        stamps = [
            "01:10:00 - [Reaction] ขำมุกแชทเรื่องกาชาเกลือมาก",
            "01:11:40 - [Reaction] ขำมุกแชทเรื่องกาชาเกลือซ้ำ",
        ]
        deduped = deduplicate_consecutive_timestamps(stamps, min_gap_sec=120, max_dedup_gap_sec=600)
        self.assertEqual(len(deduped), 1)

    def test_parse_timestamps_allows_45s_reaction_separation(self):
        raw = (
            "04:43:30 - [Gameplay] ฟาร์มเควสต์ฟรีเตรียมปลดล็อกตัวละคร\n"
            "04:44:24 - [Reaction] เหลียวขำแชทขอสกินร่างสามหลังเห็นชุดใหม่\n"
        )
        parsed = parse_timestamps(raw, max_stamps=4)
        self.assertEqual(len(parsed), 2)

# In skills/anibon-timestamper-local/tests/test_prompts.py:
    def test_prompts_instruct_splitting_distinct_reaction_onsets(self):
        chunk = {"_idx": 1, "items": [{"timestamp": "03:04:10", "start": 11050.0, "text": "test"}]}
        rec = build_recursive_prompt(chunk=chunk, current_topic="Gaming", rolling_summary="ok")
        grp = build_group_prompt(chunks=[chunk], group_idx=0, prev_tail="")
        self.assertIn("REACTION VISUAL ONSET", rec)
        self.assertIn("REACTION VISUAL ONSET", grp)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_timestamps.py skills/anibon-timestamper-local/tests/test_prompts.py`
Expected: FAIL (`len(deduped) == 2`, `len(parsed) == 1`, missing `"REACTION VISUAL ONSET"`).

- [ ] **Step 3: Implement reaction preservation in `lib/common/timestamps.py` and prompt rule in `lib/process/prompts.py`**

- In `lib/common/timestamps.py`:
  - Import `REACTION_MIN_GAP_SEC` from `common.config`.
  - In `parse_timestamps()`: extract `_collision_threshold(line: str) -> int` returning `REACTION_MIN_GAP_SEC` (`45`) when `"[Reaction]"` is in `line`, else `60`.
  - In `deduplicate_consecutive_timestamps()`: extract `_should_keep_distinct_reaction(prev_kw: set, curr_stamp: str, gap: int, common_kw: set) -> bool`: return `True` when `"[Reaction]"` in `curr_stamp` and `gap >= REACTION_MIN_GAP_SEC` and `not (len(common_kw) >= 4 or (len(prev_kw) >= 2 and len(common_kw) / len(prev_kw) >= 0.65))`; update lines `228–230` and `239–245` cleanly.
- In `lib/process/prompts.py`:
  - Add a compact, genre-neutral `REACTION VISUAL ONSET` bullet to both `build_recursive_prompt()` (`lines 448–462`) and `build_group_prompt()` (`lines 628–644`): keep separate `[Reaction]` lines when distinct reveals, crashes, physical camera gags (e.g., leaning into camera, slumping on desk, showing items, or getting up to lie on the bed behind the chair), or emotional swings occur even 45–120s apart; anchor `HH:MM:SS` to initial reaction/reveal onset; match genuine anger (`หัวร้อน`/`เดือดจัด`/`สับแหลก`) vs stunned silence (`ชะงักนิ่ง`) vs playful camera/bed acting (`แซว`/`ขำ`/`เล่นกล้อง`/`ลงไปนอนเตียง`).

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_timestamps.py skills/anibon-timestamper-local/tests/test_prompts.py skills/anibon-timestamper-local/tests/test_config.py`
Expected: PASS (`OK`).

- [ ] **Step 5: Commit**

```bash
git add lib/common/timestamps.py lib/process/prompts.py \
  skills/anibon-timestamper-local/tests/test_timestamps.py \
  skills/anibon-timestamper-local/tests/test_prompts.py
git commit -m "feat: preserve distinct rapid reaction timestamps and genre-neutral onset prompt"
```

---

### Task 3: OBS Layout Detection, Cut Splitting, Dual-Box Kinematics & Audio RMS Envelope (`lib/video/`)

**Files:**
- Create: `lib/video/motion_types.py` (`< 95` lines — shared dataclasses & box presets)
- Create: `lib/video/obs_layout.py` (`< 150` lines — per-segment OBS corner/fullscreen detection + full-frame layout cut splitter)
- Create: `lib/video/audio_envelope.py` (`< 110` lines — pure-stdlib PCM `s16le` RMS envelope + silence drop metrics)
- Create: `lib/video/face_motion_metrics.py` (`< 185` lines — calibrated `2.0 fps` Dual-Box kinematics + `#10`/`#12` regime classifier + 4-keyframe selector, zero `subprocess`)
- Create: `lib/video/face_motion.py` (`< 175` lines — Dual-Box `F`+`W` extractor + 256x256 VLM strip frame exporter)
- Test: `skills/anibon-timestamper-local/tests/test_obs_layout.py`
- Test: `skills/anibon-timestamper-local/tests/test_audio_envelope.py`
- Test: `skills/anibon-timestamper-local/tests/test_face_motion.py`

**Interfaces:**
- Produces in `lib/video/motion_types`:
  - `@dataclass(frozen=True) class FaceBox`: `x: float`, `y: float`, `w: float`, `h: float`, method `derive_tight_face() -> FaceBox` (maps full webcam box `W` -> inner head/face box `F` per verified `probe/boxes.py:derive_inner_face_box`)
  - `WEBCAM_BOX_PRESETS: Dict[str, Optional[FaceBox]]`: `"top-right"` `(0.76, 0.00, 0.24, 0.30)`, `"mid-right"` `(0.75, 0.33, 0.25, 0.32)`, `"mid-left"` `(0.00, 0.38, 0.22, 0.24)`, `"bottom-right"`, `"bottom-left"`, `"top-left"`, `"fullscreen"` `(0.00, 0.00, 1.00, 1.00)` (full uncropped room frame so sideways movement & bed behind chair stay visible), `"none"`
  - `@dataclass(frozen=True) class LayoutSegment`: `layout: str`, `webcam_box: Optional[FaceBox]`, `face_box: Optional[FaceBox]`, `cut_secs: Tuple[float, ...]`
  - `@dataclass(frozen=True) class RegimeThresholds`: ported verbatim from verified `probe/metrics.py:22-36` (`motion_threshold=0.060`, `spike_ratio=2.2`, `pose_threshold=0.075`, `freeze_vel_ceiling=0.016`, `freeze_pose_floor=0.038`, `min_freeze_sec=2.0`, `angry_mean_vel=0.055`, `angry_rms_vel=0.068`, `angry_duty_cycle=0.42`, `joy_post_vel_floor=0.020`, `joy_post_pose_floor=0.055`, plus `posture_w_pose_floor=0.14`, `posture_w_peak_floor=0.12`)
  - `@dataclass(frozen=True) class FaceMotionSample`, `@dataclass(frozen=True) class KeyframePick`, `@dataclass(frozen=True) class MotionRegime` (regimes: `"calm_news" | "stunned_freeze" | "playful_tease" | "angry" | "joy_flex" | "shock_burst" | "posture_act"`)
- Produces in `lib/video/obs_layout`:
  - `detect_layout_cuts(full_frames: List[bytes], fps: float = 2.0, cut_mad_floor: float = 0.22) -> List[int]` (indices where global frame structure jumps — hard-suppresses `±1.5s` around cuts and selects largest clean contiguous sub-segment)
  - `detect_obs_layout(source: Path | str, bounds: WindowBounds, preferred: str = "auto") -> LayoutSegment` (scores edge/corner motion vs background/static UI regions across sparse probe frames, or honors explicit manual preset when `preferred != "auto"`)
- Produces in `lib/video/audio_envelope`:
  - `@dataclass(frozen=True) class AudioBurstMetrics`: `rms_z_max: float`, `shout_sec: Optional[float]`, `silence_drop_sec: Optional[float]`, `has_audio_trigger: bool`
  - `compute_audio_envelope_from_pcm(pcm_s16le: bytes, sample_rate: int = 8000, bin_sec: float = 0.5) -> AudioBurstMetrics`
  - `extract_audio_burst_metrics(source: Path | str, bounds: WindowBounds, z_thresh: float = 2.5) -> AudioBurstMetrics`
- Produces in `lib/video/face_motion_metrics`:
  - `compute_frame_delta(frame_a: bytes, frame_b: bytes) -> Tuple[float, float, float, float, float]` (`0.45 * raw_mad + 0.55 * struct_mad` lighting-compensated delta)
  - `score_motion_series(frames: List[bytes], fps: float = 2.0, abs_offset_sec: float = 0.0) -> Tuple[List[FaceMotionSample], int]`
  - `classify_dual_regime(face_samples: List[FaceMotionSample], webcam_samples: List[FaceMotionSample], thresholds: Optional[RegimeThresholds] = None, fps: float = 2.0) -> MotionRegime`:
    - Uses **`F` (`face_samples`)** for talking-head baseline detection (`is_talking_head_baseline`) and primary `calm_news` gating.
    - Uses **`W` (`webcam_samples`)** `z_max`, `spike_ratio`, and earliest suprathreshold burst inflection (`_find_onset_index`) for `shock_burst` capture (`webcam_z_max >= 4.0` or `shock_sc >= 0.70`), **plus** `W`-vs-`F` room/chair-departure detection (`posture_act` when `W` has large body excursion `w_peak_vel >= 0.12` / sustained `w_pose_shift >= 0.14` — e.g. standing up to lie on the bed behind the chair, leaning into lens, or ducking — guarding `_detect_freeze_plateau` so an vacated empty chair is NOT mislabeled `stunned_freeze`).
    - Always returns 4 distinct `KeyframePick`s (`pre_onset_baseline` within `15s` before onset, `onset_inflection`, `peak_delta`, `post_peak_state`); for `posture_act` (`w_pose_shift >= 0.14`), searches `post_peak_state` over **`+2.5s..+12.0s`** picking the lowest-velocity settled hold frame so Boat lying on the bed / holding a camera pose is captured clearly after walking back, and always exports full uncropped `W` JPEGs for VLM.

- [ ] **Step 1: Write failing unit tests for layout cuts, audio envelope, and calibrated Dual-Box kinematics**

```python
# tests/test_obs_layout.py:
#   - Full-frame OBS layout cut mid-window splits cleanly & excludes +-1.5s cut indices from fake z_max spikes
#   - Corner preset + derive_tight_face() keeps top/right/left alignment inside normalized [0..1]; fullscreen keeps full (0,0,1,1) room view
# tests/test_audio_envelope.py:
#   - Pure-stdlib PCM s16le fixtures: quiet baseline -> sudden shout bin yields rms_z_max >= 2.5 & has_audio_trigger=True
#   - Steady speech yields has_audio_trigger=False
#   - Sudden silence drop after speech captures silence_drop_sec
# tests/test_face_motion.py (at fps=2.0):
#   - calm_news conversational talking on F suppresses VLM (trigger_vlm=False) even if W has minor fidgets
#   - stunned_freeze holds >= 2.0s after pre_peak/pose_jump trigger -> selects 4 distinct keyframes with local 15s anchor
#   - chair_vacated / bed_retreat: large W excursion + static empty-chair plateau in F routes to posture_act (NOT stunned_freeze!) and picks settled post_peak_state frame at +5s..+12s
#   - sustained angry (mean_vel >= 0.055 OR alternate peak_vel >= 0.250 + rms_step_vel >= 0.058 path) -> triggers angry
#   - shock_burst detected from W spike even when F slightly damped; earliest suprathreshold onset_sec precedes global peak
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_obs_layout.py skills/anibon-timestamper-local/tests/test_audio_envelope.py skills/anibon-timestamper-local/tests/test_face_motion.py`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `motion_types.py`, `obs_layout.py`, `audio_envelope.py`, `face_motion_metrics.py`, `face_motion.py`**

Enforce Clean Code rules strictly (`< 190` lines/file, `<= 20` lines/fn, `<= 3` args). Port all verified formulas from `/Users/zenithth/.gemini/antigravity/scratch/theory_proof/probe/metrics.py` cleanly into helper functions (`_detect_freeze_plateau`, `_count_oscillations`, `_find_onset_index`, `_score_regimes`, `select_dynamic_keyframes`), keeping dual `F`+`W` fusion clean so `extract_dual_motion_series()` pipes both crops (or full-frame check + dual crop) via `ffmpeg` at `2.0 fps`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_obs_layout.py skills/anibon-timestamper-local/tests/test_audio_envelope.py skills/anibon-timestamper-local/tests/test_face_motion.py`
Expected: PASS (`OK`).

- [ ] **Step 5: Commit**

```bash
git add lib/video/motion_types.py lib/video/obs_layout.py lib/video/audio_envelope.py \
  lib/video/face_motion_metrics.py lib/video/face_motion.py \
  skills/anibon-timestamper-local/tests/test_obs_layout.py \
  skills/anibon-timestamper-local/tests/test_audio_envelope.py \
  skills/anibon-timestamper-local/tests/test_face_motion.py
git commit -m "feat: add OBS layout cut splitting, audio RMS envelope, and 2fps Dual-Box kinematics"
```

---

### Task 4: Telemetry-Injected Multi-Regime VLM Prompt, Body/Bed-Pose Guard & Resolver (`lib/process/reaction_verify.py`)

**Files:**
- Create: `lib/process/reaction_verify.py` (`< 190` lines across Tasks 4–5 — extract pure prompt/parse helpers if nearing cap)
- Test: `skills/anibon-timestamper-local/tests/test_reaction_verify.py`

**Interfaces:**
- Consumes: `common.time.fmt_ts`, `common.config.STAMP_COLLISION_SEC`, `ONSET_SNAP_PRE_SEC`, `ONSET_SNAP_POST_SEC`, `process.multimodal_situations.score_item_situations`, `process.vision_verify.stamp_seconds`, `video.motion_types` (`MotionRegime`, `WindowBounds`), `video.audio_envelope.AudioBurstMetrics`
- Produces:
  - `@dataclass(frozen=True) class CoTriggerSignals`: `situation_score: float`, `chat_verdict: str`, `chat_peak_in_window: bool`, `audio: Optional[AudioBurstMetrics]` (`has_any` property -> `True` when `situation_score >= 2.0` OR `chat_verdict == "MEME_PULSE" and chat_peak_in_window` OR `(audio and audio.has_audio_trigger)`)
  - `@dataclass(frozen=True) class ReactionVerifyResult`: `original: str`, `updated: str`, `snapped_sec: int`, `emotion_class: str`, `face_cue: str`, `peak_motion: float`, `confidence: float`, `accepted: bool`
  - `needs_reaction_verify(stamp: str, transcript_ctx: str = "", triggers: Optional[CoTriggerSignals] = None) -> bool`
  - `build_face_reaction_prompt(stamp: str, regime: MotionRegime, triggers: Optional[CoTriggerSignals] = None, transcript_ctx: str = "") -> str`
  - `parse_snapped_response(raw: str, original: str, bounds: Tuple[int, int], min_conf: float = 0.6) -> ReactionVerifyResult`
  - `resolve_monotonic_snap(results: List[ReactionVerifyResult], collision_sec: int = STAMP_COLLISION_SEC) -> List[str]`

- [ ] **Step 1: Write the failing tests covering telemetry injection, all 6 core moods + body/bed poses & tag locks**

- Verify `build_face_reaction_prompt()` explicitly includes:
  - Image 1 `[pre_onset_baseline]` timestamp within `15s`, plus dynamic keyframes showing full webcam scene (`W` including bed/background behind chair)
  - Explicit kinematic telemetry lines (`regime=`, `freeze_duration_sec=`, `freeze_drop_ratio=`, `webcam_z_max=`, `w_pose_shift=`, `burst_width_sec=`, `audio_rms_z=`)
  - Explicit Thai VLM calibration warnings:
    1. Startle-laugh / recoil (`shock` vs `joy_flex` when `webcam_z_max >= 5.0` & narrow burst)
    2. `stunned_freeze` when `freeze_duration_sec >= 2.0` & `freeze_drop_ratio >= 2.0` (do NOT confuse with silent news/PV watching OR an empty chair!)
    3. Deadpan/sarcastic `angry` (`angry` vs `playful_tease`/`calm_talking` when audio shout/swearing present)
    4. **`physical_act` / off-chair body & bed poses vs `empty_chair_afk`**: instruct VLM to inspect BOTH the foreground chair AND the bed/background behind the chair:
       - Camera/desk poses (`lean_into_cam`, `duck_under_desk`, `slump_on_desk`, `show_prop_to_cam`, `praying_bow`)
       - **`lie_on_bed`** (ลุก/ถอยไปนอนแผ่บนเตียงข้างหลังเก้าอี้เพื่อเล่นมุก/หมดแรง/นอนคุย — keep truthful Thai description, `accepted=True`, never hallucinate stunned freeze on empty chair)
       - **`empty_chair_afk`** (เก้าอี้ว่างและไม่มีคนบนเตียง + ไม่มีแอ็กชันเล่นกล้อง — reject `accepted=False`, never fabricate `[Reaction]`)
- Verify `needs_reaction_verify()` protects quiet `[News]` stamps while allowing `CoTriggerSignals.has_any` (`MEME_PULSE`, `audio.has_audio_trigger`, or `situation_score >= 2.0`) to bypass suppression on motionless rants (`boss_heal`) and subtle verbal teases (`tease_yellow`).
- Verify `PROTECTED_MILESTONE_TAGS` (`"Gacha"`, `"Victory"`, `"Boss"`, `"Ending"`, `"Donation"`) never downgrade to `Reaction`; both `calm_talking` and `empty_chair_afk` return `accepted=False`; `physical_act` (`lie_on_bed`, `lean_into_cam`) accepts cleanly while preserving `[Talk]`/`[Reaction]` rules; bounds clamp rejects drift; `resolve_monotonic_snap()` prevents `< 45s` collisions.

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_reaction_verify.py`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement pure prompt, co-trigger predicate, parser, and resolver in `lib/process/reaction_verify.py`**

Keep file well under `< 200` lines (`<= 20` lines per helper). If Tasks 4 + 5 together exceed ~175 lines, keep prompt/parsing cleanly in `lib/process/reaction_prompt.py` (`< 120` lines) and orchestration in `lib/process/reaction_verify.py` (`< 160` lines).

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_reaction_verify.py`
Expected: PASS (`OK`).

- [ ] **Step 5: Commit**

```bash
git add lib/process/reaction_verify.py skills/anibon-timestamper-local/tests/test_reaction_verify.py
git commit -m "feat: add telemetry-injected 6-mood reaction prompt and co-trigger resolver"
```

---

### Task 5: Dual-Box Co-Triggered Orchestration, CLI Flags & Raw Timestamp Sync

**Files:**
- Modify: `lib/process/reaction_verify.py` (add `collect_co_triggers`, `verify_reaction_stamps`, `apply_reaction_verify`)
- Modify: `lib/process/assembly.py:24,72-87`
- Modify: `lib/process/__init__.py` & `lib/interface.py` (export `apply_reaction_verify`)
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:166-178`
- Test: `skills/anibon-timestamper-local/tests/test_reaction_verify.py`
- Test: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Consumes: `download.ytdlp` stream URL helper (when `--remote-snap`), `video.obs_layout`, `video.audio_envelope`, `video.face_motion`, `video.face_motion_metrics`, `workspace / "mood_555.json"` (`parity_gates`), `process.multimodal.build_multimodal_content`, `call_multimodal`, `common.lmstudio.resolve_endpoint`
- Produces:
  - `collect_co_triggers(workspace, sec, transcript_ctx, source, audio_fn=...) -> CoTriggerSignals` (reads existing `mood_555.json` peak windows + optional Audio RMS envelope + `score_item_situations`)
  - `verify_reaction_stamps(stamps, workspace, source, endpoint, model, ...) -> List[str]`:
    - Runs `detect_obs_layout()` -> splits at layout cuts (`±1.5s` suppression) -> computes Dual-Box `F`+`W` kinematics -> bypasses `trigger_vlm=False` ONLY if `CoTriggerSignals.has_any` (e.g. `audio.has_audio_trigger` on `boss_heal` or `MEME_PULSE` on `tease_yellow`) -> exports **`W` (wider upper-body webcam crop)** frames at `[pre_onset_baseline, onset_inflection, peak_delta, post_peak_state]` -> caches in `workspace / "reaction_verify_log.json"`.
  - Updated `_prune_and_verify_timestamps()` in `lib/process/assembly.py` running `apply_reaction_verify` **after** `prune_essential()` and syncing `{orig: updated}` lines back into `all_timestamps.txt`.
  - CLI flags in `process_chunks_local.py`: `--reaction-verify`, `--webcam-corner`, `--face-threshold`, `--remote-snap`.

- [ ] **Step 1: Write failing tests for Dual-Box + Co-Trigger orchestration & CLI flags**

- Test `apply_reaction_verify` noop when `reaction_verify=False`.
- Test `verify_reaction_stamps`:
  1. Drops `calm_news` when both `trigger_vlm=False` AND `not co_triggers.has_any` (0 VLM calls).
  2. Bypasses `calm_news` gate when `audio.has_audio_trigger=True` OR `mood_555.json` reports `MEME_PULSE` in window -> invokes `call_fn` once with wider `W` frames and updates description accurately.
  3. Processes `stunned_freeze` & `shock_burst`, snaps timestamp monotonically, writes `reaction_verify_log.json`, and hits cache (`0` repeat `call_fn` calls on second invocation).
- Test `process_chunks_local.py --help` asserts `--reaction-verify`, `--webcam-corner`, `--face-threshold`, `--remote-snap`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_reaction_verify.py skills/anibon-timestamper-local/tests/test_config.py`
Expected: FAIL.

- [ ] **Step 3: Implement orchestration, `assembly.py` wiring, `interface.py` exports, and CLI flags**

- Ensure `apply_reaction_verify` returns `stamps` unchanged if `video_file` missing (`graceful degradation`).
- Sync `{orig: updated}` mappings into `workspace / "all_timestamps.txt"` cleanly whenever any line changed.

- [ ] **Step 4: Run unit, interface, and skill-structure tests**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_reaction_verify.py skills/anibon-timestamper-local/tests/test_config.py tests/test_interface.py tests/test_skill_structure.py`
Expected: PASS (`OK`).

- [ ] **Step 5: Commit**

```bash
git add lib/process/reaction_verify.py lib/process/assembly.py \
  lib/process/__init__.py lib/interface.py \
  skills/anibon-timestamper-local/scripts/process_chunks_local.py \
  skills/anibon-timestamper-local/tests/test_reaction_verify.py \
  skills/anibon-timestamper-local/tests/test_config.py
git commit -m "feat: wire Dual-Box co-triggered --reaction-verify CLI and raw sync"
```

---

### Task 6: Cross-VOD Benchmark & Pre-Ship Co-Trigger Calibration (`VOD 1 + VOD 2 + VOD 3`)

**Files:**
- Create: `skills/anibon-timestamper-local/tests/fixtures/cross_vod_reaction_gold.json`
- Create: `skills/anibon-timestamper-local/tests/test_reaction_gold_benchmark.py`

**Interfaces:**
- Consumes: `common.timestamps.deduplicate_consecutive_timestamps`, `process.multimodal_situations.score_item_situations`, `video.obs_layout`, `video.audio_envelope`, `video.face_motion`, `video.face_motion_metrics`, `process.reaction_verify`
- Produces:
  1. **Deterministic offline regression suite (zero network, runs in CI):**
     - Rapid distinct `[Reaction]` preservation (`>= 45s`, low text overlap) vs duplicate banter collapse (`< 150s`, high overlap).
     - OBS layout-cut spike suppression (`z_max` reset across cut boundaries).
     - Protected tag invariance (`[Gacha]`, `[Victory]`, `[Boss]`, `[News]`) + `45s` monotonic snap bounds.
     - Chair-leave / bed-behind-chair & full-body camera-play invariants (`posture_act` settled keyframe `+3s..+12s`, `physical_act` / `lie_on_bed` acceptance vs `empty_chair_afk` rejection, zero empty-chair false `stunned_freeze`).
     - Audio RMS shout + `mood_555.json` `MEME_PULSE` co-trigger recovery when facial `med_vel` is flat (`boss_heal` motionless rant simulation).
  2. **Optional real-clip cross-VOD calibration harness (`@unittest.skipUnless` local `/Users/zenithth/.gemini/antigravity/scratch/theory_proof/` clips present):**
     - Tests real clips across all 3 contrasting VODs (`VOD 1` `b04`/`c05` `tR9jOZVYSj8`, `VOD 2` `angry_lanterns`/`calm_sso`/`10m block` `McgRhdbJXlU`, `VOD 3` `crash10_core_rant`/`ponr_stunned`/`boss_heal`/`cuts` `XEOPUvpRw60`).
     - Acceptance gate before flipping `REACTION_VERIFY` default: `>= 75%` binary reaction vs calm accuracy, `<= 20%` calm-news FP rate, `100%` layout-cut spike rejection, `<= 4.5s` median onset error on real shocks/freezes, and empirical Audio RMS + LiveChat co-trigger lift on motionless-rant / subtle-tease failure cases.

- [ ] **Step 1: Create fixture + cross-VOD benchmark test in `test_reaction_gold_benchmark.py`**

- [ ] **Step 2: Run benchmark + calibration suite**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_reaction_gold_benchmark.py`
Expected: Offline suite PASSES; optional cross-VOD real-clip calibration reports verified metrics and exposes any audio/chat tuning needed before enabling `REACTION_VERIFY=True` globally.

- [ ] **Step 3: Run full `skills/anibon-timestamper-local/tests/` and `tests/` test suites**

Run: `PYTHONPATH="lib" python3 -m unittest discover -s skills/anibon-timestamper-local/tests && PYTHONPATH="lib" python3 -m unittest discover -s tests`
Expected: All unit tests PASS (`0` failures).

- [ ] **Step 4: Commit**

```bash
git add skills/anibon-timestamper-local/tests/fixtures/cross_vod_reaction_gold.json \
  skills/anibon-timestamper-local/tests/test_reaction_gold_benchmark.py
git commit -m "test: add cross-VOD benchmark and Dual-Box co-trigger calibration"
```

---

## Self-Review Checklist

- **No Overfitting / Domain-Agnostic Coverage:** Zero FGO-only tokens (`DESIGN_REACTION_CUES` removed); triggers generalize across FGO (`tR9jOZVYSj8`), unplanned news (`McgRhdbJXlU`), and UE5 combat gaming (`XEOPUvpRw60`) via OBS auto-layout, `audio_envelope.py`, `mood_555.json` / LiveChat bursts, and universal Thai `EMOTION_REACTION_CUES`.
- **Empirical `VERDICT.md` Alignment:** Addresses all 7 empirically driven fixes: (1) auto OBS corner + `±1.5s` cut suppression, (2) Dual-Box `F` gating + full uncropped `W` / `(0,0,1,1)` fullscreen room context, (3) telemetry-injected VLM prompt + startle-laugh/freeze/anger/bed-pose rules, (4) domain-agnostic co-triggers, (5) earliest suprathreshold onset snapping + `20s` pre-window padding, (6) `2.0 fps` `#10`+`#12` thresholds + realistic benchmark targets, (7) `posture_act` & empty-chair guard separating bed-retreat/camera-play (`lie_on_bed`, `lean_into_cam`, `slump_on_desk`, `+3s..+12s` settled keyframe) from both `stunned_freeze` and true `empty_chair_afk`.
- **Reuses Existing Codebase:** Integrates `mood_555.json` (`parity_gates.py` / `scripts/analyze_555.py`), `livechat.py`, `multimodal_situations.py`, `vision_verify.py` (`is_ambiguous`, `stamp_seconds`), and `assembly.py` without duplicating chat/LLM plumbing.
- **Clean Code & Dependencies:** Zero `PIL` / `numpy` / `cv2` / `drawtext`; every new module `< 190` lines (`motion_types.py`, `obs_layout.py`, `audio_envelope.py`, `face_motion_metrics.py`, `face_motion.py`, `reaction_verify.py`); `creating-highlight-video` excluded.
