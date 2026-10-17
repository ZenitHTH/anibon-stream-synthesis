# Local .env Configuration Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all hardcoded numeric and endpoint configuration parameters (such as `max_tokens`, timeouts, temperatures, pruning bounds, deduplication gaps, and byte limits) in `anibon-timestamper-local` into a `.env` file loaded via a zero-dependency `anibon/config.py` module.

**Architecture:** Create `scripts/anibon/config.py` with a stdlib `.env` parser (`load_dotenv`) and typed getters (`env_int`, `env_float`, `env_str`) that auto-load `skills/anibon-timestamper-local/.env` on import while respecting existing `os.environ` overrides and falling back safely on invalid values. Wire `lmstudio.py`, `summarizer.py`, `prompts.py`, `multimodal.py`, `timestamps.py`, and `process_chunks_local.py` to read their defaults from `anibon.config`.

**Tech Stack:** Python 3 stdlib (`os`, `pathlib`), `unittest`.

**Spec:** User request to split all configuration numbers (e.g. `max_tokens`, timeouts, thresholds) into a `.env` file in `skills/anibon-timestamper-local/`.

## Global Constraints

- Root: `skills/anibon-timestamper-local/` (git repo = `~/.gemini/config/plugins/anibon-stream-synthesis`). All relative paths below are relative to `skills/anibon-timestamper-local/`.
- Test command: `PYTHONPATH=scripts python3 -m unittest <module> -v` (no pytest or `python-dotenv` dependency).
- Precedence order: CLI flags > process `os.environ` > workspace `.env` (if passed via `--env-file`) > skill root `.env` > hardcoded fallback in `config.py`.
- All current default values MUST remain identical so existing unit tests and behavior do not change unless `.env` or env vars are modified.

## Review Focus

1. Malformed numeric values in `.env` (e.g. `ANIBON_CHUNK_MAX_TOKENS=abc` or empty `ANIBON_CHUNK_MAX_TOKENS=`) → `env_int` / `env_float` must fall back to the default value without crashing (`test_malformed_or_empty_env_falls_back_to_default`).
2. Inline comments and quoted values in `.env` (e.g. `ANIBON_PRIMARY_HOST="100.115.25.30" # tailscale`) → parser strips quotes and inline `#` comments cleanly (`test_dotenv_parses_quotes_comments_and_export`).
3. Process environment variables set before import (e.g. `ANIBON_SUMMARIZER_MAX_TOKENS=8192`) → `load_dotenv(override=False)` preserves existing `os.environ` values (`test_os_environ_takes_precedence_over_dotenv`).
4. Explicit `--env-file` passed on CLI → `load_dotenv(path, override=True)` overrides defaults for that run (`test_load_dotenv_override_updates_values`).
5. Function signature defaults in `summarizer.py` / `lmstudio.py` / `timestamps.py` → use `config` constants so callers that omit optional args automatically get the `.env`-configured numbers (`test_summarizer_and_lmstudio_use_config_defaults`).

---

### Task 1: Create `.env` file and `scripts/anibon/config.py` with unit tests

**Files:**
- Create: `.env`
- Create: `scripts/anibon/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces in `anibon.config`:
  - `load_dotenv(path: Optional[Path] = None, override: bool = False) -> Dict[str, str]`
  - `env_str(key: str, default: str) -> str`
  - `env_int(key: str, default: int) -> int`
  - `env_float(key: str, default: float) -> float`
  - Constants (exact names and defaults):
    - `PRIMARY_HOST: str` (`ANIBON_PRIMARY_HOST`, `"100.115.25.30"`)
    - `DEFAULT_PORT: int` (`ANIBON_PORT`, `1234`)
    - `DEFAULT_MODEL: str` (`ANIBON_DEFAULT_MODEL`, `"gemma-4-12b-it-qat@q4_k_xl"`)
    - `PROBE_TIMEOUT_SEC: float` (`ANIBON_PROBE_TIMEOUT_SEC`, `1.0`)
    - `CHUNK_MAX_TOKENS: int` (`ANIBON_CHUNK_MAX_TOKENS`, `4096`)
    - `CHUNK_TIMEOUT_SEC: int` (`ANIBON_CHUNK_TIMEOUT_SEC`, `180`)
    - `MULTIMODAL_TIMEOUT_SEC: int` (`ANIBON_MULTIMODAL_TIMEOUT_SEC`, `120`)
    - `PRUNE_MAX_TOKENS: int` (`ANIBON_PRUNE_MAX_TOKENS`, `4000`)
    - `PRUNE_TIMEOUT_SEC: int` (`ANIBON_PRUNE_TIMEOUT_SEC`, `600`)
    - `SUMMARIZER_MAX_TOKENS: int` (`ANIBON_SUMMARIZER_MAX_TOKENS`, `4096`)
    - `SUMMARIZER_TIMEOUT_SEC: int` (`ANIBON_SUMMARIZER_TIMEOUT_SEC`, `600`)
    - `ENTITY_CONTEXT_MAX_TOKENS: int` (`ANIBON_ENTITY_CONTEXT_MAX_TOKENS`, `300`)
    - `DEFAULT_TEMPERATURE: float` (`ANIBON_TEMPERATURE`, `0.1`)
    - `VISION_TEMPERATURE: float` (`ANIBON_VISION_TEMPERATURE`, `0.2`)
    - `MAX_RETRIES: int` (`ANIBON_MAX_RETRIES`, `2`)
    - `PRUNE_MIN_INPUT: int` (`ANIBON_PRUNE_MIN_INPUT`, `60`)
    - `PRUNE_TARGET_MIN: int` (`ANIBON_PRUNE_TARGET_MIN`, `40`)
    - `PRUNE_TARGET_MAX: int` (`ANIBON_PRUNE_TARGET_MAX`, `60`)
    - `DEDUP_MIN_GAP_SEC: int` (`ANIBON_DEDUP_MIN_GAP_SEC`, `120`)
    - `DEDUP_MAX_GAP_SEC: int` (`ANIBON_DEDUP_MAX_GAP_SEC`, `600`)
    - `STAMP_COLLISION_SEC: int` (`ANIBON_STAMP_COLLISION_SEC`, `45`)
    - `DEFAULT_GROUP_SIZE: int` (`ANIBON_GROUP_SIZE`, `4`)
    - `DEFAULT_BLOCK_SIZE: int` (`ANIBON_BLOCK_SIZE`, `2400`)
    - `BYTE_CAP_LIMIT: int` (`ANIBON_BYTE_CAP_LIMIT`, `3500`)

- [x] **Step 1: Write the failing tests in `tests/test_config.py`**

```python
import os
import tempfile
import unittest
from pathlib import Path
from anibon.config import (
    load_dotenv,
    env_int,
    env_float,
    env_str,
    SKILL_DOTENV_PATH,
    CHUNK_MAX_TOKENS,
    SUMMARIZER_MAX_TOKENS,
    PRUNE_MAX_TOKENS,
    BYTE_CAP_LIMIT,
)


class TestConfig(unittest.TestCase):
    def test_skill_dotenv_file_exists_and_loads_defaults(self):
        self.assertTrue(SKILL_DOTENV_PATH.is_file())
        self.assertEqual(CHUNK_MAX_TOKENS, 4096)
        self.assertEqual(SUMMARIZER_MAX_TOKENS, 4096)
        self.assertEqual(PRUNE_MAX_TOKENS, 4000)
        self.assertEqual(BYTE_CAP_LIMIT, 3500)

    def test_dotenv_parses_quotes_comments_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "# Comment line\n"
                "export TEST_HOST=\"100.115.25.30\" # inline comment\n"
                "TEST_TOKENS=2048 # token limit\n"
                "TEST_TEMP='0.25'\n",
                encoding="utf-8",
            )
            parsed = load_dotenv(env_file, override=True)
            self.assertEqual(parsed["TEST_HOST"], "100.115.25.30")
            self.assertEqual(env_int("TEST_TOKENS", 100), 2048)
            self.assertAlmostEqual(env_float("TEST_TEMP", 0.1), 0.25)
            for k in ("TEST_HOST", "TEST_TOKENS", "TEST_TEMP"):
                os.environ.pop(k, None)

    def test_malformed_or_empty_env_falls_back_to_default(self):
        os.environ["TEST_BAD_INT"] = "not_a_number"
        os.environ["TEST_EMPTY_FLOAT"] = ""
        try:
            self.assertEqual(env_int("TEST_BAD_INT", 4096), 4096)
            self.assertAlmostEqual(env_float("TEST_EMPTY_FLOAT", 0.1), 0.1)
        finally:
            os.environ.pop("TEST_BAD_INT", None)
            os.environ.pop("TEST_EMPTY_FLOAT", None)

    def test_os_environ_takes_precedence_over_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("TEST_PREC=100\n", encoding="utf-8")
            os.environ["TEST_PREC"] = "999"
            try:
                load_dotenv(env_file, override=False)
                self.assertEqual(env_int("TEST_PREC", 0), 999)
            finally:
                os.environ.pop("TEST_PREC", None)

    def test_load_dotenv_override_updates_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("TEST_OVER=555\n", encoding="utf-8")
            os.environ["TEST_OVER"] = "111"
            try:
                load_dotenv(env_file, override=True)
                self.assertEqual(env_int("TEST_OVER", 0), 555)
            finally:
                os.environ.pop("TEST_OVER", None)
```

- [x] **Step 2: Run test to verify it fails**
  Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'anibon.config'`

- [x] **Step 3: Create `.env` and `scripts/anibon/config.py`**
  Write `.env` at `skills/anibon-timestamper-local/.env` with all 24 `ANIBON_*` keys documented by section, and implement `scripts/anibon/config.py` with `reload_config()` so calling `load_dotenv(..., override=True)` can refresh module constants when `--env-file` is passed.

- [x] **Step 4: Run test to verify it passes**
  Run: `PYTHONPATH=scripts python3 -m unittest tests.test_config -v`
  Expected: PASS (5 tests)

- [x] **Step 5: Commit**
  `git add skills/anibon-timestamper-local/.env skills/anibon-timestamper-local/scripts/anibon/config.py skills/anibon-timestamper-local/tests/test_config.py && git commit -m "feat(local): add .env config file and stdlib loader in anibon/config.py"`

---

### Task 2: Wire `summarizer.py`, `lmstudio.py`, `prompts.py`, `multimodal.py`, `timestamps.py`, and `process_chunks_local.py` to `anibon.config`

**Files:**
- Modify: `scripts/anibon/summarizer.py` (use `DEFAULT_TEMPERATURE`, `PRUNE_MIN_INPUT`, `PRUNE_TARGET_MIN`, `PRUNE_TARGET_MAX`, `PRUNE_MAX_TOKENS`, `PRUNE_TIMEOUT_SEC`, `SUMMARIZER_MAX_TOKENS`, `SUMMARIZER_TIMEOUT_SEC`, `DEFAULT_BLOCK_SIZE`, `BYTE_CAP_LIMIT`)
- Modify: `scripts/anibon/lmstudio.py` (use `PRIMARY_HOST`, `DEFAULT_PORT`, `DEFAULT_MODEL`, `PROBE_TIMEOUT_SEC`, `CHUNK_MAX_TOKENS`, `VISION_TEMPERATURE`, `CHUNK_TIMEOUT_SEC`, `MAX_RETRIES`)
- Modify: `scripts/anibon/prompts.py` (use `ENTITY_CONTEXT_MAX_TOKENS` in `build_chunk_entity_context`)
- Modify: `scripts/anibon/multimodal.py` (use `CHUNK_MAX_TOKENS`, `DEFAULT_TEMPERATURE`, `MULTIMODAL_TIMEOUT_SEC` in `call_multimodal`)
- Modify: `scripts/anibon/timestamps.py` (use `DEDUP_MIN_GAP_SEC`, `DEDUP_MAX_GAP_SEC` in `deduplicate_consecutive_timestamps`)
- Modify: `scripts/process_chunks_local.py` (use `CHUNK_MAX_TOKENS`, `DEFAULT_TEMPERATURE`, `DEFAULT_GROUP_SIZE`, `DEFAULT_BLOCK_SIZE`, `STAMP_COLLISION_SEC`, `MULTIMODAL_TIMEOUT_SEC`; add `--env-file` CLI option that calls `load_dotenv(Path(args.env_file), override=True)`)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: constants and `load_dotenv` from `anibon.config`
- Produces: all existing function signatures remain backward-compatible, with default parameter values sourced from `anibon.config`.

- [x] **Step 1: Add failing test `test_modules_use_config_defaults` in `tests/test_config.py`**

```python
    def test_modules_use_config_defaults(self):
        import inspect
        from anibon import config, summarizer, lmstudio, prompts, multimodal, timestamps

        self.assertEqual(
            inspect.signature(summarizer.run_local_summarizer_pass).parameters["max_tokens"].default,
            config.SUMMARIZER_MAX_TOKENS,
        )
        self.assertEqual(
            inspect.signature(summarizer.prune_essential).parameters["min_input"].default,
            config.PRUNE_MIN_INPUT,
        )
        self.assertEqual(
            inspect.signature(summarizer.enforce_byte_cap).parameters["limit"].default,
            config.BYTE_CAP_LIMIT,
        )
        self.assertEqual(
            inspect.signature(lmstudio.call_local).parameters["timeout"].default,
            config.CHUNK_TIMEOUT_SEC,
        )
        self.assertEqual(
            inspect.signature(prompts.build_chunk_entity_context).parameters["max_tokens"].default,
            config.ENTITY_CONTEXT_MAX_TOKENS,
        )
        self.assertEqual(
            inspect.signature(multimodal.call_multimodal).parameters["timeout"].default,
            config.MULTIMODAL_TIMEOUT_SEC,
        )
        self.assertEqual(
            inspect.signature(timestamps.deduplicate_consecutive_timestamps).parameters["min_gap_sec"].default,
            config.DEDUP_MIN_GAP_SEC,
        )
```

- [x] **Step 2: Implement the config wiring across the 6 files**
  Replace hardcoded default literals in function signatures and internal calls (`prune_essential` `max_tokens=PRUNE_MAX_TOKENS, timeout=PRUNE_TIMEOUT_SEC`, `run_local_summarizer_pass` `timeout=SUMMARIZER_TIMEOUT_SEC`, `process_chunks_local.py` collision spacing `STAMP_COLLISION_SEC` and CLI defaults) with `anibon.config` constants. Add `--env-file` to `process_chunks_local.py`.

- [x] **Step 3: Run full test suite to verify all tests pass**
  Run: `PYTHONPATH=scripts python3 -m unittest discover -s tests -v`
  Expected: PASS (106 tests)

- [x] **Step 4: Update `SKILL.md` to document `.env` and `--env-file`**
  Add a brief note in `SKILL.md` under Quick Commands explaining that token budgets, timeouts, temperatures, pruning bounds, and endpoint defaults live in `.env` (or custom `--env-file`).

- [x] **Step 5: Commit**
  `git add skills/anibon-timestamper-local/ && git commit -m "feat(local): wire all pipeline numeric defaults to .env via anibon.config"`
