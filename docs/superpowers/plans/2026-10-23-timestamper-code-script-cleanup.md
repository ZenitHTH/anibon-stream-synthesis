# Timestamper Code, Script & File Management Implementation Plan (Clean Code Edition)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor file, script, and path management across `anibon-timestamper` and `anibon-timestamper-local` following Robert C. Martin's *Clean Code* principles: Single Source of Truth (DRY), Dead Code Elimination (G9), Clean Tests (F.I.R.S.T.), and The Boy Scout Rule.

**Architecture:** Enforce strict component separation: plugin root `scripts/` houses canonical CLI adapters, `lib/` encapsulates core domain logic (Single Responsibility Principle), and skills maintain strictly workflow-specific runners. All cross-module path navigations resolve via bounded, tested relative paths.

**Tech Stack:** Python 3.15, standard library `unittest`, `pathlib`, `argparse`, Bash.

**Spec:** Robert C. Martin's *Clean Code: A Handbook of Agile Software Craftsmanship* (Prentice Hall):
- **The Boy Scout Rule** (Ch. 1): Leave the repository cleaner than you found it.
- **Single Responsibility Principle & Common Closure** (Ch. 10 & Component Principles): Files that change together live together; one reason to change per module.
- **Elimination of Duplication / DRY** (Ch. 13 & 17, Smell G5): Duplication is the primary cause of bugs, drift, and maintenance fatigue.
- **Dead Code Purge** (Ch. 17, Smells G9, G10, G12): Remove uncalled scripts, accidental artifacts, and dead shims immediately.
- **F.I.R.S.T. Clean Tests** (Ch. 9): Tests must be Fast, Independent, Repeatable, Self-Validating, and Timely—executable directly without environment gymnastics.

---

## Global Constraints

- **Single Source of Truth (DRY)**: Exactly one canonical implementation of every CLI utility and data file on disk. Zero duplicate copies, zero deceptive symlinks.
- **Dead Code Elimination (G9)**: No zombie folders (typo directories like `--help`), empty artifact trees, or abandoned symlinks.
- **Clean Test Isolation (F.I.R.S.T. - Independent & Self-Validating)**: Every test file under `tests/` and `skills/*/tests/` must execute and pass via standard `python3 -m unittest` without requiring manual `PYTHONPATH` exports.
- **No pytest**: Standard library `unittest` only across the entire codebase.
- **Safe Compatibility**: Maintain runtime backward compatibility with registered Antigravity session hooks and active skill contracts.

---

## Review Focus

1. **Parity Gate Execution (Abstraction Level Integrity)**: `lib/process/parity_gates.py` must correctly resolve `scripts/` using `parents[2]` (plugin root), executing `audit_gaps.py` and `check_sections.py` instead of silently skipping them.
2. **Hook System Resilience**: `hooks.json` must reference canonical `scripts/check_sections.py`, and the in-session forwarder shim at `skills/anibon-timestamper/scripts/check_sections.py` must forward calls cleanly without breaking file-writing tools.
3. **Autonomous Unit Tests**: Tests in `skills/anibon-timestamper/tests` must import dependencies reliably through self-contained `sys.path` resolution.
4. **Shell Script Parity (DRY)**: Consolidating `launch_local.zsh` into `launch_local.sh` must retain 100% parameter functionality (arguments `$1` through `$6` including `VIDEO_URL`).
5. **Architectural Guardrails**: `tests/test_skill_structure.py` must guard the repository against dead directories, rogue symlinks, and duplicate runners.

---

### Task 1: Fix Parity Gate Script Path Resolution (Boy Scout Rule & Abstraction Integrity)

*Clean Code Reference: Chapter 17 (Smell G6: Code at Wrong Level of Abstraction)*
`lib/process/parity_gates.py` hardcoded `parents[4]` instead of `parents[2]`, leaping past the component boundary into the parent user directory. Parity gates silently failed open.

**Files:**
- Modify: `lib/process/parity_gates.py:15`
- Test: `skills/anibon-timestamper-local/tests/test_parity_gates.py`

**Interfaces:**
- Consumes: `Path(__file__).resolve()` from `lib/process/parity_gates.py`
- Produces: `_PLUGIN_SCRIPTS` pointing directly to `<plugin_root>/scripts`

- [ ] **Step 1: Write failing test asserting `_PLUGIN_SCRIPTS` resolves to the existing root scripts directory**

In `skills/anibon-timestamper-local/tests/test_parity_gates.py`:
```python
    def test_plugin_scripts_directory_exists_and_contains_gates(self):
        from process.parity_gates import _PLUGIN_SCRIPTS
        self.assertTrue(_PLUGIN_SCRIPTS.is_dir(), f"_PLUGIN_SCRIPTS does not exist: {_PLUGIN_SCRIPTS}")
        self.assertTrue((_PLUGIN_SCRIPTS / "audit_gaps.py").is_file(), "audit_gaps.py missing in _PLUGIN_SCRIPTS")
        self.assertTrue((_PLUGIN_SCRIPTS / "check_sections.py").is_file(), "check_sections.py missing in _PLUGIN_SCRIPTS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=lib:scripts:skills/anibon-timestamper-local/scripts python3 -m unittest skills/anibon-timestamper-local/tests/test_parity_gates.py -k test_plugin_scripts_directory_exists_and_contains_gates`
Expected: FAIL (`_PLUGIN_SCRIPTS` points to `~/.gemini/config/scripts` which does not exist)

- [ ] **Step 3: Fix `_PLUGIN_SCRIPTS` path in `lib/process/parity_gates.py`**

In `lib/process/parity_gates.py` line 15:
```python
_PLUGIN_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=lib:scripts:skills/anibon-timestamper-local/scripts python3 -m unittest skills/anibon-timestamper-local/tests/test_parity_gates.py -k test_plugin_scripts_directory_exists_and_contains_gates`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/process/parity_gates.py skills/anibon-timestamper-local/tests/test_parity_gates.py
git commit -m "fix(parity-gates): correct root scripts path resolution from parents[4] to parents[2]"
```

---

### Task 2: Purge Dead Artifacts & Accidental Folders (Clean Code G9: Dead Code)

*Clean Code Reference: Chapter 17 (Smell G9: Dead Code, G10: Misplaced Responsibility)*
Accidental directory typo `--help/` and empty `frames/samples` clutter the codebase and confuse readers. The skill-level `resources/garbled_replacements.json` symlink violates Single Source of Truth because canonical resources live at plugin root `resources/`.

**Files:**
- Delete: `skills/anibon-timestamper/--help` (accidental directory)
- Delete: `skills/anibon-timestamper/frames/samples` (empty directory)
- Delete: `skills/anibon-timestamper/frames` (empty directory)
- Delete: `skills/anibon-timestamper/resources/garbled_replacements.json` (redundant symlink)
- Delete: `skills/anibon-timestamper/resources` (empty directory)
- Modify: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `skills/anibon-timestamper/` filesystem tree
- Produces: Clean directory structure with zero dead or accidental artifacts.

- [ ] **Step 1: Write test assertion in `tests/test_skill_structure.py` against dead folders and redundant skill resources**

Add check in `tests/test_skill_structure.py`:
```python
    def test_no_accidental_or_empty_directories(self):
        timestamper_dir = SKILLS_DIR / "anibon-timestamper"
        self.assertFalse((timestamper_dir / "--help").exists(), "Accidental '--help' folder found")
        self.assertFalse((timestamper_dir / "frames").exists(), "Empty 'frames' folder found")
        self.assertFalse((timestamper_dir / "resources").exists(), "Redundant 'resources' directory found in timestamper")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_no_accidental_or_empty_directories`
Expected: FAIL

- [ ] **Step 3: Remove dead artifacts**

```bash
rm -rf skills/anibon-timestamper/--help
rm -rf skills/anibon-timestamper/frames
rm -rf skills/anibon-timestamper/resources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_no_accidental_or_empty_directories`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u
git add tests/test_skill_structure.py
git commit -m "chore(skills): delete accidental --help directory and dead resource symlinks"
```

---

### Task 3: Deduplicate Local Launch Runners (Clean Code DRY / Smell G5: Duplication)

*Clean Code Reference: Chapter 13 & Chapter 17 (Smell G5: Duplication)*
`launch_local.sh` and `launch_local.zsh` contain 95% identical code, differing only in the shell interpreter and a 6th optional `VIDEO_URL` argument in `.zsh`. Maintain one POSIX-compatible runner supporting all 6 arguments.

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/launch_local.sh`
- Delete: `skills/anibon-timestamper-local/scripts/launch_local.zsh`
- Test: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: CLI parameters: `$1` (WORKSPACE), `$2` (ENDPOINT_OR_IP), `$3` (MODEL), `$4` (LANG), `$5` (MODE), `$6` (VIDEO_URL)
- Produces: Single unified `launch_local.sh` runner.

- [ ] **Step 1: Write test assertion in `tests/test_skill_structure.py`**

In `tests/test_skill_structure.py`:
```python
    def test_launch_local_runners_consolidation(self):
        local_scripts = SKILLS_DIR / "anibon-timestamper-local" / "scripts"
        self.assertFalse((local_scripts / "launch_local.zsh").exists(), "Redundant launch_local.zsh still exists")
        sh_content = (local_scripts / "launch_local.sh").read_text(encoding="utf-8")
        self.assertIn("VIDEO_URL", sh_content, "launch_local.sh missing VIDEO_URL argument support")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_launch_local_runners_consolidation`
Expected: FAIL

- [ ] **Step 3: Update `launch_local.sh` and remove `launch_local.zsh`**

Update `launch_local.sh` usage and arguments:
```bash
usage() {
    echo "Usage: $0 <WORKSPACE> [ENDPOINT_OR_IP] [MODEL] [LANG] [MODE] [VIDEO_URL]"
    echo "  ENDPOINT_OR_IP: Full URL or IP address (default: 100.115.25.30)"
    echo "  MODEL: Model identifier (default: auto)"
    echo "  LANG: Output language th|en (default: th)"
    echo "  MODE: recursive|group (default: recursive)"
    echo "  VIDEO_URL: Optional YouTube URL for whisper audio slicing"
    exit 1
}
...
VIDEO_URL="${6:-}"
EXTRA_ARGS=()
if [[ -n "$VIDEO_URL" ]]; then
    EXTRA_ARGS+=(--video-url "$VIDEO_URL")
fi
```
Delete `skills/anibon-timestamper-local/scripts/launch_local.zsh`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_skill_structure.py -k test_launch_local_runners_consolidation`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/launch_local.sh tests/test_skill_structure.py
git rm skills/anibon-timestamper-local/scripts/launch_local.zsh
git commit -m "refactor(runners): consolidate launch_local.zsh into launch_local.sh (DRY)"
```

---

### Task 4: Self-Validating Clean Tests (Clean Code Ch. 9 F.I.R.S.T. Principles)

*Clean Code Reference: Chapter 9 (Clean Tests: Independent & Self-Validating)*
Tests in `skills/anibon-timestamper/tests` (`test_validate_tags.py`, `test_pack_timestamps.py`, `test_analyze_555_emoji.py`) fail when run via `python3 -m unittest discover` because they relied on fragile relative offsets (`parents[2]` which points to `skills/` instead of plugin root). Clean tests must set up their own paths cleanly and run independently.

**Files:**
- Modify: `skills/anibon-timestamper/tests/test_validate_tags.py:7-14`
- Modify: `skills/anibon-timestamper/tests/test_pack_timestamps.py:6-12`
- Modify: `skills/anibon-timestamper/tests/test_analyze_555_emoji.py:1-12`

**Interfaces:**
- Consumes: `Path(__file__).resolve().parents[3]` (plugin root)
- Produces: Reliable autonomous test execution for `skills/anibon-timestamper/tests`.

- [ ] **Step 1: Run unassisted test discovery to reproduce failures**

Run: `python3 -m unittest discover -s skills/anibon-timestamper/tests`
Expected: FAIL (ModuleNotFoundError on `analyze_555`, `pack_timestamps`, `validate_tags`)

- [ ] **Step 2: Update path resolution across all three test files**

In `skills/anibon-timestamper/tests/test_validate_tags.py`:
```python
_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[3]
for _p in (_PLUGIN_ROOT / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
```

In `skills/anibon-timestamper/tests/test_pack_timestamps.py`:
```python
_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[3]
for _p in (_PLUGIN_ROOT / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
```

In `skills/anibon-timestamper/tests/test_analyze_555_emoji.py`:
```python
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _p in (_PLUGIN_ROOT / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
```

- [ ] **Step 3: Run unittest discovery to verify self-validating execution**

Run: `python3 -m unittest discover -s skills/anibon-timestamper/tests`
Expected: PASS (all 11 tests pass with 0 errors)

- [ ] **Step 4: Commit**

```bash
git add skills/anibon-timestamper/tests/
git commit -m "fix(tests): ensure autonomous sys.path resolution in anibon-timestamper tests (Clean Tests)"
```

---

### Task 5: Component Boundary Alignment in Documentation & Hooks (Clean Architecture)

*Clean Code Reference: Chapter 10 (Classes/Modules: Single Responsibility Principle)*
Align documentation in `SKILL.md` files to clearly state that shared pipeline tools live at plugin root (`scripts/`). Ensure `hooks.json` uses the canonical script path, with an in-place forwarder bridge for active sessions.

**Files:**
- Modify: `hooks.json`
- Modify: `skills/anibon-timestamper/SKILL.md`
- Modify: `skills/anibon-timestamper-local/SKILL.md`
- Ensure: `skills/anibon-timestamper/scripts/check_sections.py` (backward-compatibility forwarding bridge)

**Interfaces:**
- Consumes: Canonical script locations at root `scripts/`
- Produces: Unambiguous documentation and crash-free tool execution.

- [ ] **Step 1: Verify `hooks.json` points to canonical script**

Verify `hooks.json` specifies:
```json
"command": "python3 scripts/check_sections.py --file \"$TARGET_FILE\""
```

- [ ] **Step 2: Update `SKILL.md` documentation**

Clarify in `anibon-timestamper/SKILL.md` and `anibon-timestamper-local/SKILL.md`:
- Pipeline orchestration commands (`prepare_video.py`, `audit_gaps.py`, `check_sections.py`, `pack_timestamps.py`) execute from plugin root directory.
- Skill-specific runners (`process_chunks_local.py`) reside in `skills/<skill>/scripts/`.

- [ ] **Step 3: Run skill structure test to verify frontmatter and formatting integrity**

Run: `python3 -m unittest tests/test_skill_structure.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add hooks.json skills/anibon-timestamper/SKILL.md skills/anibon-timestamper-local/SKILL.md skills/anibon-timestamper/scripts/check_sections.py
git commit -m "docs(skills): align SKILL.md commands and hooks to canonical root scripts"
```

---

### Task 6: Full Integration Test Verification (Boy Scout Rule Verification)

*Clean Code Reference: Chapter 1 (The Boy Scout Rule)*
Leave the entire repo in a verified, passing state with 0 regressions across all suites.

**Files:**
- Verify: Entire codebase

- [ ] **Step 1: Execute complete test suites across all layers**

Run:
```bash
python3 -m unittest discover -s tests && \
python3 -m unittest discover -s skills/anibon-timestamper/tests && \
PYTHONPATH=lib:scripts:skills/anibon-timestamper-local/scripts python3 -m unittest discover -s skills/anibon-timestamper-local/tests
```
Expected: PASS with 0 failures and 0 errors across all 245+ tests.

- [ ] **Step 2: Verify CLI help exits cleanly on all root and skill scripts**

Run:
```bash
for f in scripts/*.py; do
    PYTHONPATH=lib python3 "$f" --help > /dev/null || echo "Failed: $f"
done
```
Expected: All exit with code 0.
