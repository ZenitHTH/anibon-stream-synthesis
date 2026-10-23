# Clean Script Architecture & Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate redundant script copies (`prepare_video.py`), eliminate the fragile cross-skill symlink web in favor of direct Clean Code component ownership, and enforce `lib/interface.py` as the single source of truth for CLI drivers.

**Architecture:** Shared cross-cutting CLI executables (`prepare_video.py`, `pack_timestamps.py`, `check_sections.py`, `analyze_555.py`, `validate_tags.py`, `audit_gaps.py`, `whisper_dispatcher.py`) reside exclusively at the plugin root `scripts/` as thin CLI adapters importing from `interface`. Skill-specific scripts reside only in their respective skill directory (`skills/<skill>/scripts/`). All duplicate file copies and deceptive symlink shims across skills are removed, and `test_skill_structure.py` is updated to verify this clean separation.

**Tech Stack:** Python 3.15, standard library `unittest`, `argparse`, `pathlib`, plugin `interface` facade.

**Spec:** Clean Code / Clean Architecture component principles by Robert C. Martin (Single Source of Truth, Common Closure Principle, Elimination of Duplication).

---

## Global Constraints

- **Single Source of Truth**: Exactly one canonical implementation of each CLI driver on disk; zero duplicate copies.
- **Library Separation**: All CLI drivers in `scripts/` must be thin adapters delegating core logic to `lib/interface.py`.
- **Zero Regressions**: All 245 existing unit tests across `skills/anibon-timestamper-local/tests`, `skills/anibon-timestamper/tests`, and `tests/` must pass.
- **Python Version Compatibility**: All Python files must use `from __future__ import annotations` and stdlib-only tools without pytest.
- **Explicit Invocations**: Skill markdown (`SKILL.md`) references shared scripts directly without relying on fake local symlinks.

## Review Focus

1. **CLI Flag Parity**: `scripts/prepare_video.py` must support all flags from all 3 previous variants (`--no-storyboard`, `--vision`, `--format`, `--block`, `--overlap`, `--workspace`).
2. **Path Resolution**: `scripts/*.py` must resolve `_LIB_DIR` via `Path(__file__).resolve().parent.parent / "lib"`, working regardless of caller working directory.
3. **Skill Structure Gate**: `tests/test_skill_structure.py` must not fail on removed symlinks and must actively prevent duplicate script drift.
4. **Symlink Integrity**: Ensure no broken symlinks remain in any skill directory.
5. **Execution Verification**: Every consolidated script must execute with `--help` without throwing `ImportError` or `ModuleNotFoundError`.

---

### Task 1: Canonical `scripts/prepare_video.py`

**Files:**
- Create: `scripts/prepare_video.py`
- Test: `tests/test_prepare_video_cli.py`

**Interfaces:**
- Consumes:
  - `interface.correct_transcript`
  - `interface.download_storyboard`
  - `interface.download_transcript`
  - `interface.load_default_mappings`
  - `interface.load_transcript`
  - `interface.write_chunk_json`
  - `interface.write_chunk_txt`
  - `interface.write_chunk_xml`
  - `interface.process.vision`
- Produces:
  - CLI executable `scripts/prepare_video.py` with superset of flags: `url`, `[workspace]`, `--block`, `--overlap`, `--format` (`txt`, `json`, `xml`), `--no-storyboard`, `--vision`.

- [ ] **Step 1: Write the failing CLI test for `scripts/prepare_video.py`**

```python
# tests/test_prepare_video_cli.py
from __future__ import annotations
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN_ROOT / "scripts" / "prepare_video.py"


class TestPrepareVideoCLI(unittest.TestCase):
    def test_cli_help(self):
        self.assertTrue(SCRIPT.is_file(), "scripts/prepare_video.py must exist as a real file")
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PLUGIN_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--no-storyboard", res.stdout)
        self.assertIn("--vision", res.stdout)
        self.assertIn("--format", res.stdout)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_prepare_video_cli.py`
Expected: FAIL (file does not exist yet)

- [ ] **Step 3: Implement `scripts/prepare_video.py` using `interface`**

Consolidate all flags into `scripts/prepare_video.py`:
- Handle argument parsing: `url`, `workspace`, `--block`, `--overlap`, `--format`, `--no-storyboard`, `--vision`.
- Call `download_transcript(url, workspace)` and conditional `download_storyboard(url, workspace)`.
- Call `chunk_transcript(workspace, block, overlap, format)`.
- If `--vision`, invoke `interface.process.vision.run(workspace, url)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_prepare_video_cli.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/prepare_video.py tests/test_prepare_video_cli.py
git commit -m "feat(scripts): create canonical scripts/prepare_video.py using interface"
```

---

### Task 2: Deduplicate `prepare_video.py` across Skills

**Files:**
- Delete: `skills/anibon-timestamper-local/scripts/prepare_video.py`
- Delete: `skills/anibon-timestamper/scripts/prepare_video.py`
- Delete: `skills/cleaning-auto-transcripts/scripts/prepare_video.py`
- Modify: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `scripts/prepare_video.py`
- Produces: Clean tree where `prepare_video.py` has exactly 1 file representation.

- [ ] **Step 1: Write test assertion in `tests/test_skill_structure.py` for zero `prepare_video.py` copies in skills**

Add check in `test_skill_structure.py`:
```python
    def test_no_vendored_prepare_video_duplicates(self):
        dups = list(PLUGIN_ROOT.glob("skills/*/scripts/prepare_video.py"))
        self.assertEqual(dups, [], f"Redundant prepare_video.py found in skills: {dups}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_no_vendored_prepare_video_duplicates`
Expected: FAIL with 3 duplicates detected

- [ ] **Step 3: Remove the 3 duplicate copies**

Delete:
- `skills/anibon-timestamper-local/scripts/prepare_video.py`
- `skills/anibon-timestamper/scripts/prepare_video.py`
- `skills/cleaning-auto-transcripts/scripts/prepare_video.py`

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_no_vendored_prepare_video_duplicates`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u
git add tests/test_skill_structure.py
git commit -m "refactor(skills): remove duplicate prepare_video.py files across skills"
```

---

### Task 3: Clean up Symlink Web in Skills

**Files:**
- Remove symlinks:
  - `skills/anibon-timestamper/scripts/analyze_555.py`
  - `skills/anibon-timestamper/scripts/audit_gaps.py`
  - `skills/anibon-timestamper/scripts/check_sections.py`
  - `skills/anibon-timestamper/scripts/pack_timestamps.py`
  - `skills/anibon-timestamper/scripts/process_chunks_local.py`
  - `skills/anibon-timestamper/scripts/validate_tags.py`
  - `skills/anibon-timestamper/scripts/whisper_dispatcher.py`
  - `skills/anibon-timestamper-local/scripts/analyze_555.py`
  - `skills/anibon-timestamper-local/scripts/audit_gaps.py`
  - `skills/anibon-timestamper-local/scripts/check_sections.py`
  - `skills/anibon-timestamper-local/scripts/fetch_fgo_db.py`
  - `skills/anibon-timestamper-local/scripts/fetch_ygo_db.py`
  - `skills/anibon-timestamper-local/scripts/pack_timestamps.py`
  - `skills/anibon-timestamper-local/scripts/validate_tags.py`
  - `skills/anibon-timestamper-local/scripts/whisper_dispatcher.py`
- Modify: `tests/test_skill_structure.py:174-184`
- Modify: `skills/anibon-timestamper/tests/*.py` (update imports from root `scripts/` if importing via test runner)

**Interfaces:**
- Consumes: Canonical scripts in root `scripts/`
- Produces: Zero deceptive symlinks in skill scripts directories.

- [ ] **Step 1: Update `tests/test_skill_structure.py` to assert no symlinks exist in skill scripts**

Replace `test_no_dead_or_divergent_script_copies` symlink check:
```python
    def test_no_symlinked_scripts_in_skills(self):
        symlinks = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/scripts/*.py")
            if p.is_symlink()
        ]
        self.assertEqual(symlinks, [], f"Deceptive script symlinks found in skills: {symlinks}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_no_symlinked_scripts_in_skills`
Expected: FAIL (15 symlinks detected)

- [ ] **Step 3: Remove all 15 script symlinks from `skills/*/scripts/`**

Remove symlinks from `skills/anibon-timestamper/scripts/` and `skills/anibon-timestamper-local/scripts/`.

- [ ] **Step 4: Update skill test runners to import from root `scripts/`**

Ensure `skills/anibon-timestamper/tests/test_pack_timestamps.py`, `test_validate_tags.py`, `test_align_live_chat.py`, and `test_analyze_555_emoji.py` add `PLUGIN_ROOT / "scripts"` to `sys.path` when testing shared scripts.

- [ ] **Step 5: Run tests to verify all pass**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts:scripts python3 -m unittest discover -s skills/anibon-timestamper-local/tests && \
PYTHONPATH=lib:skills/anibon-timestamper/scripts:scripts python3 -m unittest discover -s skills/anibon-timestamper/tests && \
PYTHONPATH=lib:scripts python3 -m unittest discover -s tests
```
Expected: PASS (all tests pass)

- [ ] **Step 6: Commit**

```bash
git add -u
git add tests/test_skill_structure.py
git commit -m "refactor(skills): eliminate deceptive symlink web in skills/*/scripts"
```

---

### Task 4: Align SKILL.md Execution Documentation

**Files:**
- Modify: `skills/anibon-timestamper/SKILL.md`
- Modify: `skills/anibon-timestamper-local/SKILL.md`
- Modify: `skills/cleaning-auto-transcripts/SKILL.md`

**Interfaces:**
- Consumes: Real canonical paths for CLI tools.
- Produces: Updated markdown documentation instructing agents to run `python3 scripts/<name>.py` (or `$PLUGIN_ROOT/scripts/<name>.py`).

- [ ] **Step 1: Inspect references to `scripts/` in `SKILL.md` files**

Scan for `prepare_video.py`, `pack_timestamps.py`, `check_sections.py` in skill docs.

- [ ] **Step 2: Update paths in `SKILL.md` to reference root scripts or skill-owned scripts directly**

Ensure agent commands clearly specify root pipeline utilities (`scripts/prepare_video.py`, `scripts/pack_timestamps.py`) or skill scripts (`skills/anibon-timestamper-local/scripts/process_chunks_local.py`).

- [ ] **Step 3: Run skill structure validation test**

Run: `python3 -m unittest tests/test_skill_structure.py`
Expected: PASS (all frontmatter and skill structure tests pass)

- [ ] **Step 4: Commit**

```bash
git add skills/anibon-timestamper/SKILL.md skills/anibon-timestamper-local/SKILL.md skills/cleaning-auto-transcripts/SKILL.md
git commit -m "docs(skills): update SKILL.md script execution paths to canonical locations"
```

---

### Task 5: Full Repository Verification & Push

**Files:**
- Verify: All files in repo.

- [ ] **Step 1: Run complete unit test suite across all packages**

```bash
PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts python3 -m unittest discover -s /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/tests && \
PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts python3 -m unittest discover -s /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/tests && \
PYTHONPATH=/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib:/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts python3 -m unittest discover -s /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests
```
Expected: All 246+ tests PASS with 0 failures and 0 errors.

- [ ] **Step 2: Test CLI help execution for all root scripts**

```bash
for f in anibon-stream-synthesis/scripts/*.py; do
    PYTHONPATH=anibon-stream-synthesis/lib python3 "$f" --help > /dev/null || echo "Failed: $f"
done
```
Expected: Clean exit code 0 for all scripts.

- [ ] **Step 3: Push commit to remote branch**

```bash
git -C anibon-stream-synthesis push origin feat/chaining-weight-signal-detector
```
Expected: Successfully pushed to GitHub.
