# Post-Review Polish & Invariant Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended via `agy --model "Gemini 3.8 Flash (High)"`) or superpowers:executing-plans (using Antigravity native tools: `view_file`, `replace_file_content`, `multi_replace_file_content`, `write_to_file`, `run_command`) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the remaining 10 `import pytest` dependencies across skill test suites, wrap bare skill test functions into `unittest.TestCase` classes so `unittest discover` runs every test, enforce the 3,500-byte YouTube comment ceiling (`GEMINI.md` Invariant #4) in `run_local_summarizer_pass()` and `finalize_and_assemble_timestamps()`, and add `from __future__ import annotations` across all 22 modules using PEP 604 `X | Y` type hints so macOS system `/usr/bin/python3` (3.9) never crashes on import.

**Architecture:** Convert the 15 skill-level test files (`skills/anibon-timestamper-local/tests/`, `skills/anibon-livechat-analysis/tests/`, `skills/anibon-timestamper/tests/`) to `unittest.TestCase` with `tempfile.TemporaryDirectory`, pipe both LLM and heuristic outputs in `finalize_and_assemble_timestamps()` through `enforce_byte_cap(limit=3500)` while keeping `assemble_parts()` unit-test signature backward-compatible, and prepend `from __future__ import annotations` to all modules using `|` union type syntax.

**Tech Stack:** Python 3.9+ / 3.10+ standard library (`unittest`, `tempfile`, `unittest.mock`, `__future__.annotations`).

**Spec:** `GEMINI.md` (Invariant #4: 3,500-byte ceiling) and `docs/superpowers/plans/2026-10-14-plan-restructure.md`

## Global Constraints

- Zero `import pytest` statements anywhere in `tests/` or `skills/*/tests/`.
- Every `test_*.py` file across root and skills must be discoverable and runnable via `python3 -m unittest discover`.
- All assembled YouTube comment blocks written to `anibon_timestamps.md` by `process_chunks_local.py` or `run_local_summarizer_pass()` must strictly remain `<= 3,500` UTF-8 bytes (`GEMINI.md` Invariant #4), while `assemble_parts(stamps, deduplicate=False)` preserves its default `enforce_byte_limit=False` signature so `test_assemble_parts_macro_grouping_avoids_over_splitting` continues to pass.
- Every `.py` file using PEP 604 `X | Y` or PEP 585 `list[...]` annotations in `lib/`, `scripts/`, and `skills/` must include `from __future__ import annotations` so hooks invoked by `/usr/bin/python3` (macOS Python 3.9) do not raise `TypeError` at import time.

## Review Focus

- `skills/anibon-timestamper-local/tests/test_summarizer.py::test_assemble_parts_macro_grouping_avoids_over_splitting` expects 4–6 parts on 200 synthetic stamps when `assemble_parts(stamps, deduplicate=False)` is called directly; keep `enforce_byte_limit: bool = False` as the default parameter on `assemble_parts()`, and apply `enforce_byte_cap()` in `run_local_summarizer_pass()` and `finalize_and_assemble_timestamps()` (tested in Task 2).
- `skills/anibon-livechat-analysis/tests/` imports `skills.anibon_livechat_analysis.scripts.*` via `conftest.py`'s `LiveChatPackageFinder`; when running under `unittest discover`, `conftest.py` is not auto-loaded unless imported by `skills/anibon-livechat-analysis/tests/__init__.py` (tested in Task 1).
- `skills/anibon-timestamper/tests/test_*.py` use bare `def test_*(tmp_path)` functions without `unittest.TestCase`, causing `unittest discover` to report `Ran 0 tests`; wrapping them in `unittest.TestCase` classes makes all 5 files execute (tested in Task 1).
- `from __future__ import annotations` must appear at the very top of each module (immediately after module docstring / shebang / encoding comment and before any other imports) or Python raises `SyntaxError: from __future__ imports must occur at the beginning of the file` (tested in Task 3).
- `test_domain_db.py` queries SQLite databases (`ygo_cards.db`, `atlas_fgo.db`, `pokemon.db`); if optional local `.db` binaries are not present in a clean checkout, tests should gracefully `self.skipTest("SQLite DB not bootstrapped")` when the DB file is absent rather than failing (tested in Task 1).

## File Structure

- `skills/anibon-timestamper-local/tests/test_{domain_db,knowledge_reader,phonetic_bridge,topic_scanner,transcript_source,vision_verify,world_sanitizer}.py` — Converted from `pytest` to `unittest.TestCase`.
- `skills/anibon-livechat-analysis/tests/{__init__,test_extract_visual_livechat,test_visual_chat_crop,test_visual_chat_dedup}.py` — Auto-loads `conftest` finder in `__init__.py` and converts all 3 test files from `pytest` to `unittest.TestCase`.
- `skills/anibon-timestamper/tests/{__init__,test_align_live_chat,test_analyze_555_emoji,test_detect_signals,test_pack_timestamps,test_validate_tags}.py` — Wraps bare `def test_*` functions into `unittest.TestCase` classes.
- `skills/anibon-timestamper-local/scripts/anibon/summarizer.py` & `skills/anibon-timestamper-local/scripts/process_chunks_local.py` — Enforces `enforce_byte_cap(limit=3500)` on `run_local_summarizer_pass()` and `finalize_and_assemble_timestamps()`.
- 22 Python modules across `lib/`, `scripts/`, and `skills/` — Updated with `from __future__ import annotations`.

### Task 1: Convert All 15 Skill Test Files to `unittest.TestCase` and Remove Remaining `pytest` Imports

**Files:**
- Modify: `skills/anibon-timestamper-local/tests/test_domain_db.py:1-32`
- Modify: `skills/anibon-timestamper-local/tests/test_knowledge_reader.py:1-132`
- Modify: `skills/anibon-timestamper-local/tests/test_phonetic_bridge.py:1-35`
- Modify: `skills/anibon-timestamper-local/tests/test_topic_scanner.py:1-30`
- Modify: `skills/anibon-timestamper-local/tests/test_transcript_source.py:1-40`
- Modify: `skills/anibon-timestamper-local/tests/test_vision_verify.py:1-202`
- Modify: `skills/anibon-timestamper-local/tests/test_world_sanitizer.py:1-35`
- Delete: `skills/anibon-timestamper-local/pytest.ini`
- Create: `skills/anibon-livechat-analysis/tests/__init__.py`
- Modify: `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py:1-268`
- Modify: `skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py:1-45`
- Modify: `skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py:1-129`
- Create: `skills/anibon-timestamper/tests/__init__.py`
- Modify: `skills/anibon-timestamper/tests/test_align_live_chat.py:1-120`
- Modify: `skills/anibon-timestamper/tests/test_analyze_555_emoji.py:1-110`
- Modify: `skills/anibon-timestamper/tests/test_detect_signals.py:1-60`
- Modify: `skills/anibon-timestamper/tests/test_pack_timestamps.py:1-138`
- Modify: `skills/anibon-timestamper/tests/test_validate_tags.py:1-208`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `unittest.TestCase`, `tempfile.TemporaryDirectory`, `unittest.mock.patch`
- Produces: Zero-dependency `unittest` discovery across `tests/`, `skills/anibon-timestamper-local/tests/`, `skills/anibon-timestamper/tests/`, and `skills/anibon-livechat-analysis/tests/`.

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_zero_pytest_imports_across_repo` to `TestSkillStructure` in `tests/test_skill_structure.py`:

```python
    def test_zero_pytest_imports_across_repo(self):
        offenders = []
        for p in list(PLUGIN_ROOT.glob("tests/**/*.py")) + list(PLUGIN_ROOT.glob("skills/*/tests/**/*.py")):
            txt = p.read_text(encoding="utf-8")
            if re.search(r"^\s*(?:import|from)\s+pytest\b", txt, re.MULTILINE):
                offenders.append(str(p.relative_to(PLUGIN_ROOT)))
        self.assertEqual(offenders, [], f"Test files still importing pytest: {offenders}")
        self.assertFalse((PLUGIN_ROOT / "skills/anibon-timestamper-local/pytest.ini").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib /opt/homebrew/bin/python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL listing the 10 skill test files still importing `pytest`.

- [ ] **Step 3: Convert all 15 skill test files to `unittest.TestCase` and add `__init__.py` bootstraps**

1. Create `skills/anibon-livechat-analysis/tests/__init__.py` that imports `conftest` so `LiveChatPackageFinder` is registered on `sys.meta_path` during `unittest discover`:
```python
from pathlib import Path
import sys

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: F401
```
2. Create `skills/anibon-timestamper/tests/__init__.py` that adds `skills/anibon-timestamper/scripts` and `lib` to `sys.path`:
```python
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_ROOT = _SKILL_DIR.parent.parent
for _p in (_SKILL_DIR / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
```
3. In the 7 `skills/anibon-timestamper-local/tests/test_*.py` files, 3 `skills/anibon-livechat-analysis/tests/test_*.py` files, and 5 `skills/anibon-timestamper/tests/test_*.py` files:
   - Remove `import pytest`.
   - Wrap top-level `def test_*` functions inside `class Test...(unittest.TestCase):` methods (`def test_...(self):`).
   - Replace `tmp_path` parameters with `with tempfile.TemporaryDirectory() as _tmp: tmp_path = Path(_tmp)`.
   - Replace `with pytest.raises(Exc, match="..."):` with `with self.assertRaisesRegex(Exc, "..."):` and `with pytest.raises(Exc):` with `with self.assertRaises(Exc):`.
   - In `test_domain_db.py`, check `DEFAULT_YGO_DB.is_file()`, `DEFAULT_FGO_DB.is_file()`, and `DEFAULT_POKE_DB.is_file()` and call `self.skipTest("SQLite DB not present")` if absent.
   - Delete `skills/anibon-timestamper-local/pytest.ini`.

- [ ] **Step 4: Run all 4 test suites to verify they pass**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper/scripts:skills/anibon-stream-activity/scripts:skills/creating-highlight-video/scripts /opt/homebrew/bin/python3 -m unittest discover -s tests -p "test_*.py" -v && \
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts /opt/homebrew/bin/python3 -m unittest discover -s skills/anibon-timestamper-local/tests -p "test_*.py" -v && \
PYTHONPATH=lib:skills/anibon-timestamper/scripts /opt/homebrew/bin/python3 -m unittest discover -s skills/anibon-timestamper/tests -p "test_*.py" -v && \
PYTHONPATH=lib:skills/anibon-livechat-analysis/scripts /opt/homebrew/bin/python3 -m unittest discover -s skills/anibon-livechat-analysis/tests -p "test_*.py" -v
```
Expected: PASS across all 4 test suites with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add skills/ tests/test_skill_structure.py
git commit -m "refactor(tests): convert all 15 skill test files to stdlib unittest"
```

### Task 2: Enforce 3,500-Byte Ceiling in `run_local_summarizer_pass()` & `finalize_and_assemble_timestamps()`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/summarizer.py:135-142`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:92-96,291-298`
- Modify: `skills/anibon-timestamper-local/tests/test_summarizer.py`
- Modify: `skills/anibon-timestamper-local/tests/test_pipeline_e2e.py`
- Test: `skills/anibon-timestamper-local/tests/test_summarizer.py` and `skills/anibon-timestamper-local/tests/test_pipeline_e2e.py`

**Interfaces:**
- Consumes: `anibon.summarizer.enforce_byte_cap(md: str, limit: int = 3500) -> str`
- Produces: Guaranteed `<= 3500` UTF-8 bytes per section in `run_local_summarizer_pass()` and `finalize_and_assemble_timestamps()`

- [ ] **Step 1: Write the failing test in `skills/anibon-timestamper-local/tests/test_summarizer.py` and `test_pipeline_e2e.py`**

In `skills/anibon-timestamper-local/tests/test_summarizer.py`, add:
```python
    def test_run_local_summarizer_pass_enforces_byte_cap(self):
        from unittest.mock import patch
        from anibon.summarizer import run_local_summarizer_pass

        stamps = [f"00:{i:02d}:00 - [Talk] " + ("ก" * 120) for i in range(25)]
        fake_llm_output = (
            "Part 1 | Start: 00:00:00 | Summary: เปิดสตรีมคุยข่าวใหญ่\n"
            "Part 2 | Start: 00:20:00 | Summary: ปิดท้ายสตรีม\n"
        )
        with patch("anibon.summarizer.call_local", return_value=fake_llm_output):
            md = run_local_summarizer_pass("[http://127.0.0.1:1234](http://127.0.0.1:1234)", "test-model", stamps)
        self.assertIsNotNone(md)
        for part in md.split("\n\n"):
            self.assertLessEqual(len(part.encode("utf-8")), 3500)
```

In `skills/anibon-timestamper-local/tests/test_pipeline_e2e.py`, add:
```python
    def test_finalize_and_assemble_enforces_3500_byte_cap(self):
        import tempfile
        from pathlib import Path
        from process_chunks_local import finalize_and_assemble_timestamps

        stamps = [f"00:{i:02d}:00 - [Talk] " + ("ข" * 120) for i in range(30)]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            out_md, _ = finalize_and_assemble_timestamps(
                workspace=ws,
                all_timestamps=stamps,
                endpoint="[http://127.0.0.1:1234](http://127.0.0.1:1234)",
                model="test-model",
                temperature=0.1,
                block_size=2400,
                no_summarizer_pass=True,
            )
            content = out_md.read_text(encoding="utf-8")
            for block in content.split("\n\n"):
                if block.strip():
                    self.assertLessEqual(len(block.encode("utf-8")), 3500)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts /opt/homebrew/bin/python3 -m unittest skills/anibon-timestamper-local/tests/test_summarizer.py skills/anibon-timestamper-local/tests/test_pipeline_e2e.py -v
```
Expected: FAIL (`AssertionError: 7606 not less than or equal to 3500`).

- [ ] **Step 3: Apply `enforce_byte_cap()` in `run_local_summarizer_pass()` and `finalize_and_assemble_timestamps()`**

1. In `skills/anibon-timestamper-local/scripts/anibon/summarizer.py:138`, change:
```python
            if rendered_parts:
                return enforce_byte_cap("\n\n".join(rendered_parts))
```
2. In `skills/anibon-timestamper-local/scripts/process_chunks_local.py`:
   - Import `enforce_byte_cap` from `anibon.summarizer` at line 92.
   - In `finalize_and_assemble_timestamps()` at line 297 (right before `out_md.write_text(assembled, encoding="utf-8")`), add:
```python
    assembled = enforce_byte_cap(assembled)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts /opt/homebrew/bin/python3 -m unittest skills/anibon-timestamper-local/tests/test_summarizer.py skills/anibon-timestamper-local/tests/test_pipeline_e2e.py -v
```
Expected: PASS (including `test_assemble_parts_macro_grouping_avoids_over_splitting`).

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/summarizer.py skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper-local/tests/test_summarizer.py skills/anibon-timestamper-local/tests/test_pipeline_e2e.py
git commit -m "fix(summarizer): enforce 3500B ceiling on LLM and heuristic final assembly"
```

### Task 3: Add `from __future__ import annotations` Across All 22 PEP 604/585 Modules

**Files:**
- Modify: `lib/anibon/{analyzer,chunk_io,cleaner,parsers,vision,ytdlp}.py`
- Modify: `scripts/{check_sections,pack_timestamps}.py`
- Modify: `skills/anibon-livechat-analysis/scripts/{extract_visual_livechat,visual_chat_crop,visual_chat_dedup}.py`
- Modify: `skills/anibon-stream-activity/scripts/{align_activity_timeline,extract_activity_timeline,unpack_storyboard}.py`
- Modify: `skills/anibon-timestamper/scripts/{align_live_chat,detect_signals,validate_part_coherence}.py`
- Modify: `skills/anibon-timestamper-local/scripts/{anibon/parity_gates,signal_detector}.py`
- Modify: `skills/cleaning-auto-transcripts/scripts/{clean_garbled_english,update_garbled_dictionary}.py`
- Modify: `skills/creating-highlight-video/scripts/plan_highlight.py`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `from __future__ import annotations`
- Produces: Python 3.9+ import compatibility across all `lib/`, `scripts/`, and `skills/` modules (including when macOS `hooks.json` invokes `/usr/bin/python3`).

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_future_annotations_in_pep604_modules` to `TestSkillStructure` in `tests/test_skill_structure.py`:

```python
    def test_future_annotations_in_pep604_modules(self):
        missing = []
        type_re = re.compile(r"(->\s*[^:\n]*\|)|(:[^=\n]*\|\s*(?:None|int|float|str|list|dict|tuple|Path))|(\b(?:list|dict|tuple|set)\[)")
        for folder in ("lib", "scripts", "skills"):
            for p in (PLUGIN_ROOT / folder).rglob("*.py"):
                if p.is_symlink() or "/tests/" in str(p):
                    continue
                txt = p.read_text(encoding="utf-8")
                if type_re.search(txt) and "from __future__ import annotations" not in txt:
                    missing.append(str(p.relative_to(PLUGIN_ROOT)))
        self.assertEqual(missing, [], f"Modules using PEP 604/585 annotations without __future__.annotations: {missing}")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib /opt/homebrew/bin/python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL listing the 22 modules.

- [ ] **Step 3: Insert `from __future__ import annotations` after module docstrings in all 22 modules**

Use `ast.parse()` to find the end line of any module docstring (or after `#!` / `# -*-` header comments if no docstring) and insert `from __future__ import annotations` at the top of each of the 22 files:
- `lib/anibon/{analyzer,chunk_io,cleaner,parsers,vision,ytdlp}.py`
- `scripts/{check_sections,pack_timestamps}.py`
- `skills/anibon-livechat-analysis/scripts/{extract_visual_livechat,visual_chat_crop,visual_chat_dedup}.py`
- `skills/anibon-stream-activity/scripts/{align_activity_timeline,extract_activity_timeline,unpack_storyboard}.py`
- `skills/anibon-timestamper/scripts/{align_live_chat,detect_signals,validate_part_coherence}.py`
- `skills/anibon-timestamper-local/scripts/{anibon/parity_gates,signal_detector}.py`
- `skills/cleaning-auto-transcripts/scripts/{clean_garbled_english,update_garbled_dictionary}.py`
- `skills/creating-highlight-video/scripts/plan_highlight.py`

- [ ] **Step 4: Run tests under both Homebrew Python 3.14 and macOS system `/usr/bin/python3` (3.9)**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper/scripts:skills/anibon-stream-activity/scripts:skills/creating-highlight-video/scripts /opt/homebrew/bin/python3 -m unittest discover -s tests -p "test_*.py" -v && \
PYTHONPATH=lib /usr/bin/python3 -m unittest tests/test_cleaner_v2.py tests/test_check_sections.py tests/test_skill_structure.py -v
```
Expected: PASS on both Python 3.14 and macOS system Python 3.9.

- [ ] **Step 5: Commit**

```bash
git add lib/ scripts/ skills/ tests/test_skill_structure.py
git commit -m "fix(compat): add __future__.annotations to all PEP 604/585 modules"