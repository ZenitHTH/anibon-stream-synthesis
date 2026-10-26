# Upgrade YouTube Minutes Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `youtube-minutes-synthesis` and `scripts/prepare_video.py` (`lib/download/ytdlp.py`) to use the latest v1.3.0 `anibon-stream-synthesis` unified tools (multi-language `json3` download, automatic `info.json` publish-date metadata persistence, Schema v2 garbled cleaning, storyboard/targeted frame slicing, and valid subagent prompt building).

**Architecture:**
1. Extend `lib/download/ytdlp.py` (`download_transcript`, `save_metadata`) and `lib/interface.py` so `scripts/prepare_video.py` supports multi-language subtitles (`--sub-langs "th-orig,en-orig,th,en"`) and automatically writes `info.json` with `upload_date`, `release_timestamp`, `title`, `duration`, and `channel` during workspace preparation.
2. Upgrade `skills/youtube-minutes-synthesis/SKILL.md` to replace legacy `.vtt` downloads, brittle `yt-dlp -g -f 134` frame commands, and deleted `../scripts/subagent-prompt-builder.py` references with the v1.3.0 pipeline (`scripts/prepare_video.py`, `clean_garbled_english.py`, `slice_stream_frame.py`, `unpack_storyboard.py`, `detect_signals.py`, and `build_subagent_prompts.py`), and remove the empty `skills/youtube-minutes-synthesis/scripts/` directory.

**Tech Stack:** Python 3 (`unittest`), `yt-dlp`, `ffmpeg`, Markdown (`SKILL.md`).

**Spec:** Approved design in conversation for `skills/youtube-minutes-synthesis/SKILL.md` and `scripts/prepare_video.py`.

## Global Constraints

- Follow Robert C. Martin's Clean Code rules: max 20 lines per function, single responsibility per function, max 3 arguments per function, no boolean flag arguments, guard clauses first, and keep files under 200 lines (`lib/download/ytdlp.py` is currently 199 lines — keep it $\le 200$ lines or extract helpers cleanly).
- Every Python module using PEP 604/585 type annotations (`|`, `list[...]`, `dict[...]`) must include `from __future__ import annotations`.
- All tests use standard library `unittest` (zero `pytest` imports).
- All existing root tests (`PYTHONPATH=lib python3 -m unittest discover -s tests`) must pass.

## Review Focus

- English-only YouTube videos (no `th-orig` or `th` track) -> `download_transcript` with default `sub_langs="th-orig,en-orig,th,en"` must pick up `raw_transcript.en-orig.json3` or `raw_transcript.en.json3` and rename it to `raw_transcript.json`.
- Multiple `.json3` subtitle files downloaded by `yt-dlp` (e.g., both `en` and `th-orig`) -> `_select_best_json3` must prefer original tracks (`th-orig`, `en-orig`) before fallback tracks (`th`, `en`).
- `probe_metadata` returns `None` (network error or offline test run) -> `save_metadata(url, workspace)` must return `None` gracefully without crashing `prepare_video.py`.
- `lib/download/ytdlp.py` line count -> Currently 199 lines; compact docstrings or extract metadata helper so `ytdlp.py` stays strictly under the 200-line Clean Code cap.
- Stale references in `skills/youtube-minutes-synthesis/SKILL.md` -> `test_skill_structure.py` must verify that `subagent-prompt-builder.py`, `sk_permission`, and `ead_file` are absent and `prepare_video.py`, `clean_garbled_english.py`, `slice_stream_frame.py`, and `build_subagent_prompts.py` are present, and that the empty `skills/youtube-minutes-synthesis/scripts` directory is removed.

---

### Task 1: Multi-Language Subtitle Download & Automatic `info.json` Metadata Persistence

**Files:**
- Modify: `lib/download/ytdlp.py`
- Modify: `lib/download/__init__.py`
- Modify: `lib/interface.py`
- Modify: `scripts/prepare_video.py`
- Test: `tests/test_prepare_video_cli.py`
- Test: `tests/test_interface.py`

**Interfaces:**
- Produces in `lib/download/ytdlp.py` (and re-exported via `lib/download/__init__.py` and `lib/interface.py`):
  - `DEFAULT_SUB_LANGS: str = "th-orig,en-orig,th,en"`
  - `_select_best_json3(workspace: Path) -> Path | None`
  - `download_transcript(url: str, workspace: Path, sub_langs: str = DEFAULT_SUB_LANGS) -> None`
  - `save_metadata(url: str, workspace: Path) -> Path | None`
- Produces in `scripts/prepare_video.py`:
  - CLI argument `--sub-langs` (default: `DEFAULT_SUB_LANGS`)
  - Calls `save_metadata(url, workspace)` and `download_transcript(url, workspace, args.sub_langs)`

- [ ] **Step 1: Write the failing tests in `tests/test_prepare_video_cli.py` and `tests/test_interface.py`**

In `tests/test_prepare_video_cli.py`, add tests for `--sub-langs`, English/multi-lang `.json3` selection priority, and `save_metadata`:
```python
    def test_cli_help_includes_sub_langs(self):
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PLUGIN_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--sub-langs", res.stdout)
        self.assertIn("th-orig,en-orig,th,en", res.stdout)

    def test_download_transcript_prefers_orig_and_supports_english_json3(self):
        import tempfile
        from unittest.mock import patch
        import sys as _sys
        _sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
        from download.ytdlp import download_transcript

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            def fake_run(cmd, **kwargs):
                (ws / "raw_transcript.en.json3").write_text('{"events": [{"segs": [{"utf8": "translated"}]}]}', encoding="utf-8")
                (ws / "raw_transcript.en-orig.json3").write_text('{"events": [{"segs": [{"utf8": "original"}]}]}', encoding="utf-8")

            with patch("subprocess.run", side_effect=fake_run):
                download_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                out = ws / "raw_transcript.json"
                self.assertTrue(out.is_file())
                self.assertIn("original", out.read_text(encoding="utf-8"))

    def test_save_metadata_writes_compact_info_json_and_handles_none(self):
        import json
        import tempfile
        from unittest.mock import patch
        import sys as _sys
        _sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
        from download.ytdlp import save_metadata

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            fake_meta = {
                "id": "dQw4w9WgXcQ",
                "title": "Test Meeting Video",
                "upload_date": "20261025",
                "release_timestamp": 1792944000,
                "duration": 1800,
                "channel": "Test Channel",
                "uploader": "Test Uploader",
                "formats": [{"huge": "ignored"}],
            }
            with patch("download.ytdlp.probe_metadata", return_value=fake_meta):
                info_path = save_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                self.assertEqual(info_path, ws / "info.json")
                saved = json.loads(info_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["upload_date"], "20261025")
                self.assertEqual(saved["title"], "Test Meeting Video")
                self.assertNotIn("formats", saved)

        with tempfile.TemporaryDirectory() as tmp2:
            ws2 = Path(tmp2)
            with patch("download.ytdlp.probe_metadata", return_value=None):
                self.assertIsNone(save_metadata("https://www.youtube.com/watch?v=bad", ws2))
```

In `tests/test_interface.py`, add assertions in `test_download_functions_callable`:
```python
        self.assertTrue(callable(interface.save_metadata))
        self.assertEqual(interface.DEFAULT_SUB_LANGS, "th-orig,en-orig,th,en")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=lib python3 -m unittest tests/test_prepare_video_cli.py tests/test_interface.py`
Expected: FAIL (`ImportError: cannot import name 'save_metadata'` and `--sub-langs` missing from `--help`)

- [ ] **Step 3: Implement `DEFAULT_SUB_LANGS`, `_select_best_json3`, `download_transcript`, and `save_metadata` in `lib/download/ytdlp.py`, re-export in `lib/download/__init__.py` & `lib/interface.py`, and wire into `scripts/prepare_video.py`**

In `lib/download/ytdlp.py` (keep all functions $\le 20$ lines, max 3 args, and total file $< 200$ lines):
```python
DEFAULT_SUB_LANGS = "th-orig,en-orig,th,en"
_SUB_PRIORITY = ("th-orig", "en-orig", "th", "en")
_METADATA_KEYS = ("id", "title", "upload_date", "release_timestamp", "duration", "channel", "uploader", "webpage_url")


def _select_best_json3(workspace: Path) -> Path | None:
    """Select downloaded .json3 file preferring original audio tracks."""
    candidates = sorted(workspace.glob("raw_transcript*.json3"))
    if not candidates:
        return None
    for lang in _SUB_PRIORITY:
        for path in candidates:
            if path.name.endswith(f".{lang}.json3"):
                return path
    return candidates[0]


def download_transcript(url: str, workspace: Path, sub_langs: str = DEFAULT_SUB_LANGS) -> None:
    """Download YouTube transcript via yt-dlp as raw_transcript.json."""
    out = workspace / "raw_transcript.json"
    if out.exists():
        print("[*] Transcript already exists, skipping download.", file=sys.stderr)
        return
    print("[*] Downloading transcript via yt-dlp...", file=sys.stderr)
    cmd = [
        *ytdlp_cmd(), "-P", str(workspace), "--write-auto-subs", "--write-subs",
        "--sub-lang", sub_langs, "--sub-format", "json3", "--skip-download",
        "--ignore-no-formats-error", "-o", "raw_transcript", url,
    ]
    subprocess.run(cmd, check=False)
    best = _select_best_json3(workspace)
    if best:
        best.rename(out)
    if not out.exists():
        print("[!] Error: Failed to download transcript.", file=sys.stderr)
        sys.exit(1)


def save_metadata(url: str, workspace: Path) -> Path | None:
    """Probe and persist compact video metadata (upload_date, title, duration) to info.json."""
    info_path = Path(workspace) / "info.json"
    if info_path.is_file():
        return info_path
    meta = probe_metadata(url)
    if not meta:
        return None
    compact = {k: meta.get(k) for k in _METADATA_KEYS if meta.get(k) is not None}
    info_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding="utf-8")
    return info_path
```

Export `DEFAULT_SUB_LANGS` and `save_metadata` in `lib/download/__init__.py` and `lib/interface.py` (`__all__`).
In `scripts/prepare_video.py`:
- Import `DEFAULT_SUB_LANGS` and `save_metadata` from `interface`.
- Add `--sub-langs` CLI option (`default=DEFAULT_SUB_LANGS`, `help=f"Subtitle language priority (default: {DEFAULT_SUB_LANGS})"`).
- Call `save_metadata(url, workspace)` and `download_transcript(url, workspace, args.sub_langs)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=lib python3 -m unittest tests/test_prepare_video_cli.py tests/test_interface.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/download/ytdlp.py lib/download/__init__.py lib/interface.py scripts/prepare_video.py tests/test_prepare_video_cli.py tests/test_interface.py
git commit -m "feat(download): support multi-lang json3 subs and save info.json in prepare_video"
```

---

### Task 2: Upgrade `skills/youtube-minutes-synthesis/SKILL.md` to v1.3.0 Pipeline & Remove Empty Scripts Dir

**Files:**
- Modify: `skills/youtube-minutes-synthesis/SKILL.md`
- Delete directory: `skills/youtube-minutes-synthesis/scripts/`
- Modify: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes:
  - `scripts/prepare_video.py` (`--format xml --block 600 --overlap 60 --sub-langs`)
  - `skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py`
  - `skills/verifying-stream-ground-truth/scripts/slice_stream_frame.py`
  - `skills/anibon-stream-activity/scripts/unpack_storyboard.py`
  - `skills/anibon-timestamper/scripts/detect_signals.py`
  - `skills/anibon-timestamper/scripts/build_subagent_prompts.py`
- Produces:
  - Updated `skills/youtube-minutes-synthesis/SKILL.md` aligned with v1.3.0 plugin tools and subagent contracts.

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_youtube_minutes_synthesis_uses_v1_3_pipeline_tools` in `tests/test_skill_structure.py`:
```python
    def test_youtube_minutes_synthesis_uses_v1_3_pipeline_tools(self):
        skill_dir = SKILLS_DIR / "youtube-minutes-synthesis"
        skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        # Must not have empty scripts/ directory
        self.assertFalse(
            (skill_dir / "scripts").exists(),
            "Empty skills/youtube-minutes-synthesis/scripts directory should be removed",
        )
        # Must not reference dead/broken artifacts or typos
        for dead in ("subagent-prompt-builder.py", "sk_permission", "ead_file", "-f 134"):
            self.assertNotIn(
                dead,
                skill_md,
                f"youtube-minutes-synthesis/SKILL.md still contains outdated reference: {dead}",
            )
        # Must reference canonical v1.3.0 tools
        for required in (
            "scripts/prepare_video.py",
            "clean_garbled_english.py",
            "slice_stream_frame.py",
            "unpack_storyboard.py",
            "detect_signals.py",
            "build_subagent_prompts.py",
            "batching-subagents-concurrency",
            "anibon-local-transcription",
            "whisper-corruption-recovery",
        ):
            self.assertIn(
                required,
                skill_md,
                f"youtube-minutes-synthesis/SKILL.md missing v1.3.0 tool reference: {required}",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py`
Expected: FAIL (`skills/youtube-minutes-synthesis/scripts` still exists and `SKILL.md` still contains `subagent-prompt-builder.py`, `sk_permission`, `-f 134`)

- [ ] **Step 3: Remove empty `skills/youtube-minutes-synthesis/scripts/` directory and update `skills/youtube-minutes-synthesis/SKILL.md`**

1. Remove empty directory `skills/youtube-minutes-synthesis/scripts/`.
2. Update `skills/youtube-minutes-synthesis/SKILL.md` so all steps use the v1.3.0 plugin tools (commands run from plugin root `anibon-stream-synthesis/`):
   - **Pre-flight (`preparing-tools`)**: Verify `yt-dlp`, `ffmpeg`, `python3`.
   - **Step 1 (Prepare Workspace, Transcript & Publish Date)**:
     - Run `python3 -X utf8 scripts/prepare_video.py "<URL>" --format xml --block 600 --overlap 60`
     - Explain that `prepare_video.py` creates `~/youtube_<id>_workspace/`, writes `info.json` (`upload_date`, `release_timestamp`, `title`, `duration`, `channel`), downloads multi-language `json3` subtitles (`th-orig,en-orig,th,en` → `raw_transcript.json`), downloads storyboard slides (`frames/`), and applies `default_mappings.json` to emit 10-minute XML chunks (`chunks/chunk_*.xml`).
     - **Publish Date Rule**: Read `<workspace>/info.json` (or `yt-dlp --dump-json "<URL>"`) to record `upload_date` / `release_timestamp` in report metadata. Add `"Old video — context may differ from the present"` if older than 6 months; never attribute post-publish events to the speaker.
   - **Step 2 (Clean Thai-Latin Garbles & No-Caption Fallback)**:
     - Run `python3 -X utf8 skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py --chunks ~/youtube_<id>_workspace/chunks/` (uses root `resources/garbled_replacements.json` Schema v2).
     - **Missing Captions Fallback**: Load `anibon-local-transcription` (`whisper.cpp`) and `whisper-corruption-recovery` (`fix_hallucinations.py`) if YouTube has no captions or audio $\ge 2\text{h}$ has repetition loops.
     - **Anti-Bot / HTTP 403 / 429 Handling**: Use `--extractor-args "youtube:player_client=android"` first to avoid macOS Keychain prompts; only fall back to `--cookies-from-browser <browser>` (or user upload in cloud sandbox) if needed.
   - **Step 2.B (Visual Grounding & On-Screen Inspection)**:
     - **Fast Storyboard Inspection**: Unpack storyboard slides downloaded by `prepare_video.py`:
       `python3 -X utf8 skills/anibon-stream-activity/scripts/unpack_storyboard.py --mhtml "~/youtube_<id>_workspace/frames/storyboard*" --out-dir "~/youtube_<id>_workspace/frames/slides"`
     - **Targeted High-Res Frame Slicing (`verifying-stream-ground-truth`)**: When inspecting slides, tables, settings sheets, numbers, or banners at a specific timestamp, slice a targeted frame without downloading the full video:
       `python3 -X utf8 skills/verifying-stream-ground-truth/scripts/slice_stream_frame.py "<URL>" "<HH:MM:SS>" -o "~/youtube_<id>_workspace/frames/frame_<label>.jpg"`
     - Read the extracted image to verify on-screen text, numbers (including Japanese `万`/`億` conversions), and diagrams directly.
   - **Step 3 (Domain Signals & Hierarchical Agenda Synthesis)**:
     - **Videos $\le 40$ minutes**: Read `<workspace>/chunks/chunk_*.xml` sequentially to group agenda blocks and synthesize meeting minutes.
     - **Videos $> 40$ minutes (Subagent Dispatch Contract)**:
       1. **Permissions**: Ask user permission (`ask_permission` / workspace read permission) before spawning parallel subagents or downloading large media.
       2. **Detect Domain Signals**:
          `python3 -X utf8 skills/anibon-timestamper/scripts/detect_signals.py --chunks ~/youtube_<id>_workspace/chunks/ --knowledge resources/knowledge.json --output ~/youtube_<id>_workspace/signals.json`
          If `signals.json` matches domain references under `skills/anibon-world-identity/references/`, load `anibon-world-identity` to verify entity names.
       3. **Build Subagent Prompts**:
          `python3 -X utf8 skills/anibon-timestamper/scripts/build_subagent_prompts.py ~/youtube_<id>_workspace`
          Generates `<workspace>/prompts_by_chunk/chunk_NN.txt` ($<46\text{KB}$ per file) and `<workspace>/prompts/group_NN.txt`.
       4. **Rate-Limit-Safe Parallel Dispatch (`batching-subagents-concurrency`)**:
          Spawn subagents via `invoke_subagent` (`Model: "flash"`) in controlled batches of **4–6 subagents per turn**, reading assigned `file://<workspace>/prompts_by_chunk/chunk_NN.txt` files sequentially.
       5. **Reduce & Assemble**: Merge group summaries into the final Markdown meeting minutes report following the Recommended Template (or `anibon-summarizer` when timestamp sections are requested).

- [ ] **Step 4: Run full test suites to verify everything passes**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest discover -s tests && PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest discover -s skills/anibon-timestamper-local/tests`
Expected: PASS (all root tests and local timestamper tests pass, zero warnings/errors)

- [ ] **Step 5: Commit**

```bash
git add skills/youtube-minutes-synthesis tests/test_skill_structure.py
git commit -m "feat(youtube-minutes-synthesis): upgrade skill workflow to v1.3.0 pipeline tools"
```
