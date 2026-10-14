# Anibon Stream Synthesis Refactor, Restructure & Optimize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended via `agy --model "Gemini 3.8 Flash (High)"`) or superpowers:executing-plans (using Antigravity native tools: `view_file`, `replace_file_content`, `multi_replace_file_content`, `write_to_file`, `run_command`) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut ~10,079 duplicate/dead Python lines and ~9,572 duplicate JSON/Markdown lines, fix v2 dictionary loading and XML double-escaping bugs, optimize O(N*P) regex normalization hot loops, drop the undeclared `pytest` dependency, and upgrade all Antigravity (`agy`) model pins to `Gemini 3.8 Flash (High)`.

**Architecture:** Consolidate all shared library modules into `lib/anibon/` and all shared JSON dictionaries into root `resources/`. Replace copy-pasted per-skill `scripts/anibon/` packages and duplicated CLI scripts with `sys.path` imports or thin symlinks, pre-compile and cache the 3,359 phonetic replacement patterns in `lib/anibon/cleaner.py`, extract a single post-loop assembly helper in `process_chunks_local.py`, and standardize all `agy` CLI invocations on `Gemini 3.8 Flash (High)`.

**Tech Stack:** Python 3.10+ (standard library only: `re`, `json`, `shutil`, `pkgutil`, `sqlite3`, `concurrent.futures`, `unittest`, `tempfile`, `xml.etree.ElementTree`, `pathlib`), Antigravity CLI (`agy --model "Gemini 3.8 Flash (High)"`).

**Spec:** `PLAN-restructure.md`, `specs/pipeline-fix-spec.md`, `GEMINI.md`

## Global Constraints

- Python 3.10+ standard library only (`unittest`, `tempfile`, `unittest.mock`); zero external pip dependencies required to run scripts or tests.
- Backward-compatible CLI entry points and imports (`process_chunks_local`, `signal_detector`, `detect_signals`, `pack_timestamps`, `check_sections`, `whisper_dispatcher`).
- Streamer identity invariant: exclusively `ปู่โบ๊ต` (never `ปู่บอท`, `ลุงบอท`, `ปู่โบต`).
- YouTube comment block target ceiling: <= 3,500 UTF-8 bytes (hard cap 4,500 UTF-8 bytes); never drop proper nouns to fit byte limits.
- Antigravity model invariant (`GEMINI.md`): always use `Gemini 3.8 Flash (High)` (never pin to older `Gemini 3.5` or `Gemini 3.6 Flash`).

## Review Focus

- `garbled_replacements.json` v2 schema (`"mappings": {"Target": ["pat1"]}`) + root-level flat entries + v1 `"replacements"` fallback must all load in `lib/anibon/cleaner.py` (tested in Task 2).
- Word-boundary regex patterns (`\b2SKO\b`) inside `garbled_replacements.json` must not be escaped into literal `\\b` by `re.escape()` during normalization (tested in Task 2).
- XML chunk cleaning (`_clean_xml_chunk`) must not double-escape `&`, `<`, `>` into `&amp;amp;` when `ElementTree.write()` serializes text (tested in Task 2).
- Root and skill test suites must run cleanly via `python3 -m unittest` when `pytest` is not installed (tested in Task 1 & Task 5).
- `agy` subprocess calls and documentation must consistently pass `--model "Gemini 3.8 Flash (High)"` with no remaining `Gemini 3.6 Flash` pins (tested in Task 6).

## File Structure

- `lib/anibon/{__init__,analyzer,chunk_io,cleaner,corruption,markdown,parsers,resources,time,vision,ytdlp}.py` — Canonical shared library for all skills and root scripts.
- `resources/{asr_garbled_patterns,channels,default_mappings,emoji_dictionary,filename_game_map,garbled_replacements,knowledge,signal_config,tag_macros,tone_hints}.json` — Single source of truth for all dictionaries and signal configs, resolved via `anibon.resources.resource_path()`.
- `agents/{anibon-chunk-timestamper,anibon-garbled-notes,anibon-summarizer}.md` — Canonical agent definitions registered by `.opencode/plugins/anibon-stream-synthesis.mjs`.
- `scripts/{analyze_555,assembly-gate,audit_gaps,check_sections,pack_timestamps,preflight-gate,validate_tags,whisper_dispatcher}.py` — Canonical shared CLI scripts.
- `skills/anibon-timestamper-local/scripts/process_chunks_local.py` — Canonical local LLM/VLM orchestrator with unified `finalize_and_assemble_timestamps()`.
- `tests/test_*.py` — Zero-dependency `unittest.TestCase` verification suite.

### Task 1: Unify `lib/anibon/` and Delete 5 Vendored `scripts/anibon/` Copies

**Files:**
- Modify: `lib/anibon/resources.py:1-42`
- Modify: `lib/anibon/ytdlp.py:1-119`
- Create: `lib/anibon/vision.py` (moved from `skills/anibon-timestamper-local/scripts/_vision.py`)
- Modify: `skills/anibon-timestamper-local/scripts/anibon/__init__.py:1-3`
- Delete: `skills/anibon-local-transcription/scripts/anibon/` (9 files)
- Delete: `skills/antigravity-vision-proxy/scripts/anibon/` (9 files)
- Delete: `skills/cleaning-auto-transcripts/scripts/anibon/` (9 files)
- Delete: `skills/anibon-timestamper/scripts/anibon/` (9 files)
- Delete: `skills/anibon-timestamper-local/scripts/anibon/{analyzer,chunk_io,cleaner,corruption,markdown,parsers,resources,time,ytdlp}.py` (9 duplicate core files)
- Delete: `skills/{anibon-timestamper-local,antigravity-vision-proxy,cleaning-auto-transcripts}/scripts/_vision.py` (3 files)
- Modify: `tests/test_skill_structure.py:1-88`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `anibon.resources.resource_path(name: str) -> Path`
  - `anibon.resources.plugin_root() -> Path`
  - `anibon.ytdlp.ytdlp_cmd() -> list[str]`
  - `anibon.vision.extract_frames(video_path: Path, output_dir: Path, timestamps: list[int]) -> list[Path]`

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Use Antigravity `write_to_file` or `replace_file_content` on `tests/test_skill_structure.py` to convert it from `pytest` to `unittest.TestCase` and add `test_no_vendored_core_anibon_duplicates`:

```python
import os
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"


class TestSkillStructure(unittest.TestCase):
    def test_no_vendored_core_anibon_duplicates(self):
        core_mods = {
            "analyzer.py", "chunk_io.py", "cleaner.py", "corruption.py",
            "markdown.py", "parsers.py", "resources.py", "time.py", "ytdlp.py",
        }
        dups = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/scripts/anibon/*.py")
            if p.name in core_mods and not p.is_symlink()
        ]
        vision_dups = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/scripts/_vision.py")
            if not p.is_symlink()
        ]
        self.assertEqual(dups, [], f"Duplicate core anibon modules found: {dups}")
        self.assertEqual(vision_dups, [], f"Duplicate _vision.py modules found: {vision_dups}")
```

- [ ] **Step 2: Run test to verify it fails**

Run via Antigravity `run_command`:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL with 45 duplicate core files and 3 `_vision.py` files listed.

- [ ] **Step 3: Implement unified `lib/anibon/ytdlp.py`, `lib/anibon/resources.py`, and `lib/anibon/vision.py`, extend `anibon.__path__`, and delete the 48 duplicate files**

1. In `lib/anibon/ytdlp.py`, add `shutil.which` fallback so both standalone `yt-dlp` binary and `python3 -m yt_dlp` work:
```python
import shutil
import subprocess
import sys
from pathlib import Path


def ytdlp_cmd() -> list[str]:
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]
```
Replace `[sys.executable, "-m", "yt_dlp", ...]` at lines 31, 63, and 91 of `lib/anibon/ytdlp.py` with `[*ytdlp_cmd(), ...]`.

2. In `skills/anibon-timestamper-local/scripts/anibon/__init__.py`, bridge `lib/anibon` and local submodules via `pkgutil.extend_path`:
```python
import pkgutil
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[4] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

__path__ = pkgutil.extend_path(__path__, __name__)
```

3. Move `skills/anibon-timestamper-local/scripts/_vision.py` to `lib/anibon/vision.py`, update `prepare_video.py` imports from `import _vision` to `from anibon import vision as _vision`, and delete the 45 duplicate core `anibon/*.py` files and 3 `_vision.py` files:
```bash
cp skills/anibon-timestamper-local/scripts/_vision.py lib/anibon/vision.py
rm -rf skills/anibon-local-transcription/scripts/anibon \
       skills/antigravity-vision-proxy/scripts/anibon \
       skills/cleaning-auto-transcripts/scripts/anibon \
       skills/anibon-timestamper/scripts/anibon
rm -f skills/anibon-timestamper-local/scripts/anibon/{analyzer,chunk_io,cleaner,corruption,markdown,parsers,resources,time,ytdlp}.py
rm -f skills/{anibon-timestamper-local,antigravity-vision-proxy,cleaning-auto-transcripts}/scripts/_vision.py
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/anibon skills tests/test_skill_structure.py
git commit -m "refactor(lib): consolidate 48 duplicate anibon and vision modules into lib/anibon"
```

### Task 2: Fix V2 Schema Bug, `\b` Word Boundaries, XML Double-Escaping, & Regex Cache Thrashing in `lib/anibon/cleaner.py`

**Files:**
- Modify: `lib/anibon/cleaner.py:1-98`
- Modify: `skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py:1-167`
- Modify: `skills/anibon-timestamper-local/scripts/signal_detector.py:58-108,210-232`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:141-218`
- Modify: `scripts/pack_timestamps.py:47-65`
- Modify: `scripts/whisper_dispatcher.py:127-164`
- Create: `tests/test_cleaner_v2.py`
- Test: `tests/test_cleaner_v2.py`

**Interfaces:**
- Consumes: `anibon.resources.resource_path(name: str) -> Path`
- Produces:
  - `anibon.cleaner.load_replacements(path: Path | None = None) -> list[tuple[re.Pattern, str]]`
  - `anibon.cleaner.clean_text(text: str, compiled: list[tuple[re.Pattern, str]] | None = None) -> str`
  - `anibon.cleaner.clean_text_with_count(text: str, compiled: list[tuple[re.Pattern, str]] | None = None) -> tuple[str, int]`

- [ ] **Step 1: Write the failing test in `tests/test_cleaner_v2.py`**

```python
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from anibon.cleaner import clean_text, clean_text_with_count, load_replacements
from anibon.resources import resource_path


class TestCleanerV2(unittest.TestCase):
    def test_v2_schema_and_word_boundary_patterns(self):
        compiled = load_replacements(resource_path("garbled_replacements.json"))
        self.assertGreater(len(compiled), 2000)
        cleaned, count = clean_text_with_count("เล่น 2SKO กับปู่บอท", compiled)
        self.assertIn("2XKO", cleaned)
        self.assertIn("ปู่โบ๊ต", cleaned)
        self.assertGreaterEqual(count, 2)

    def test_xml_cleaning_does_not_double_escape_ampersand(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = Path(tmp) / "chunk_01.xml"
            xml_path.write_text(
                '<transcript start_sec="0"><item timestamp="00:00:01">Tom &amp; Jerry เล่น 2SKO</item></transcript>',
                encoding="utf-8",
            )
            tree = ET.parse(xml_path)
            for item in tree.getroot().iter("item"):
                item.text = clean_text((item.text or "").strip())
            tree.write(xml_path, encoding="utf-8", xml_declaration=False)
            raw_out = xml_path.read_text(encoding="utf-8")
            self.assertIn("Tom &amp; Jerry เล่น 2XKO", raw_out)
            self.assertNotIn("&amp;amp;", raw_out)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_cleaner_v2.py -v
```
Expected: FAIL with `ImportError: cannot import name 'clean_text_with_count'` and `len(compiled) == 0`.

- [ ] **Step 3: Implement unified v1+v2+root `load_replacements` with pre-compiled caching in `lib/anibon/cleaner.py`, fix XML double-escaping in `clean_garbled_english.py`, and route all 5 callers through `anibon.cleaner`**

1. Replace `lib/anibon/cleaner.py` with:
```python
import json
import re
from pathlib import Path
from anibon.resources import resource_path

_REGEX_META_RE = re.compile(r"\\b|\\B|\\d|\\w|\\s|[\[\]()^$?*+{|]")
_SPEAKER_SCRUB_RE = re.compile(r"(?:ปู่บอท|ลุงบอท|ปู่โบต)")
_CACHE: dict[Path, list[tuple[re.Pattern, str]]] = {}


def _compile_pattern(pat: str) -> re.Pattern:
    expr = pat if _REGEX_META_RE.search(pat) else re.escape(pat)
    return re.compile(expr, re.IGNORECASE)


def load_replacements(path: Path | None = None) -> list[tuple[re.Pattern, str]]:
    target_path = Path(path) if path else resource_path("garbled_replacements.json")
    if target_path in _CACHE:
        return _CACHE[target_path]
    if not target_path.is_file():
        return []

    data = json.loads(target_path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []

    if isinstance(data.get("mappings"), dict):
        for canonical, patterns in data["mappings"].items():
            pats = patterns if isinstance(patterns, list) else [patterns]
            for p in pats:
                if p and str(p).strip():
                    pairs.append((str(p).strip(), str(canonical).strip()))

    for k, v in data.items():
        if k in ("version", "description", "note", "mappings", "replacements"):
            continue
        if isinstance(v, str) and k.strip():
            pairs.append((k.strip(), v.strip()))
        elif isinstance(v, list):
            for p in v:
                if p and str(p).strip():
                    pairs.append((str(p).strip(), k.strip()))

    for entry in data.get("replacements", []):
        pat = entry.get("pattern", "").strip()
        rep = entry.get("replacement", "").strip()
        if pat:
            pairs.append((pat, rep))

    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    compiled: list[tuple[re.Pattern, str]] = [(_SPEAKER_SCRUB_RE, "ปู่โบ๊ต")]
    for pat, rep in pairs:
        try:
            compiled.append((_compile_pattern(pat), rep))
        except re.error:
            continue

    _CACHE[target_path] = compiled
    return compiled


def clean_text_with_count(
    text: str, compiled: list[tuple[re.Pattern, str]] | None = None
) -> tuple[str, int]:
    if not text:
        return "", 0
    active = compiled if compiled is not None else load_replacements()
    total_changes = 0
    for pattern, replacement in active:
        text, n = pattern.subn(replacement, text)
        total_changes += n
    return text, total_changes


def clean_text(
    text: str, compiled: list[tuple[re.Pattern, str]] | None = None
) -> str:
    cleaned, _ = clean_text_with_count(text, compiled)
    return cleaned
```
Keep `clean_chunk`, `correct_transcript`, `load_asr_garbled_patterns`, and `scan_garbles` in `lib/anibon/cleaner.py`, pre-compiling patterns once before iterating over `transcript` in `correct_transcript`.

2. In `skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py`:
   - Import `load_replacements, clean_text, clean_chunk` from `anibon.cleaner`.
   - Delete `_escape_xml` and change line 85 from `item.text = _escape_xml(cleaned)` to `item.text = cleaned`.

3. In `scripts/pack_timestamps.py:47`, replace `_load_garbled_cleaner()` with `from anibon.cleaner import clean_text as _clean_desc`.

4. In `scripts/whisper_dispatcher.py:127`, replace `load_master_dictionary_matcher()` body with `from anibon.cleaner import load_replacements; return load_replacements()`.

5. In `skills/anibon-timestamper-local/scripts/signal_detector.py:210` (`normalize_transcript`) and `skills/anibon-timestamper-local/scripts/process_chunks_local.py:141` (`sanitize_and_audit_timestamps`), use `_compile_pattern(pat)` + `pattern.subn()` cached per `mappings` list instead of calling `re.findall(re.escape(pat), ...)` + `re.sub(re.escape(pat), ...)` inside the per-chunk loop.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_cleaner_v2.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/anibon/cleaner.py skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py skills/anibon-timestamper-local/scripts/signal_detector.py skills/anibon-timestamper-local/scripts/process_chunks_local.py scripts/pack_timestamps.py scripts/whisper_dispatcher.py tests/test_cleaner_v2.py
git commit -m "fix(cleaner): support v2 mappings, preserve regex boundaries, and fix XML double-escaping"
```

### Task 3: Deduplicate JSON Dictionaries & `.opencode/agents/` Definitions

**Files:**
- Move: `skills/anibon-timestamper/resources/{knowledge,channels,tone_hints,emoji_dictionary}.json` -> `resources/`
- Modify: `resources/default_mappings.json` (merge any extra entries from `skills/anibon-timestamper-local/resources/default_mappings.json`)
- Delete: `skills/anibon-timestamper/resources/` (10 files)
- Delete: `skills/anibon-timestamper-local/resources/` (2 files)
- Delete: `skills/cleaning-auto-transcripts/resources/` (1 file)
- Modify: `.opencode/plugins/anibon-stream-synthesis.mjs:11`
- Modify: `agents/{anibon-chunk-timestamper,anibon-garbled-notes,anibon-summarizer}.md`
- Delete: `.opencode/agents/` (3 files)
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `anibon.resources.resource_path(name: str) -> Path`
- Produces: Single source of truth in `resources/*.json` and `agents/*.md`

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

Add `test_no_duplicate_skill_resources_or_opencode_agents` to `TestSkillStructure` in `tests/test_skill_structure.py`:

```python
    def test_no_duplicate_skill_resources_or_opencode_agents(self):
        skill_jsons = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/resources/*.json")
            if not p.is_symlink()
        ]
        self.assertEqual(skill_jsons, [], f"Duplicate skill resource JSONs found: {skill_jsons}")
        self.assertFalse((PLUGIN_ROOT / ".opencode" / "agents").exists())
        for required in ("garbled_replacements.json", "default_mappings.json", "knowledge.json", "signal_config.json"):
            self.assertTrue((PLUGIN_ROOT / "resources" / required).is_file(), f"Missing root resource: {required}")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL with 13 duplicate skill JSON files and `.opencode/agents` existing.

- [ ] **Step 3: Consolidate JSON dictionaries into `resources/` and agent prompts into `agents/`**

1. Move `knowledge.json`, `channels.json`, `tone_hints.json`, and `emoji_dictionary.json` from `skills/anibon-timestamper/resources/` to `resources/`, merge `skills/anibon-timestamper-local/resources/default_mappings.json` into `resources/default_mappings.json`, and remove `skills/*/resources/*.json`.
2. In `.opencode/plugins/anibon-stream-synthesis.mjs:11`, change:
```javascript
const pluginAgentsDir = path.resolve(__dirname, '../../agents');
```
3. Merge OpenCode frontmatter permissions from `.opencode/agents/*.md` into `agents/*.md` and delete `.opencode/agents/`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/ agents/ .opencode/ skills/ tests/test_skill_structure.py
git commit -m "refactor(resources): consolidate duplicate JSON dictionaries and agent definitions"
```

### Task 4: Reconcile Divergent Duplicate Scripts, Clean Gate Scripts, & Delete Dead Code

**Files:**
- Modify: `scripts/whisper_dispatcher.py:50-72,335-395`
- Delete: `skills/cleaning-auto-transcripts/scripts/whisper_dispatcher.py`
- Replace with symlink: `skills/anibon-timestamper/scripts/process_chunks_local.py` -> `../../anibon-timestamper-local/scripts/process_chunks_local.py`
- Replace with symlinks: `skills/anibon-timestamper/scripts/{analyze_555,audit_gaps,check_sections,pack_timestamps,validate_tags,whisper_dispatcher}.py` -> `../../../scripts/<name>.py`
- Replace with symlinks: `skills/anibon-timestamper-local/scripts/{fetch_fgo_db,fetch_ygo_db}.py` -> `../../anibon-world-identity/scripts/fetch_{fgo,ygo}_db.py`
- Delete: `skills/anibon-timestamper-local/scripts/anibon/websearch.py`
- Delete: `skills/anibon-timestamper-local/tests/test_websearch.py`
- Delete: `skills/anibon-local-transcription/scripts/{benchmark_check,detect_hallucinations}.py`
- Delete: `skills/cleaning-auto-transcripts/scripts/clean_garbled_dictionary.py`
- Delete: `scripts/subagent-prompt-builder.py`
- Move: `skills/anibon-timestamper/scripts/test_analyze_555_emoji.py` -> `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`
- Modify: `scripts/preflight-gate.py:1-132`
- Modify: `scripts/assembly-gate.py:1-288`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `anibon.time.parse_ts`, `anibon.parsers.parse_timestamps`
- Produces: Clean `scripts/preflight-gate.py`, `scripts/assembly-gate.py`, and unified `scripts/whisper_dispatcher.py`

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

```python
    def test_no_dead_or_divergent_script_copies(self):
        dead_paths = [
            "skills/cleaning-auto-transcripts/scripts/whisper_dispatcher.py",
            "skills/anibon-timestamper-local/scripts/anibon/websearch.py",
            "skills/anibon-local-transcription/scripts/benchmark_check.py",
            "skills/anibon-local-transcription/scripts/detect_hallucinations.py",
            "skills/cleaning-auto-transcripts/scripts/clean_garbled_dictionary.py",
            "scripts/subagent-prompt-builder.py",
            "skills/anibon-timestamper/scripts/test_analyze_555_emoji.py",
        ]
        for rel in dead_paths:
            self.assertFalse((PLUGIN_ROOT / rel).exists(), f"Dead/divergent file still exists: {rel}")

        symlinked = [
            "skills/anibon-timestamper/scripts/process_chunks_local.py",
            "skills/anibon-timestamper/scripts/pack_timestamps.py",
            "skills/anibon-timestamper/scripts/check_sections.py",
            "skills/anibon-timestamper/scripts/whisper_dispatcher.py",
            "skills/anibon-timestamper-local/scripts/fetch_fgo_db.py",
            "skills/anibon-timestamper-local/scripts/fetch_ygo_db.py",
        ]
        for rel in symlinked:
            self.assertTrue((PLUGIN_ROOT / rel).is_symlink(), f"Expected symlink at {rel}")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL

- [ ] **Step 3: Merge Vulkan `device_id` into `scripts/whisper_dispatcher.py`, replace hard copies with symlinks, delete dead scripts, and clean `preflight-gate.py` & `assembly-gate.py`**

1. In `scripts/whisper_dispatcher.py`, add optional `device_id: Optional[int] = None` to `HardwareProfile` and `run_whisper_slice()` (`if device_id is not None: cmd.extend(["-dev", str(device_id)])`).
2. Delete dead files and replace duplicate scripts with relative symlinks:
```bash
rm -f skills/cleaning-auto-transcripts/scripts/whisper_dispatcher.py \
      skills/anibon-timestamper-local/scripts/anibon/websearch.py \
      skills/anibon-timestamper-local/tests/test_websearch.py \
      skills/anibon-local-transcription/scripts/benchmark_check.py \
      skills/anibon-local-transcription/scripts/detect_hallucinations.py \
      skills/cleaning-auto-transcripts/scripts/clean_garbled_dictionary.py \
      scripts/subagent-prompt-builder.py
mv skills/anibon-timestamper/scripts/test_analyze_555_emoji.py skills/anibon-timestamper/tests/test_analyze_555_emoji.py
ln -sf ../../anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper/scripts/process_chunks_local.py
for f in analyze_555.py audit_gaps.py check_sections.py pack_timestamps.py validate_tags.py whisper_dispatcher.py; do
  ln -sf "../../../scripts/$f" "skills/anibon-timestamper/scripts/$f"
done
for f in fetch_fgo_db.py fetch_ygo_db.py; do
  ln -sf "../../anibon-world-identity/scripts/$f" "skills/anibon-timestamper-local/scripts/$f"
done
```
3. In `scripts/preflight-gate.py`:
   - Import `parse_ts` from `anibon.time` instead of inline `to_sec()`.
   - Replace `"detect_topics.py — keyword scan for sub-skill routing"` with `"detect_signals.py — TF-IDF keyword scan for sub-skill routing"`.
   - Set default `skill_base = str(Path(__file__).resolve().parent.parent / "skills" / "anibon-timestamper")`.
4. In `scripts/assembly-gate.py`:
   - Import `parse_ts` from `anibon.time`.
   - Delete unused `rewrite_section_headers()` (lines 58-96) and `merge_undersized_sections()` (lines 114-152).

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ skills/ tests/test_skill_structure.py
git commit -m "refactor(scripts): eliminate divergent copies, symlink shared CLIs, and prune dead code"
```

### Task 5: Unify Post-Loop Assembly in `process_chunks_local.py` & Convert Root Tests to Stdlib `unittest`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:274-289,520-574,700-747,850-925`
- Modify: `skills/anibon-timestamper-local/tests/test_pipeline_e2e.py`
- Modify: `tests/test_align_activity_timeline.py`
- Modify: `tests/test_detect_signals.py`
- Modify: `tests/test_extract_activity_timeline.py`
- Modify: `tests/test_merge_timestamps.py`
- Modify: `tests/test_unpack_storyboard.py`
- Modify: `tests/test_verify_highlight.py`
- Modify: `tests/test_vision.py`
- Modify: `tests/test_vlog_support.py`
- Test: `tests/` and `skills/anibon-timestamper-local/tests/`

**Interfaces:**
- Consumes: `apply_vision_verify`, `run_local_summarizer_pass`, `assemble_parts`, `audit_timestamps_against_glossary`, `run_parity_gates`
- Produces: `finalize_and_assemble_timestamps(workspace: Path, all_timestamps: list[str], endpoint: str, model: str, temperature: float, block_size: int, no_summarizer_pass: bool, args: argparse.Namespace | None = None, glossary: dict | None = None) -> tuple[Path, list[str]]`

- [ ] **Step 1: Write the failing test in `skills/anibon-timestamper-local/tests/test_pipeline_e2e.py`**

```python
    def test_finalize_and_assemble_timestamps_helper_exists(self):
        from process_chunks_local import finalize_and_assemble_timestamps
        self.assertTrue(callable(finalize_and_assemble_timestamps))
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper-local/scripts python3 -m unittest skills/anibon-timestamper-local/tests/test_pipeline_e2e.py -v
```
Expected: FAIL with `ImportError: cannot import name 'finalize_and_assemble_timestamps'`.

- [ ] **Step 3: Extract `finalize_and_assemble_timestamps()` in `process_chunks_local.py` and convert `tests/test_*.py` from `pytest` to `unittest.TestCase`**

1. In `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, define:
```python
def finalize_and_assemble_timestamps(
    workspace: Path,
    all_timestamps: List[str],
    endpoint: str,
    model: str,
    temperature: float,
    block_size: int,
    no_summarizer_pass: bool,
    args: Optional[argparse.Namespace] = None,
    glossary: Optional[dict] = None,
) -> Tuple[Path, List[str]]:
    deduped = list(dict.fromkeys(all_timestamps))
    raw_ts = workspace / "all_timestamps.txt"
    raw_ts.write_text("\n".join(deduped), encoding="utf-8")
    if args:
        deduped = apply_vision_verify(deduped, workspace, args, model)
    assembled = None
    if not no_summarizer_pass:
        assembled = run_local_summarizer_pass(endpoint, model, deduped, workspace, temperature)
    if not assembled:
        assembled = assemble_parts(deduped, workspace, block_size)
    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    if glossary:
        audit_timestamps_against_glossary(out_md, glossary)
    run_parity_gates(workspace, out_md)
    return out_md, deduped
```
Call `finalize_and_assemble_timestamps(...)` in `run_recursive_mode`, `run_group_mode`, and `--summarize-only`.
Replace `_fmt_ts` and `ts_to_sec` in `process_chunks_local.py:274-283` with `from anibon.time import fmt_ts as _fmt_ts, parse_ts as ts_to_sec`.

2. In `tests/test_{align_activity_timeline,detect_signals,extract_activity_timeline,merge_timestamps,unpack_storyboard,verify_highlight,vision,vlog_support}.py`, remove `import pytest` and wrap standalone test functions in `unittest.TestCase` classes using `tempfile.TemporaryDirectory()` where `tmp_path` was used and `unittest.mock.patch` where `monkeypatch` was used.

- [ ] **Step 4: Run test to verify all root and skill tests pass under stdlib `unittest`**

Run:
```bash
PYTHONPATH=lib:skills/anibon-timestamper/scripts:skills/anibon-stream-activity/scripts:skills/creating-highlight-video/scripts python3 -m unittest discover -s tests -p "test_*.py" -v && PYTHONPATH=lib:skills/anibon-timestamper-local/scripts python3 -m unittest discover -s skills/anibon-timestamper-local/tests -p "test_*.py" -v
```
Expected: PASS (0 errors across all root and local-timestamper tests).

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/process_chunks_local.py skills/anibon-timestamper-local/tests/test_pipeline_e2e.py tests/
git commit -m "refactor(tests,local): unify 3 timestamp assembly blocks and drop pytest dependency"
```

### Task 6: Upgrade `agy` Model Pins to `Gemini 3.8 Flash (High)` Across Code, Skills, & Docs

**Files:**
- Modify: `GEMINI.md:18-21`
- Modify: `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py:3,354-362`
- Modify: `skills/anibon-livechat-analysis/SKILL.md:58`
- Modify: `skills/antigravity-vision-proxy/SKILL.md:96,119-120`
- Modify: `skills/whisper-corruption-recovery/SKILL.md:56`
- Modify: `docs/REFERENCE.md:206`
- Modify: `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py`
- Modify: `tests/test_skill_structure.py`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `agy --model "Gemini 3.8 Flash (High)"`
- Produces: `extract_visual_livechat.run_agy_vision_ocr(frames_dir: Path, model: str = "Gemini 3.8 Flash (High)") -> str`

- [ ] **Step 1: Write the failing test in `tests/test_skill_structure.py`**

```python
    def test_agy_model_pinned_to_gemini_3_8_flash_high(self):
        targets = [
            PLUGIN_ROOT / "GEMINI.md",
            PLUGIN_ROOT / "skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py",
            PLUGIN_ROOT / "skills/anibon-livechat-analysis/SKILL.md",
            PLUGIN_ROOT / "skills/antigravity-vision-proxy/SKILL.md",
            PLUGIN_ROOT / "skills/whisper-corruption-recovery/SKILL.md",
            PLUGIN_ROOT / "docs/REFERENCE.md",
        ]
        for path in targets:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("Gemini 3.6 Flash", content, f"Stale Gemini 3.6 Flash pin in {path.relative_to(PLUGIN_ROOT)}")
            self.assertIn("Gemini 3.8 Flash (High)", content, f"Missing Gemini 3.8 Flash (High) in {path.relative_to(PLUGIN_ROOT)}")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: FAIL (`Stale Gemini 3.6 Flash pin in GEMINI.md`).

- [ ] **Step 3: Update `GEMINI.md`, `extract_visual_livechat.py`, `antigravity-vision-proxy/SKILL.md`, `anibon-livechat-analysis/SKILL.md`, `whisper-corruption-recovery/SKILL.md`, and `docs/REFERENCE.md` to `Gemini 3.8 Flash (High)`**

1. In `GEMINI.md:20`, replace `Current: \`Gemini 3.6 Flash\`.` with `Current: \`Gemini 3.8 Flash (High)\`.`.
2. In `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py:354-362`, update `run_agy_vision_ocr`:
```python
def run_agy_vision_ocr(frames_dir: Path, model: str = "Gemini 3.8 Flash (High)") -> str:
    """Invoke agy with Gemini 3.8 Flash (High) to extract live chat messages from frames."""
    cmd = [
        "agy",
        "--model", model,
        "--dangerously-skip-permissions",
        "--print",
        LIVECHAT_OCR_PROMPT,
        "--add-dir", str(frames_dir),
    ]
```
3. Replace `Gemini 3.6 Flash` / `Gemini 3.6 Flash (Medium)` with `Gemini 3.8 Flash (High)` in `skills/antigravity-vision-proxy/SKILL.md:96,119-120`, `skills/anibon-livechat-analysis/SKILL.md:58`, `skills/whisper-corruption-recovery/SKILL.md:56`, and `docs/REFERENCE.md:206`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=lib python3 -m unittest tests/test_skill_structure.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add GEMINI.md docs/REFERENCE.md skills/ tests/test_skill_structure.py
git commit -m "chore(agy): upgrade Antigravity model pins to Gemini 3.8 Flash (High)"