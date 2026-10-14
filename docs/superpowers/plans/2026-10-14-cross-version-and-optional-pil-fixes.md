# Cross-Version Python 3.9–3.14 & Optional Pillow Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended via `agy --model "Gemini 3.8 Flash (High)"`) or superpowers:executing-plans (using Antigravity native tools: `view_file`, `replace_file_content`, `multi_replace_file_content`, `write_to_file`, `run_command`) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `NameError: name 'Any' is not defined` crash in `vision_verify.py` on Python 3.9–3.13 and guard all top-level `from PIL import ...` imports across `multimodal.py`, `unpack_storyboard.py`, `extract_visual_livechat.py`, and their unit tests so every CLI script and all 4 test suites run cleanly across Python 3.9, 3.12, and 3.14 with zero third-party packages installed.

**Architecture:** Add `from __future__ import annotations` and `Any` to `vision_verify.py`, wrap top-level `PIL` imports in `try ... except ImportError` guards across all 3 production modules (`multimodal.py`, `unpack_storyboard.py`, `extract_visual_livechat.py`) with an `ffmpeg` crop fallback in `multimodal.py:sample_chunk_keyframes`, and add `@unittest.skipIf(Image is None, "Pillow not installed")` to the PIL-specific test methods in `test_unpack_storyboard.py` and `test_extract_visual_livechat.py`.

**Tech Stack:** Python 3.9–3.14 standard library (`__future__.annotations`, `typing.Any`, `unittest`, `subprocess`), optional `Pillow` (`PIL`).

**Spec:** `README.md` ("Python 3.10+ (Standard library only)") and `GEMINI.md`

## Global Constraints

- Zero third-party packages required to import or run `process_chunks_local.py`, `unpack_storyboard.py`, `extract_visual_livechat.py`, or any of the 4 `unittest` suites.
- Full compatibility across Python 3.9 (`/usr/bin/python3`), Python 3.12 (`/opt/homebrew/bin/python3.12`), and Python 3.14 (`/opt/homebrew/bin/python3`).
- When `Pillow` (`PIL`) is installed, all image-cropping and visual-chat layout detection tests must execute normally without skipping.

## Review Focus

- Python 3.14 enables PEP 649 (deferred evaluation of annotations), which hid `args: Any` in `vision_verify.py:252` when `Any` was missing from `from typing import ...`; testing on Python 3.9/3.12 catches this class of bug (tested in Task 1).
- `process_chunks_local.py:107` imports `from anibon.multimodal import ...` unconditionally at startup even in default text-only mode; an unguarded `from PIL import Image` in `multimodal.py:13` crashes `process_chunks_local.py` on any Python installation without `Pillow` (tested in Task 2).
- `unpack_storyboard.py` functions `extract_slides_from_mhtml_bytes`, `extract_slides_from_mhtml_file`, and `calculate_tile_bbox` use pure stdlib `bytes`/`int` math and must work even when `PIL` is absent (tested in Task 2).
- `test_unpack_storyboard.py` and `test_extract_visual_livechat.py` import `from PIL import Image` at module top level; guarding the import and decorating only the methods that construct `Image.new(...)` with `@unittest.skipIf(Image is None, ...)` allows all non-PIL tests in those files to run when `PIL` is missing (tested in Task 2).
- In `multimodal.py:sample_chunk_keyframes`, if `Image is None`, falling back to `ffmpeg -y -i <slide_file> -vf crop=320:180:<x>:<y> -frames:v 1 <out_tile>` preserves multimodal tile cropping even without `Pillow` (tested in Task 2).

## File Structure

- `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py` — Adds `from __future__ import annotations` and `Any` import so Python 3.9–3.13 imports cleanly.
- `skills/anibon-timestamper-local/scripts/anibon/multimodal.py` — Guards `from PIL import Image` with `try/except ImportError` and adds `ffmpeg` crop fallback in `sample_chunk_keyframes`.
- `skills/anibon-stream-activity/scripts/unpack_storyboard.py` & `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py` — Guards top-level `from PIL import ...` with `try/except ImportError`.
- `tests/test_unpack_storyboard.py` & `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py` — Guards top-level `from PIL import ...` and skips only `Image.new` test methods when `Image is None`.
- `tests/test_skill_structure.py` — Adds regression tests verifying every production module imports cleanly without `NameError` or unguarded `PIL` imports.

### Task 1: Fix `NameError: name 'Any' is not defined` in `vision_verify.py` on Python 3.9–3.13

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py:1-10,248-256`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py` and `skills/anibon-timestamper-local/tests/test_vision_verify.py`

**Interfaces:**
- Consumes: `from __future__ import annotations`, `from typing import Any, Callable, Dict, List, Optional, Union`
- Produces: `anibon.vision_verify.apply_vision_verify(stamps: List[str], workspace: Path, args: Any, model: str) -> List[str]` importable on Python 3.9–3.14

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_all_local_anibon_modules_import_cleanly` to `TestSkillStructure` in `tests/test_skill_structure.py`:

```python
    def test_all_local_anibon_modules_import_cleanly(self):
        vf = PLUGIN_ROOT / "skills/anibon-timestamper-local/scripts/anibon/vision_verify.py"
        txt = vf.read_text(encoding="utf-8")
        self.assertIn("from __future__ import annotations", txt)
        self.assertRegex(txt, r"from typing import [^\n]*\bAny\b")
```

- [ ] **Step 2: Run test on Python 3.12 (or 3.14) to verify it fails**

Run:
```bash
PYTHONPATH=lib /opt/homebrew/bin/python3.12 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL (`AssertionError: 'from __future__ import annotations' not found in ...`).

- [ ] **Step 3: Add `from __future__ import annotations` and `Any` to `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py`**

In `skills/anibon-timestamper-local/scripts/anibon/vision_verify.py:1-10`, replace lines 1–9 with:

```python
"""vision_verify.py — Ambiguous timestamp detection and visual ground truth verification."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
```

- [ ] **Step 4: Run test on both Python 3.12 and Python 3.14 to verify it passes**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts /opt/homebrew/bin/python3.12 -m unittest skills/anibon-timestamper-local/tests/test_vision_verify.py tests/test_skill_structure.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/vision_verify.py tests/test_skill_structure.py
git commit -m "fix(vision-verify): import Any and __future__.annotations for Python 3.9-3.13"
```

### Task 2: Guard Optional `PIL` Imports Across `multimodal.py`, `unpack_storyboard.py`, `extract_visual_livechat.py`, & Tests

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/multimodal.py:1-16,225-248`
- Modify: `skills/anibon-stream-activity/scripts/unpack_storyboard.py:1-16,64-95`
- Modify: `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py:15-25,144-160`
- Modify: `tests/test_unpack_storyboard.py:1-50`
- Modify: `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py:1-35`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`, `tests/test_unpack_storyboard.py`, `skills/anibon-timestamper-local/tests/test_multimodal.py`, `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py`

**Interfaces:**
- Consumes: optional `PIL.Image` (with `subprocess` `ffmpeg` crop fallback in `multimodal.py:sample_chunk_keyframes`)
- Produces: Zero-dependency import and execution across all production scripts and test suites when `PIL` is absent

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_no_unguarded_pil_imports` to `TestSkillStructure` in `tests/test_skill_structure.py`:

```python
    def test_no_unguarded_pil_imports(self):
        offenders = []
        for folder in ("lib", "scripts", "skills", "tests"):
            for p in (PLUGIN_ROOT / folder).rglob("*.py"):
                if p.is_symlink():
                    continue
                txt = p.read_text(encoding="utf-8")
                if re.search(r"^from PIL import\b", txt, re.MULTILINE):
                    offenders.append(str(p.relative_to(PLUGIN_ROOT)))
        self.assertEqual(offenders, [], f"Unguarded top-level PIL imports found: {offenders}")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib /opt/homebrew/bin/python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL listing the 5 files (`multimodal.py`, `unpack_storyboard.py`, `extract_visual_livechat.py`, `test_unpack_storyboard.py`, `test_extract_visual_livechat.py`).

- [ ] **Step 3: Guard `from PIL import ...` in all 5 files and add `ffmpeg` tile crop fallback in `multimodal.py`**

1. In `skills/anibon-timestamper-local/scripts/anibon/multimodal.py`:
   - Add `from __future__ import annotations` at line 2 and `import subprocess` at line 8.
   - Replace `from PIL import Image` at line 13 with:
```python
try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]
```
   - In `sample_chunk_keyframes` (around line 236), support both `Image` and `ffmpeg` fallback:
```python
            try:
                if Image is not None:
                    im = Image.open(slide_file)
                    tile = im.crop((col * 320, row * 180, (col + 1) * 320, (row + 1) * 180))
                    tile.save(out_tile, quality=95)
                else:
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", str(slide_file),
                            "-vf", f"crop=320:180:{col * 320}:{row * 180}",
                            "-frames:v", "1", "-q:v", "2", str(out_tile),
                        ],
                        capture_output=True,
                        check=True,
                        timeout=15,
                    )
            except Exception as e:
                print(f"[multimodal] tile crop error at {sec}s: {e}", file=sys.stderr)
                continue
```

2. In `skills/anibon-stream-activity/scripts/unpack_storyboard.py:13`:
   - Replace `from PIL import Image` with:
```python
try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]
```

3. In `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py:19`:
   - Replace `from PIL import Image, ImageFilter, ImageStat` with:
```python
try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:
    Image = ImageFilter = ImageStat = None  # type: ignore[assignment]
```

4. In `tests/test_unpack_storyboard.py:8`:
   - Replace `from PIL import Image` with `try: from PIL import Image except ImportError: Image = None` and decorate `test_crop_frame_at_second` with `@unittest.skipIf(Image is None, "Pillow not installed")`.

5. In `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py:6`:
   - Replace `from PIL import Image, ImageDraw` with `try: from PIL import Image, ImageDraw except ImportError: Image = ImageDraw = None` and decorate the layout-detection methods that call `Image.new(...)` with `@unittest.skipIf(Image is None, "Pillow not installed")`.

- [ ] **Step 4: Run all 4 test suites across Python 3.14, Python 3.12, and macOS Python 3.9**

Run:
```bash
for py in /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.12 /usr/bin/python3; do
  echo "=== Testing with $py ==="
  PYTHONPATH=lib:skills/anibon-timestamper/scripts:skills/anibon-stream-activity/scripts:skills/creating-highlight-video/scripts $py -m unittest discover -s tests -p "test_*.py" && \
  PYTHONPATH=lib:skills/anibon-timestamper-local/scripts $py -m unittest discover -s skills/anibon-timestamper-local/tests -p "test_*.py" && \
  PYTHONPATH=lib:skills/anibon-timestamper/scripts $py -m unittest discover -s skills/anibon-timestamper/tests -p "test_*.py" && \
  PYTHONPATH=lib:skills/anibon-livechat-analysis/scripts $py -m unittest discover -s skills/anibon-livechat-analysis/tests -p "test_*.py"
done
```
Expected: PASS (`0` errors, `0` failures) across all 4 suites on all 3 Python interpreters (`3.14`, `3.12`, and `3.9`).

- [ ] **Step 5: Commit**

```bash
git add skills/ tests/
git commit -m "fix(pil): guard optional Pillow imports and add ffmpeg tile crop fallback"