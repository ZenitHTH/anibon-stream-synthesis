# Local Config JSON Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tracked `.env` configuration file in `anibon-timestamper-local` with a tracked `config.json` file (and gitignore `.env` for secrets only).

**Architecture:** `skills/anibon-timestamper-local/config.json` stores all 24 non-secret numeric and endpoint parameters as native JSON types. `scripts/anibon/config.py` loads `config.json` via Python's stdlib `json` module while still allowing `ANIBON_*` environment variable overrides. `process_chunks_local.py` exposes `--config` (with `--env-file` as a backward-compatible alias) to load custom JSON config files.

**Tech Stack:** Python 3 standard library (`json`, `os`, `pathlib`, `unittest`).

**Spec:** User request (2026-10-17) — move non-secret configuration from `.env` to `config.json` since `.env` is reserved for secrets.

## Global Constraints

- Zero external dependencies (stdlib `json` only).
- Remove tracked `skills/anibon-timestamper-local/.env` and add `.env` to root `.gitignore` so secrets are never committed.
- All 24 exported constant names in `anibon.config` (`PRIMARY_HOST`, `DEFAULT_PORT`, `DEFAULT_CHAT_PATH`, `DEFAULT_MODEL`, `PROBE_TIMEOUT_SEC`, `CHUNK_MAX_TOKENS`, `CHUNK_TIMEOUT_SEC`, `MULTIMODAL_TIMEOUT_SEC`, `PRUNE_MAX_TOKENS`, `PRUNE_TIMEOUT_SEC`, `SUMMARIZER_MAX_TOKENS`, `SUMMARIZER_TIMEOUT_SEC`, `ENTITY_CONTEXT_MAX_TOKENS`, `DEFAULT_TEMPERATURE`, `VISION_TEMPERATURE`, `MAX_RETRIES`, `PRUNE_MIN_INPUT`, `PRUNE_TARGET_MIN`, `PRUNE_TARGET_MAX`, `DEDUP_MIN_GAP_SEC`, `DEDUP_MAX_GAP_SEC`, `STAMP_COLLISION_SEC`, `DEFAULT_GROUP_SIZE`, `DEFAULT_BLOCK_SIZE`, `BYTE_CAP_LIMIT`) remain identical so downstream modules (`summarizer.py`, `lmstudio.py`, `prompts.py`, `multimodal.py`, `timestamps.py`) require zero changes.

## Review Focus

- Malformed or missing `config.json` must log a warning to `stderr` and fall back to hardcoded defaults without crashing.
- Invalid value types in `config.json` (e.g., `"not_a_number"` for an integer field) must fall back to the default int/float value.
- `os.environ["ANIBON_<KEY>"]` overrides `config.json` when `override=False` (default startup), while `load_config(custom_path, override=True)` overrides both.
- Both snake_case keys (`"chunk_max_tokens"`) and upper `ANIBON_` keys (`"ANIBON_CHUNK_MAX_TOKENS"`) in custom JSON files are accepted.

---

### Task 1: Replace `.env` with `config.json` and update `anibon/config.py`

**Files:**
- Delete: `skills/anibon-timestamper-local/.env`
- Modify: `.gitignore` (add `.env` and `*.env`)
- Create: `skills/anibon-timestamper-local/config.json`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/config.py`
- Modify: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Produces in `anibon.config`:
  - `SKILL_CONFIG_PATH: Path` (`skills/anibon-timestamper-local/config.json`)
  - `load_config(path: Optional[Path] = None, override: bool = False) -> Dict[str, Any]`
  - `cfg_int(key: str, default: int) -> int`
  - `cfg_float(key: str, default: float) -> float`
  - `cfg_str(key: str, default: str) -> str`
  - `reload_config() -> None`
  - All 24 module-level constants unchanged.

- [ ] **Step 1: Update `tests/test_config.py` to test `config.json` loading and precedence**

```python
import json
import os
import tempfile
import unittest
from pathlib import Path
from anibon.config import (
    load_config,
    cfg_int,
    cfg_float,
    cfg_str,
    SKILL_CONFIG_PATH,
    CHUNK_MAX_TOKENS,
    SUMMARIZER_MAX_TOKENS,
    PRUNE_MAX_TOKENS,
    BYTE_CAP_LIMIT,
)


class TestConfig(unittest.TestCase):
    def tearDown(self):
        load_config(SKILL_CONFIG_PATH, override=True)

    def test_skill_config_json_exists_and_loads_defaults(self):
        self.assertTrue(SKILL_CONFIG_PATH.is_file())
        self.assertEqual(CHUNK_MAX_TOKENS, 4096)
        self.assertEqual(SUMMARIZER_MAX_TOKENS, 4096)
        self.assertEqual(PRUNE_MAX_TOKENS, 4000)
        self.assertEqual(BYTE_CAP_LIMIT, 3500)

    def test_load_config_parses_json_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "config.json"
            cfg_file.write_text(
                json.dumps({
                    "primary_host": "192.168.1.50",
                    "chunk_max_tokens": 2048,
                    "temperature": 0.25,
                }),
                encoding="utf-8",
            )
            parsed = load_config(cfg_file, override=True)
            self.assertEqual(parsed["primary_host"], "192.168.1.50")
            self.assertEqual(cfg_str("primary_host", "100.115.25.30"), "192.168.1.50")
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 2048)
            self.assertAlmostEqual(cfg_float("temperature", 0.1), 0.25)

    def test_malformed_json_or_bad_types_fall_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / "bad.json"
            bad_file.write_text("{invalid json", encoding="utf-8")
            self.assertEqual(load_config(bad_file, override=True), {})

            type_file = Path(tmp) / "types.json"
            type_file.write_text(
                json.dumps({"chunk_max_tokens": "not_a_number", "temperature": ""}),
                encoding="utf-8",
            )
            load_config(type_file, override=True)
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 4096)
            self.assertAlmostEqual(cfg_float("temperature", 0.1), 0.1)

    def test_os_environ_overrides_config_json_when_not_forced(self):
        os.environ["ANIBON_CHUNK_MAX_TOKENS"] = "8192"
        try:
            load_config(SKILL_CONFIG_PATH, override=False)
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 8192)
        finally:
            os.environ.pop("ANIBON_CHUNK_MAX_TOKENS", None)
```

- [x] **Step 1: Update `tests/test_config.py` to test `config.json` loading and precedence**
...
- [x] **Step 2: Run test to verify it fails**
  Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
  Expected: FAIL with `ImportError: cannot import name 'load_config' from 'anibon.config'`

- [x] **Step 3: Create `config.json`, remove `.env`, update `.gitignore`, and implement `scripts/anibon/config.py`**
  Write `skills/anibon-timestamper-local/config.json` with all 24 snake_case keys, update `scripts/anibon/config.py` to load `config.json` into an in-memory `_CONFIG` dict with `ANIBON_<UPPER_KEY>` env fallback, remove `skills/anibon-timestamper-local/.env`, and add `.env` to `.gitignore`.

- [x] **Step 4: Run test to verify it passes**
  Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
  Expected: PASS

---

### Task 2: Wire `--config` CLI flag in `process_chunks_local.py` and update `SKILL.md`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`
- Modify: `skills/anibon-timestamper-local/SKILL.md`
- Modify: `skills/anibon-timestamper-local/tests/test_config.py`

**Interfaces:**
- Consumes: `load_config`, `reload_config` from `anibon.config`
- Produces: `--config` CLI argument on `process_chunks_local.py` (with `--env-file` kept as an alias for convenience).

- [x] **Step 1: Update CLI flag test in `tests/test_config.py` to assert `--config`**

```python
    def test_process_chunks_has_config_flag(self):
        import subprocess
        res = subprocess.run(
            ["python3", "scripts/process_chunks_local.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(SKILL_CONFIG_PATH.parent),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--config", res.stdout)
```

- [x] **Step 2: Run test to verify it fails**
  Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
  Expected: FAIL (`--config` not in help output)

- [x] **Step 3: Update `process_chunks_local.py` and `SKILL.md`**
  In `process_chunks_local.py`, import `load_config` from `anibon.config` and replace `--env-file` with `--config`, `--env-file` (`dest="config_file"`). Update `SKILL.md` tip block to reference `config.json` and `--config`.

- [x] **Step 4: Run full test suite to verify all tests pass**
  Run: `PYTHONPATH=scripts python3 -m unittest discover -s tests -v`
  Expected: PASS (107 tests)

- [x] **Step 5: Commit**
  `git add .gitignore skills/anibon-timestamper-local/ docs/superpowers/plans/2026-10-17-local-config-json.md && git commit -m "refactor(local): replace .env with config.json for non-secret settings"`
