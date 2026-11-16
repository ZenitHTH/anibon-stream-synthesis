# Dual-Side Multi-Mood Detection & Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the 7-mood Dual-Side (Speaker + Chat) Mood Detection system against Whisper repetition loops, viewer Q&A echo, and `.xml`/`.json`/`.jsonl.gz` chunk formats, and wire it end-to-end across both `anibon-timestamper-local` and `anibon-timestamper` (cloud subagent prompts + validator).

**Architecture:** `scripts/speaker_mood.py` owns per-line deduplicated speaker cue extraction across `.txt`, `.json`, `.xml`, and `.jsonl.gz` chunk inputs and emits a 7-mood override (`RAGE_QUIT_PULSE`, `ANGRY_TILT_PULSE`, `PANIC_SHOCK_PULSE`, `SICK_AFK_PULSE`, `HYPE_CLUTCH_PULSE`, `SLEEPY_DRAIN_PULSE`). `scripts/analyze_555.py` fuses speaker overrides with chat signals into `mood_555.json`, which `lib/chunk/state.py`, `lib/process/parity_gates.py`, `skills/anibon-timestamper/scripts/build_subagent_prompts.py`, and `scripts/validate_mood.py` consume uniformly.

**Tech Stack:** Python 3.11+, `unittest`, `re`, `xml.etree.ElementTree`, `gzip`, `json`.

**Spec:** `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/specs/2026-08-06-mood-tone-guidance-design.md`

## Global Constraints

- Validation is **guidance-only** (`validate_mood.py` labels timestamps with mood + tone + suggested verbs; it never rejects a verb).
- Functions must stay `<= 20` lines per Clean Code rules; files stay focused on a single responsibility.
- All tests run via `PYTHONPATH="lib:scripts" python3 -m unittest` with zero network calls.
- `TONE_HINTS` must cover all 10 verdicts (`RAGE_QUIT_PULSE`, `ANGRY_TILT_PULSE`, `PANIC_SHOCK_PULSE`, `SICK_AFK_PULSE`, `HYPE_CLUTCH_PULSE`, `SLEEPY_DRAIN_PULSE`, `MEME_PULSE`, `HOT`, `WARM`, `QUIET`).

## Review Focus

1. **Whisper ASR single-line repetition loop** (e.g., `"เกลียดมาก เกลียดมาก เกลียดมาก เกลียดมาก"` or `"มังกรไล่ มังกรไล่ มังกรไล่ มังกรไล่"` on a single timestamp line): must count at most **1 match per regex category per transcript line** so a 1-second Whisper stutter cannot trigger `ANGRY_TILT_PULSE` or `PANIC_SHOCK_PULSE` by itself.
2. **Consecutive identical Whisper hallucination lines** (e.g., 30 consecutive lines of `(05:51:02) นี่ฟักกินอีก` in `PN-9JHUiq60` `chunk_78`): consecutive lines with identical normalized body text must be collapsed before counting speaker mood markers.
3. **Cloud timestamper `.xml` and local `.json` chunk files**: `resolve_speaker_chunk_path` and `parse_speaker_chunk` must support `chunk_NN.txt`, `chunk_NN.json`, and `chunk_NN.xml` so `anibon-timestamper` cloud workspaces get speaker mood overrides too.
4. **Cloud `build_subagent_prompts.py` nested `tone` dict**: `mood_555.json` stores `"tone": {"tone": "...", "verbs": [...]}`; `build_subagent_prompts.py` must format `tone["tone"]`, `tone["verbs"]`, and `speaker_cues` cleanly instead of printing raw dict reprs or `verbs: None`.
5. **Dual `validate_mood.py` drift**: `skills/anibon-timestamper/scripts/validate_mood.py` and `scripts/validate_mood.py` must share the exact same behavior (delegating or importing from `scripts/validate_mood.py`) so cloud and local validation never diverge.

---

### Task 1: Per-Line Deduplication, Whisper Loop Collapsing & Multi-Format Chunk Parsing in `scripts/speaker_mood.py`

**Files:**
- Modify: `scripts/speaker_mood.py`
- Test: `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`

**Interfaces:**
- Produces:
  - `dedup_transcript_lines(text: str) -> List[str]`
  - `parse_speaker_text(text: str) -> SpeakerStats` (counts at most 1 hit per regex category per distinct line)
  - `parse_speaker_chunk(chunk_path: Optional[Path]) -> SpeakerStats` (supports `.txt`, `.json`, `.xml`)
  - `resolve_speaker_chunk_path(chunks_dir: Optional[Path], chunk_id: str) -> Optional[Path]` (searches `.txt`, `.json`, `.xml`)

- [ ] **Step 1: Write the failing tests in `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`**

```python
    def test_whisper_single_line_stutter_does_not_trigger_angry_tilt(self):
        from speaker_mood import parse_speaker_text
        stutter = "(01:00:01) เกลียดมาก เกลียดมาก เกลียดมาก เกลียดมาก เกลียดมาก\n"
        sp = parse_speaker_text(stutter)
        self.assertEqual(sp.n_frust, 1)
        self.assertEqual(classify(ChatStats(), Config(), sp).verdict, "QUIET")

    def test_whisper_consecutive_duplicate_lines_collapsed(self):
        from speaker_mood import parse_speaker_text
        loop_lines = "\n".join(
            f"(05:51:{i:02d}) ไอ้เหี้ย อารมณ์เสีย" for i in range(15)
        )
        sp = parse_speaker_text(loop_lines)
        self.assertEqual(sp.n_swears, 1)
        self.assertEqual(sp.n_frust, 1)

    def test_parse_speaker_chunk_supports_xml_and_json(self):
        from speaker_mood import parse_speaker_chunk, resolve_speaker_chunk_path
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            xml_p = tdir / "chunk_05.xml"
            xml_p.write_text(
                '<chunk><item timestamp="00:20:01">ไม่เล่นแล้ว ลบเกมทิ้ง</item>'
                '<item timestamp="00:20:05">อารมณ์เสีย หัวร้อน หงุดหงิด</item></chunk>',
                encoding="utf-8",
            )
            resolved = resolve_speaker_chunk_path(tdir, "chunk_05")
            self.assertEqual(resolved, xml_p)
            sp = parse_speaker_chunk(resolved)
            self.assertEqual(classify(ChatStats(), Config(), sp).verdict, "RAGE_QUIT_PULSE")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py -v`
Expected: FAIL (`sp.n_frust` is 5 on stutter line; `.xml` not resolved by `resolve_speaker_chunk_path`).

- [ ] **Step 3: Implement `dedup_transcript_lines`, per-line capped `parse_speaker_text`, and `.txt`/`.json`/`.xml` support in `scripts/speaker_mood.py`**

Strip leading `(HH:MM:SS)` or `HH:MM:SS |` timestamps when comparing consecutive lines in `dedup_transcript_lines(text: str) -> List[str]`. In `parse_speaker_text`, count at most 1 match per regex (`SWEAR_RE`, `FRUST_RE`, `RAGE_QUIT_RE`, `SICK_AFK_RE`, `PANIC_SHOCK_RE`, `HYPE_CLUTCH_RE`, `SLEEPY_DRAIN_RE`) per deduplicated line. Extract `.xml` `<item>` text and `.json` `items[].text` in helper `_read_chunk_text(chunk_path: Path) -> str`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py -v`
Expected: PASS (18 tests OK)

- [ ] **Step 5: Commit**

```bash
git add scripts/speaker_mood.py skills/anibon-timestamper/tests/test_analyze_555_emoji.py
git commit -m "feat(mood): cap per-line speaker cues, collapse Whisper loops, support xml/json chunks"
```

---

### Task 2: Wire `--chunks` and Archive `.jsonl.gz` Support in `lib/process/parity_gates.py` and `scripts/analyze_555.py`

**Files:**
- Modify: `lib/process/parity_gates.py:33-44`
- Modify: `scripts/analyze_555.py:280-325`
- Test: `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`

**Interfaces:**
- Consumes: `load_jsonl_gz_chunks(gz_path: Path) -> Dict[str, SpeakerStats]` from `scripts/speaker_mood.py`
- Produces:
  - `analyze(livechat_dir: str, index_path: str, out_path: str, cfg: Optional[Config] = None, chunks_dir: str = "", transcript_gz: str = "") -> dict`
  - `ensure_mood_555(workspace: Path) -> None` (passes `--chunks <workspace>/chunks` and runs even when `livechat/` is absent if `chunks/` exists)

- [ ] **Step 1: Write the failing test in `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`**

```python
    def test_analyze_runs_speaker_only_when_livechat_dir_missing(self):
        from analyze_555 import analyze
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            cdir = ws / "chunks"
            cdir.mkdir()
            (cdir / "chunk_00.txt").write_text(
                "(00:01:00) ไอ้เหี้ย อารมณ์เสีย\n"
                "(00:01:05) หัวร้อน หงุดหงิด โคตรแย่\n"
                "(00:01:10) ไม่เล่นแล้ว ลบเกมทิ้ง\n",
                encoding="utf-8",
            )
            out = ws / "mood_555.json"
            res = analyze(str(ws / "livechat"), "", str(out), chunks_dir=str(cdir))
            self.assertEqual(res["chunk_00"]["verdict"], "RAGE_QUIT_PULSE")
```

- [ ] **Step 2: Run test to verify it passes/fails and test `ensure_mood_555` without `livechat/`**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py -v`

- [ ] **Step 3: Update `ensure_mood_555(workspace: Path)` in `lib/process/parity_gates.py` and add `--transcript-gz` to `scripts/analyze_555.py`**

In `lib/process/parity_gates.py`, allow `ensure_mood_555` to run when either `livechat.is_dir()` or `(workspace / "chunks").is_dir()`, passing `--chunks` when `chunks/` exists. In `scripts/analyze_555.py`, add `--transcript-gz` CLI flag calling `load_jsonl_gz_chunks(Path(transcript_gz))` when `chunks_dir` has no chunk files.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/process/parity_gates.py scripts/analyze_555.py skills/anibon-timestamper/tests/test_analyze_555_emoji.py
git commit -m "feat(mood): wire speaker-only fallback in parity_gates and transcript-gz in analyze_555"
```

---

### Task 3: Unify `validate_mood.py` & Fix Cloud `build_subagent_prompts.py` Mood Formatting

**Files:**
- Modify: `skills/anibon-timestamper/scripts/validate_mood.py`
- Modify: `skills/anibon-timestamper/scripts/build_subagent_prompts.py:67-71`
- Test: `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`

**Interfaces:**
- Consumes: `mood_555.json` schema (`verdict`, `tone: {"tone": str, "verbs": List[str]}`, `speaker_cues: List[str]`)
- Produces:
  - `format_chunk_mood_guidance(cmood: dict) -> str` in `skills/anibon-timestamper/scripts/build_subagent_prompts.py`
  - Unified `skills/anibon-timestamper/scripts/validate_mood.py` re-exporting `scripts/validate_mood.py`

- [ ] **Step 1: Write the failing test in `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`**

```python
    def test_build_subagent_prompts_formats_nested_tone_and_cues(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from build_subagent_prompts import format_chunk_mood_guidance
        sample = {
            "verdict": "ANGRY_TILT_PULSE",
            "tone": {"tone": "ปู่โบ๊ตหัวร้อน", "verbs": ["หัวร้อน", "โวย"]},
            "speaker_cues": ["อารมณ์เสีย", "ไอ้เหี้ย"],
        }
        formatted = format_chunk_mood_guidance(sample)
        self.assertIn("ANGRY_TILT_PULSE", formatted)
        self.assertIn("ปู่โบ๊ตหัวร้อน", formatted)
        self.assertIn("หัวร้อน/โวย", formatted)
        self.assertIn("อารมณ์เสีย", formatted)
        self.assertNotIn("verbs: None", formatted)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_chunk_mood_guidance'`

- [ ] **Step 3: Implement `format_chunk_mood_guidance(cmood: dict) -> str` in `skills/anibon-timestamper/scripts/build_subagent_prompts.py` and sync `skills/anibon-timestamper/scripts/validate_mood.py`**

In `build_subagent_prompts.py`, extract `format_chunk_mood_guidance(cmood: dict) -> str` handling both `tone` as a `dict` (`{"tone": ..., "verbs": [...]}`) and legacy `str`, plus `speaker_cues`. Replace duplicate logic in `skills/anibon-timestamper/scripts/validate_mood.py` by delegating to root `scripts/validate_mood.py`.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `PYTHONPATH="lib:scripts" python3 -m unittest skills/anibon-timestamper/tests/test_analyze_555_emoji.py && PYTHONPATH="lib:scripts" python3 -m unittest discover -s skills/anibon-timestamper-local/tests -q`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper/scripts/build_subagent_prompts.py skills/anibon-timestamper/scripts/validate_mood.py skills/anibon-timestamper/tests/test_analyze_555_emoji.py
git commit -m "fix(mood): format nested tone/cues in build_subagent_prompts and unify validate_mood"
```
