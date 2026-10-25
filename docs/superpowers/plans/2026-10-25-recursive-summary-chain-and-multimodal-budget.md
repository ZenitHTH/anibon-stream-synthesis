# Recursive Summary Chain & Multimodal Frame Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix recursive summary chain amnesia, frozen active topic titles, excessive per-chunk vision token load (`16` frames/chunk), and missing YouTube storyboard fallback in `anibon-timestamper-local`.

**Architecture:**
1. Tune default multimodal frame budgets (`max_chunk_frames: 6`, `scene_delta_threshold: 0.12`, `_WI_SNIPPET_LIMIT: 1800`) so 12B vision models stay under the ~4k–5k active-attention threshold per turn.
2. Refactor `lib/process/runners/recursive.py` and `lib/process/prompts.py` with small, single-responsibility functions (`<20` lines) to unfreeze `current_topic_title` whenever `new_topic_title` is emitted, chain `rolling_summary` as a 3-chunk sliding window (`" -> "`), and inject the last 3 emitted timestamps into `## PREVIOUS TOPIC STATE` to prevent duplicate micro-stamping.
3. Add an automatic 144p video + FFmpeg `tile=3x3` fallback in `lib/download/ytdlp.py` when YouTube omits `sb0/sb1/sb2/sb3` storyboard formats.

**Tech Stack:** Python 3, `unittest`, `yt-dlp`, `ffmpeg`.

**Spec:** Empirical root-cause analysis from `youtube_XBtoCdurZ_Y_workspace/recursive_outputs/chunk_00..114.json`.

## Global Constraints

- Follow Robert C. Martin's Clean Code rules: max 20 lines per function, single responsibility per function, max 3 arguments (or group into config/struct/existing signature), no boolean flag arguments on new helpers, guard clauses first.
- All existing unit tests in `tests/` (61 tests) and `skills/anibon-timestamper-local/tests/` (136 tests) must pass via `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest`.
- Preserve backward compatibility for existing `build_recursive_prompt()` callers by making `recent_timestamps: Optional[List[str]] = None` optional.

## Review Focus

- Model returns `"new_topic_title": "null"` or `"None"` as a string literal while `is_continuation` is `True` -> `_resolve_next_topic_title` must treat string `"null"`/`"none"` as empty and keep `current_topic_title`.
- `rolling_summary` accumulates identical consecutive summaries across static chunks -> `_chain_rolling_summary` must deduplicate consecutive identical sentences before joining with `" -> "`.
- `all_timestamps` is empty on `chunk_00` -> `build_recursive_prompt` must omit the `Recent Emitted Timestamps` block cleanly without empty bullet points.
- `yt-dlp -f sb0/sb1/sb2/sb3` fails AND `ffmpeg` or `yt-dlp -f 160` fails (e.g. offline test environment) -> `download_storyboard` must catch errors and return `None` without raising unhandled exceptions.
- Resuming a paused workspace from `chunk_XX.json` -> `_should_skip_cached_chunk` must preserve chained `rolling_summary` and `current_topic_title` seamlessly.

---

### Task 1: Multimodal Frame Budget & World Identity Snippet Diet

**Files:**
- Modify: `skills/anibon-timestamper-local/config.json:34-39`
- Modify: `lib/common/config.py:210-265`
- Modify: `lib/process/prompts.py:24-26`
- Test: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Produces:
  - `common.config.MAX_CHUNK_FRAMES: int = 6`
  - `common.config.SCENE_DELTA_THRESHOLD: float = 0.12`
  - `process.prompts._WI_SNIPPET_LIMIT: int = 1800`

- [x] **Step 1: Write the failing test in `skills/anibon-timestamper-local/tests/test_config.py`**

```python
    def test_multimodal_frame_budget_defaults_tuned_for_12b_attention(self):
        from common import config
        from process import prompts
        config.load_config(config.SKILL_CONFIG_PATH, override=True)
        self.assertEqual(config.MAX_CHUNK_FRAMES, 6)
        self.assertAlmostEqual(config.SCENE_DELTA_THRESHOLD, 0.12)
        self.assertEqual(prompts._WI_SNIPPET_LIMIT, 1800)
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py`
Expected: FAIL (`AssertionError: 16 != 6`)

- [x] **Step 3: Update defaults in `skills/anibon-timestamper-local/config.json`, `lib/common/config.py`, and `lib/process/prompts.py`**

- In `skills/anibon-timestamper-local/config.json`: set `"scene_delta_threshold": 0.12` and `"max_chunk_frames": 6`.
- In `lib/common/config.py`: set fallback defaults for `SCENE_DELTA_THRESHOLD` to `0.12` and `MAX_CHUNK_FRAMES` to `6` in both module init and `reload_config()`.
- In `lib/process/prompts.py`: set `_WI_SNIPPET_LIMIT = 1800`.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_config.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/config.json lib/common/config.py lib/process/prompts.py skills/anibon-timestamper-local/tests/test_config.py
git commit -m "perf(multimodal): cap default chunk frames to 6 and trim WI snippet limit"
```

---

### Task 2: Rolling Summary Sliding Window, Topic Title Unfreezing & Recent Timestamps Prompting

**Files:**
- Modify: `lib/process/runners/recursive.py:199-231` and `lib/process/runners/recursive.py:390-405`
- Modify: `lib/process/prompts.py:236-388`
- Test: `skills/anibon-timestamper-local/tests/test_prompts.py`
- Test: `skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`

**Interfaces:**
- Produces in `lib/process/runners/recursive.py`:
  - `_clean_topic_candidate(raw_title: any) -> str`
  - `_resolve_next_topic_title(res: dict, current_topic_title: str) -> str`
  - `_chain_rolling_summary(rolling_summary: str, res: dict) -> str`
- Produces in `lib/process/prompts.py`:
  - `_format_previous_topic_section(chunk_idx: int, current_topic: str, rolling_summary: str, recent_timestamps: Optional[List[str]] = None) -> str`
  - `build_recursive_prompt(..., recent_timestamps: Optional[List[str]] = None) -> str`

- [x] **Step 1: Write the failing tests in `test_prompts.py` and `test_process_chunks_resume.py`**

In `skills/anibon-timestamper-local/tests/test_prompts.py`:
```python
    def test_build_recursive_prompt_includes_recent_timestamps_and_mid_chunk_shift_rule(self):
        chunk = {
            "_idx": 5,
            "items": [{"timestamp": "00:20:00", "start": 1200.0, "text": "เปลี่ยนมาดูเกมใหม่กันครับ"}]
        }
        recent = [
            "00:12:00 - [WatchParty] ส่องตัวอย่างเกมแรก",
            "00:16:30 - [Talk] วิเคราะห์ระบบกาชา",
        ]
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="วิเคราะห์ระบบกาชา",
            rolling_summary="คุยเรื่องเรทกาชา -> เปรียบเทียบราคาสกิน",
            lang="th",
            recent_timestamps=recent,
        )
        self.assertIn("Recent Emitted Timestamps", prompt)
        self.assertIn("00:16:30 - [Talk] วิเคราะห์ระบบกาชา", prompt)
        self.assertIn("mid-chunk", prompt.lower())
```

In `skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`:
```python
    def test_update_topic_flow_unfreezes_title_on_mid_chunk_shift_and_chains_summary(self):
        from process.runners.recursive import _update_topic_flow
        chunk = {"start_sec": 300, "end_sec": 600}
        all_ts = ["00:00:00 - [WatchParty] เปิดสตรีม"]
        # Model sets is_continuation=True (mid-chunk shift) but provides new_topic_title
        res1 = {
            "is_continuation": True,
            "timestamps": ["00:06:00 - [WatchParty] ส่องฉลอง 7.5 ปี Arknights"],
            "chunk_summary": "เริ่มดู PV Arknights 7.5 ปี",
            "updated_summary": "เปลี่ยนจากคุยทั่วไปมาดู PV Arknights 7.5 ปี",
            "new_topic_title": "ส่องอัปเดต 7.5 ปี Arknights",
        }
        _, _, title1, sum1 = _update_topic_flow(res1, chunk, all_ts, "เปิดสตรีมดูอนิเมะ", "ทักทายผู้ชมช่วงเปิดไลฟ์")
        self.assertEqual(title1, "ส่องอัปเดต 7.5 ปี Arknights")
        self.assertIn("ทักทายผู้ชมช่วงเปิดไลฟ์ -> เปลี่ยนจากคุยทั่วไปมาดู PV Arknights 7.5 ปี", sum1)

        # String literal "null" in new_topic_title must NOT overwrite current_topic_title
        res2 = {
            "is_continuation": True,
            "timestamps": [],
            "chunk_summary": "วิเคราะห์สกิลตัวละครใหม่ต่อ",
            "updated_summary": "วิเคราะห์สกิลตัวละครใหม่ใน Arknights",
            "new_topic_title": "null",
        }
        _, _, title2, sum2 = _update_topic_flow(res2, chunk, all_ts, title1, sum1)
        self.assertEqual(title2, "ส่องอัปเดต 7.5 ปี Arknights")
        self.assertEqual(len(sum2.split(" -> ")), 3)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_prompts.py skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`
Expected: FAIL (`TypeError: build_recursive_prompt() got an unexpected keyword argument 'recent_timestamps'` and `AssertionError: 'เปิดสตรีมดูอนิเมะ' != 'ส่องอัปเดต 7.5 ปี Arknights'`)

- [x] **Step 3: Implement helpers in `lib/process/runners/recursive.py` and `lib/process/prompts.py`**

In `lib/process/runners/recursive.py` (keep each helper $\le 15$ lines):
```python
def _clean_topic_candidate(raw_title: any) -> str:
    """Return stripped topic title or empty string if null/none placeholder."""
    if not isinstance(raw_title, str):
        return ""
    cleaned = raw_title.strip()
    return "" if cleaned.lower() in ("null", "none", "n/a", "-") else cleaned


def _resolve_next_topic_title(res: dict, current_topic_title: str) -> str:
    """Unfreeze topic title whenever model provides a valid new_topic_title or shift."""
    new_title = _clean_topic_candidate(res.get("new_topic_title"))
    if new_title:
        return new_title
    if not res.get("is_continuation", False):
        ch_sum = _clean_topic_candidate(res.get("chunk_summary"))
        return ch_sum or current_topic_title
    return current_topic_title


def _chain_rolling_summary(rolling_summary: str, res: dict) -> str:
    """Maintain a 3-chunk sliding window summary chain on continuations; reset on clean topic break."""
    next_entry = (res.get("updated_summary") or res.get("chunk_summary") or "").strip()
    if not next_entry:
        return rolling_summary
    if not res.get("is_continuation", False) or not rolling_summary:
        return next_entry
    parts = [p.strip() for p in rolling_summary.split(" -> ") if p.strip()]
    if not parts or parts[-1] != next_entry:
        parts.append(next_entry)
    return " -> ".join(parts[-3:])
```
Update `_update_topic_flow` to use `_resolve_next_topic_title(res, current_topic_title)` and `_chain_rolling_summary(rolling_summary, res)`, and pass `recent_timestamps=all_timestamps[-3:]` in `_process_single_recursive_chunk`.

In `lib/process/prompts.py`:
- Extract `_format_previous_topic_section(chunk_idx: int, current_topic: str, rolling_summary: str, recent_timestamps: Optional[List[str]] = None) -> str` to display:
  - `Active Topic: {current_topic}`
  - `Rolling Context Chain (last 15m): {rolling_summary}`
  - `Recent Emitted Timestamps (DO NOT re-stamp the same ongoing topic):` followed by the last 3 timestamps.
- Update `is_continuation` rule in `build_recursive_prompt` to explicitly instruct:
  `false: Speaker shifted to a new subject, different game, or major activity pivot (even if the shift happens mid-chunk).`

- [x] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_prompts.py skills/anibon-timestamper-local/tests/test_process_chunks_resume.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add lib/process/runners/recursive.py lib/process/prompts.py skills/anibon-timestamper-local/tests/test_prompts.py skills/anibon-timestamper-local/tests/test_process_chunks_resume.py
git commit -m "fix(recursive): chain 3-chunk rolling summary and unfreeze topic title on mid-chunk shifts"
```

---

### Task 3: Automatic 144p Video Storyboard Synthesis Fallback

**Files:**
- Modify: `lib/download/ytdlp.py:56-92`
- Test: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Produces in `lib/download/ytdlp.py`:
  - `_synthesize_slides_from_144p(url: str, frames_dir: Path) -> Path | None`
  - Updated `download_storyboard(url: str, workspace: Path) -> Path | None`

- [x] **Step 1: Write the failing test in `skills/anibon-timestamper-local/tests/test_multimodal.py`**

```python
    def test_download_storyboard_falls_back_to_144p_ffmpeg_tiling_when_sb_missing(self):
        import tempfile
        from download.ytdlp import download_storyboard
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            clean_dir = ws / "frames" / "slides_clean"

            def fake_run(cmd, **kwargs):
                if "sb0/sb1/sb2/sb3" in cmd:
                    return MagicMock(returncode=1)
                if "video_144p.mp4" in " ".join(str(c) for c in cmd) and "yt-dlp" in str(cmd[0]):
                    (ws / "frames" / "video_144p.mp4").write_bytes(b"mp4")
                    return MagicMock(returncode=0)
                if "ffmpeg" in str(cmd[0]):
                    clean_dir.mkdir(parents=True, exist_ok=True)
                    (clean_dir / "slide_0001.jpg").write_bytes(b"jpg")
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with patch("subprocess.run", side_effect=fake_run):
                result = download_storyboard("https://www.youtube.com/watch?v=XBtoCdurZ_Y", ws)
                self.assertEqual(result, clean_dir)
                self.assertTrue((clean_dir / "slide_0001.jpg").is_file())
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_multimodal.py`
Expected: FAIL (`AssertionError: None != PosixPath('.../frames/slides_clean')`)

- [x] **Step 3: Implement `_synthesize_slides_from_144p(url: str, frames_dir: Path) -> Path | None` in `lib/download/ytdlp.py`**

- When `download_storyboard` finds no `.mhtml` file after attempting `-f sb0/sb1/sb2/sb3`, call `_synthesize_slides_from_144p(url, frames_dir)`.
- `_synthesize_slides_from_144p` downloads `-f 160/bestvideo[height<=240][ext=mp4]/worst[ext=mp4]` to `frames_dir / "video_144p.mp4"` (if not already present) and runs `ffmpeg -v error -y -i <mp4> -vf fps=1/10,scale=320:180,tile=3x3 -q:v 3 <slides_clean>/slide_%04d.jpg`.
- Keep each helper under 20 lines with early guard returns.

- [x] **Step 4: Run full test suites to verify all tests pass**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest discover -s skills/anibon-timestamper-local/tests && python3 -m unittest discover -s tests`
Expected: PASS (all 139+ local skill tests and 61 root tests pass)

- [x] **Step 5: Commit**

```bash
git add lib/download/ytdlp.py skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "feat(storyboard): auto-fallback to 144p video 3x3 tiling when sb0-sb3 unavailable"
```
