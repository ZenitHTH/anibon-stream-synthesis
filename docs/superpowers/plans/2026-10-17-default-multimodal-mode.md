# Default Multimodal Process Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Storyboard keyframe multimodal analysis by default across the `anibon-timestamper-local` pipeline (`config.json`, `prepare_video.py`, `anibon/multimodal.py`, and `process_chunks_local.py`) with automatic storyboard acquisition and `--no-multimodal` opt-out.

**Architecture:** `config.json` and `anibon/config.py` define `"multimodal_chunks": true` (`DEFAULT_MULTIMODAL_CHUNKS = True`) via a new `cfg_bool()` helper. `lib/anibon/ytdlp.py` provides `download_storyboard(url, workspace)` which is called during `prepare_video.py` and on-demand inside `prepare_storyboard_slides(workspace, video_url)` if a workspace lacks storyboard files. `process_chunks_local.py` defaults `--multimodal-chunks` to `DEFAULT_MULTIMODAL_CHUNKS` and exposes `--no-multimodal` / `--text-only` to disable it.

**Tech Stack:** Python 3 standard library (`json`, `os`, `subprocess`, `pathlib`, `unittest`), `yt-dlp`, `ffmpeg` / `PIL`.

**Spec:** User request (2026-10-17) — set up default multimodal process mode for `anibon-timestamper-local`.

## Global Constraints

- Zero external Python dependencies added (`cfg_bool` uses stdlib only).
- Graceful degradation invariant: if `yt-dlp` storyboard download fails or the loaded LLM does not support vision (`image_url`), `process_chunks_local.py` must log a warning and fall back to text-only inference without crashing the run.
- Existing workspaces that already have `chunks/` and `.video_url` (such as an in-progress run) must auto-fetch `frames/storyboard.mhtml` inside `prepare_storyboard_slides()` when multimodal mode is active.

## Review Focus

- `cfg_bool` must handle native JSON booleans (`true`/`false`), string env overrides (`"1"`, `"true"`, `"yes"`, `"0"`, `"false"`, `"no"`), and invalid strings (falling back to `default`).
- `prepare_storyboard_slides(workspace, video_url)` must not invoke `yt-dlp` when neither `video_url` nor `workspace/.video_url` exists (e.g., offline unit tests with empty temp directories).
- Passing `--no-multimodal` or `--text-only` on the CLI must override `DEFAULT_MULTIMODAL_CHUNKS=True` to `False`.
- Custom `--config` files setting `"multimodal_chunks": false` must set `args.multimodal_chunks` to `False` when no explicit CLI flag is given.
- `run_group_mode` must also respect `args.multimodal_chunks` (or cleanly log/handle keyframes) alongside `run_recursive_mode`.

---

### Task 1: Add `cfg_bool` and `DEFAULT_MULTIMODAL_CHUNKS` to `config.json` and `anibon/config.py`

**Files:**
- Modify: `skills/anibon-timestamper-local/config.json`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/config.py`
- Modify: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Produces in `anibon.config`:
  - `cfg_bool(key: str, default: bool) -> bool`
  - `DEFAULT_MULTIMODAL_CHUNKS: bool` (defaults to `True`)

- [x] **Step 1: Write failing tests in `tests/test_config.py` for `cfg_bool` and `DEFAULT_MULTIMODAL_CHUNKS`**

```python
    def test_cfg_bool_and_default_multimodal_chunks(self):
        from anibon.config import cfg_bool, DEFAULT_MULTIMODAL_CHUNKS
        self.assertTrue(DEFAULT_MULTIMODAL_CHUNKS)
        self.assertTrue(cfg_bool("multimodal_chunks", False))

        os.environ["ANIBON_MULTIMODAL_CHUNKS"] = "false"
        try:
            self.assertFalse(cfg_bool("multimodal_chunks", True))
        finally:
            os.environ.pop("ANIBON_MULTIMODAL_CHUNKS", None)

        os.environ["ANIBON_MULTIMODAL_CHUNKS"] = "invalid_bool"
        try:
            self.assertTrue(cfg_bool("multimodal_chunks", True))
            self.assertFalse(cfg_bool("multimodal_chunks", False))
        finally:
            os.environ.pop("ANIBON_MULTIMODAL_CHUNKS", None)
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
Expected: FAIL with `ImportError: cannot import name 'cfg_bool' from 'anibon.config'`

- [x] **Step 3: Implement `cfg_bool` and `DEFAULT_MULTIMODAL_CHUNKS` in `scripts/anibon/config.py` and `config.json`**

Add `"multimodal_chunks": true` to `skills/anibon-timestamper-local/config.json`. In `scripts/anibon/config.py`, add `cfg_bool(key: str, default: bool) -> bool` (accepting `bool`, `int` `0`/`1`, and case-insensitive strings `"true"/"1"/"yes"/"on"` vs `"false"/"0"/"no"/"off"`), define `DEFAULT_MULTIMODAL_CHUNKS: bool = True`, and refresh it inside `reload_config()`.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/config.json skills/anibon-timestamper-local/scripts/anibon/config.py skills/anibon-timestamper-local/tests/test_config.py
git commit -m "feat(local): add cfg_bool and default multimodal_chunks=true in config"
```


---

### Task 2: Auto-download storyboard in `ytdlp.py`, `prepare_video.py`, and `anibon/multimodal.py`

**Files:**
- Modify: `lib/anibon/ytdlp.py`
- Modify: `skills/anibon-timestamper-local/scripts/prepare_video.py`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/multimodal.py`
- Modify: `skills/anibon-timestamper-local/tests/test_multimodal.py`

**Interfaces:**
- Consumes: `ytdlp_cmd()` from `anibon.ytdlp`
- Produces:
  - `anibon.ytdlp.download_storyboard(url: str, workspace: Path) -> Path | None`
  - `anibon.multimodal.prepare_storyboard_slides(workspace: Path, video_url: Optional[str] = None) -> Optional[Path]`
  - `--no-storyboard` flag in `scripts/prepare_video.py`

- [x] **Step 1: Write failing tests in `tests/test_multimodal.py` for auto-downloading storyboard slides**

```python
    def test_prepare_storyboard_slides_auto_downloads_when_video_url_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".video_url").write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ", encoding="utf-8")

            def fake_download(url, workspace):
                frames = Path(workspace) / "frames"
                frames.mkdir(parents=True, exist_ok=True)
                slides = frames / "slides_clean"
                slides.mkdir(parents=True, exist_ok=True)
                for i in range(1, 15):
                    (slides / f"slide_{i:04d}.jpg").write_bytes(b"jpeg")
                return frames / "storyboard.mhtml"

            with patch("anibon.multimodal.download_storyboard", side_effect=fake_download) as mock_dl:
                res = prepare_storyboard_slides(ws)
                mock_dl.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                self.assertIsNotNone(res)
                self.assertEqual(res.name, "slides_clean")
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="scripts:../../lib" python3 -m unittest tests.test_multimodal -v`
Expected: FAIL with `AttributeError: <module 'anibon.multimodal'> does not have the attribute 'download_storyboard'`

- [x] **Step 3: Implement `download_storyboard` in `lib/anibon/ytdlp.py`, hook into `prepare_video.py` and `anibon/multimodal.py`**

1. In `lib/anibon/ytdlp.py`, add `download_storyboard(url: str, workspace: Path) -> Path | None` running `[*ytdlp_cmd(), "-f", "sb0/sb1/sb2/sb3", "-o", str(frames_dir / "storyboard.%(ext)s"), url]` if no `.mhtml` file exists in `workspace / "frames"`.
2. In `scripts/prepare_video.py`, call `ytdlp.download_storyboard(url, workspace)` by default unless `--no-storyboard` is passed.
3. In `scripts/anibon/multimodal.py`, import `download_storyboard` (with fallback if `anibon.ytdlp` is unavailable) and in `prepare_storyboard_slides(workspace: Path, video_url: Optional[str] = None)`, if no unpacked slides or `.mhtml` exist, resolve `url = video_url or (workspace / ".video_url").read_text().strip()` (when file exists), call `download_storyboard(url, workspace)`, and unpack the downloaded MHTML.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="scripts:../../lib" python3 -m unittest tests.test_multimodal -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add lib/anibon/ytdlp.py skills/anibon-timestamper-local/scripts/prepare_video.py skills/anibon-timestamper-local/scripts/anibon/multimodal.py skills/anibon-timestamper-local/tests/test_multimodal.py
git commit -m "feat(local): auto-download and unpack YouTube storyboards for multimodal mode"
```


---

### Task 3: Enable `--multimodal-chunks` by default in `process_chunks_local.py` with `--no-multimodal` opt-out

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`
- Modify: `skills/anibon-timestamper-local/SKILL.md`
- Modify: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Consumes: `DEFAULT_MULTIMODAL_CHUNKS` from `anibon.config`, `prepare_storyboard_slides` from `anibon.multimodal`
- Produces:
  - `args.multimodal_chunks` defaulting to `DEFAULT_MULTIMODAL_CHUNKS` (`True`)
  - CLI opt-out flags `--no-multimodal-chunks`, `--no-multimodal`, `--text-only` (`dest="multimodal_chunks"`, `action="store_false"`)

- [x] **Step 1: Write failing test in `tests/test_config.py` verifying default multimodal CLI flag and `--no-multimodal` opt-out**

```python
    def test_process_chunks_multimodal_default_and_opt_out_flag(self):
        import subprocess
        res = subprocess.run(
            ["python3", "scripts/process_chunks_local.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(SKILL_CONFIG_PATH.parent),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--no-multimodal", res.stdout)
        self.assertIn("--text-only", res.stdout)
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="scripts:../../lib" python3 -m unittest tests.test_config -v`
Expected: FAIL (`--no-multimodal` not in `--help`)

- [x] **Step 3: Update `process_chunks_local.py` and `SKILL.md`**

1. In `process_chunks_local.py`:
   - Import `DEFAULT_MULTIMODAL_CHUNKS` from `anibon.config`.
   - Set `--multimodal-chunks`, `--multimodal` (`dest="multimodal_chunks"`, `action="store_true"`, `default=DEFAULT_MULTIMODAL_CHUNKS`).
   - Add `--no-multimodal-chunks`, `--no-multimodal`, `--text-only` (`dest="multimodal_chunks"`, `action="store_false"`, `help="Disable Storyboard keyframe multimodal analysis and run in text-only mode"`).
   - Pass `video_url=getattr(args, "video_url", None)` into `prepare_storyboard_slides(workspace, video_url=...)` in `run_recursive_mode`.
   - Print `[init] multimodal  : enabled` (or `disabled (text-only)`) during startup summary in `main()`.
2. In `SKILL.md`:
   - Update Section 2 / 2.2 to state that `--multimodal-chunks` is enabled by default via `config.json` (`"multimodal_chunks": true`), and document `--no-multimodal` / `--text-only` for text-only execution.

- [x] **Step 4: Run full test suite to verify all tests pass**

Run: `PYTHONPATH="scripts:../../lib" python3 -m unittest discover -s tests -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper-local/SKILL.md skills/anibon-timestamper-local/tests/test_config.py
git commit -m "feat(local): enable multimodal chunk analysis by default with --no-multimodal opt-out"
```
