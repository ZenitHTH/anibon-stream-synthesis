# Restructure and Modularization of `anibon-timestamper-local` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose the 1,380-line monolithic `process_chunks_local.py` and its surrounding scripts in `skills/anibon-timestamper-local/scripts/` into modular, reusable, test-covered modules under `anibon/` while maintaining 100% backward compatibility and CLI behavior.

**Architecture:** Extract cohesive functional boundaries from `process_chunks_local.py` into dedicated modules in `skills/anibon-timestamper-local/scripts/anibon/`:
1. `anibon/lmstudio.py`: LLM endpoint detection, model resolution, text completions, and multi-modal Vision API caller (`image_url` data URIs for Gemma 3/4 12B Vision, Qwen-VL, etc.).
2. `anibon/websearch.py`: Lightweight DuckDuckGo search with local JSON cache, entity query formatting, and zero external API keys.
3. `anibon/timestamps.py`: Tag normalization, line sanitization, chronological loop breaking, and collision-guarded timestamp validation.
4. `anibon/prompts.py`: Prompt assembly for recursive rolling summary, group batching, World Identity context, and optional web search / vision context injection.
5. `anibon/summarizer.py`: Pass 2 local summarizer, comment part splitting (<3,500 bytes), and Thai Caveman headers formatting.
6. `anibon/state.py`: Session state save/load lifecycle and progress checkpointing.
7. Thin orchestrator `process_chunks_local.py`: Clean CLI entry point routing to execution engines and garbled collection.

**Tech Stack:** Python 3.10+ (Standard library: `urllib.request`, `json`, `re`, `pathlib`, `base64`, `unittest`).

**Spec:** Decompose `skills/anibon-timestamper-local/scripts/process_chunks_local.py` (~1,380 lines) into focused single-responsibility modules in `anibon/`, eliminating duplicated time/chunk code, adding unit test coverage, adding DuckDuckGo web search with caching, and enabling multi-modal vision calling for LM Studio (Gemma-4-12b / vision models).

## Global Constraints

- Zero regressions: CLI arguments (`--mode recursive`, `--mode group`, `--workspace`, `--endpoint`, `--model`, etc.) and output file schemas (`anibon_timestamper_state.json`, `anibon_timestamps.md`, `chunks/chunk_XX.out.json`) must remain 100% identical.
- Zero mandatory external dependencies for core functionality (keep standard library `urllib`, `re`, `json`, `pathlib`, `base64`).
- All scripts must remain executable on macOS, Linux, and Windows runners without path errors.
- UTF-8 standard stream reconfiguring must be preserved.

## Review Focus

1. **Timestamp Validation & Ordering**: Timestamps must be sorted chronologically, within chunk bounds `[start_sec - 60, end_sec + 60]`, with $\ge 45\text{s}$ spacing between adjacent marks.
2. **Backward-compatible Imports**: Any external script or test importing from `process_chunks_local` or `signal_detector` must not break (maintain re-exports where needed).
3. **State File Integrity**: `anibon_timestamper_state.json` must record `current_chunk`, `total_chunks`, `all_timestamps`, `current_topic_title`, and `rolling_summary`.
4. **World Identity Fallback**: Graceful handling when `anibon-world-identity` reference markdown files or `pokemon.db` are absent.
5. **Garbled Collector Handoff**: Auto-trigger of `whisper_dispatcher.py` post-assembly must continue functioning without path resolution failure.

---

### Task 1: Timestamp & Tag Normalization Module (`anibon/timestamps.py`)

Extract tag remapping, timestamp line sanitization, multi-timestamp collision avoidance, and window validation from `process_chunks_local.py` into a reusable module with unit tests.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/timestamps.py`
- Test: `skills/anibon-timestamper-local/tests/test_timestamps.py`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`

- [ ] **Step 1: Write unit tests for timestamp sanitization and validation**
  Cover:
  - `normalize_tag` remapping (`[วิเคราะห์]` → `[Talk]`)
  - `sanitize_timestamp_line` (removes reasoning suffixes, parenthetical noise, word count markers)
  - `validate_timestamps` (filters out-of-bounds timestamps)
  - Multi-timestamp list deduplication and 45-second collision guard
- [ ] **Step 2: Implement `anibon/timestamps.py`**
  Move:
  - `TAGS`, `TAG_REMAP`
  - `normalize_tag(match)`
  - `sanitize_timestamp_line(line)`
  - `parse_timestamps(raw, max_stamps)`
  - `validate_timestamps(stamps, start_sec, end_sec)`
  - `is_continuation(raw)`
- [ ] **Step 3: Run unit tests**
  Verify all tests in `skills/anibon-timestamper-local/tests/test_timestamps.py` pass.
- [ ] **Step 4: Update `process_chunks_local.py` to import from `anibon.timestamps`**
  Keep backward-compatible re-exports in `process_chunks_local.py`.
- [ ] **Step 5: Commit changes**
  `git commit -m "refactor(timestamper-local): extract anibon/timestamps.py module"`

---

### Task 2: LM Studio Client & Vision API Module (`anibon/lmstudio.py`)

Extract endpoint discovery, loaded model resolution, retry backoff, HTTP communication, and multi-modal Vision calling into a clean client module supporting Gemma 3/4 12B Vision, Qwen-VL, etc.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/lmstudio.py`
- Test: `skills/anibon-timestamper-local/tests/test_lmstudio.py`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`

- [ ] **Step 1: Write unit tests for model resolution, text payload, and vision payload**
  Cover:
  - Model auto-resolution from `/v1/models` list
  - Fallback logic when model not found or server unreachable
  - Chat completions payload builder with `SYSTEM_PROMPT`
  - Multi-modal vision payload builder (base64 `image_url` data URI formatting for Gemma/Qwen-VL)
- [ ] **Step 2: Implement `anibon/lmstudio.py`**
  Move & Expand:
  - `SYSTEM_PROMPT`
  - `get_loaded_models(endpoint)`
  - `resolve_model(requested_model, endpoint, force)`
  - `call_local(endpoint, model, prompt, max_tokens, temperature, retries, backoff)`
  - `encode_image_base64(image_path)`
  - `call_vision(endpoint, model, prompt, image_path, max_tokens, temperature)`
- [ ] **Step 3: Run unit tests**
  Verify mock tests in `test_lmstudio.py` pass.
- [ ] **Step 4: Update `process_chunks_local.py` to import from `anibon.lmstudio`**
- [ ] **Step 5: Commit changes**
  `git commit -m "refactor(timestamper-local): extract anibon/lmstudio.py with multi-modal vision support"`

---

### Task 3: DuckDuckGo Web Search Module (`anibon/websearch.py`)

Implement a zero-dependency DuckDuckGo search helper with local caching to look up unknown entities, game/character spellings, or anime episode titles.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/websearch.py`
- Test: `skills/anibon-timestamper-local/tests/test_websearch.py`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/prompts.py`

- [ ] **Step 1: Write unit tests for search query builder and local cache**
  Cover:
  - Cache hit returns cached results without outbound network request
  - Cache miss triggers search and writes to `<workspace>/websearch_cache.json`
  - Query formatting for Thai livestream context (e.g., adding "game wiki", "anime", etc.)
- [ ] **Step 2: Implement `anibon/websearch.py`**
  Add:
  - `load_search_cache(cache_file)`
  - `save_search_cache(cache_file, cache)`
  - `search_duckduckgo(query, max_results, timeout)` (pure `urllib` / DuckDuckGo Lite HTML & REST)
  - `search_entity_context(entity, domain, cache_file)`
- [ ] **Step 3: Run unit tests**
  Verify mock tests in `test_websearch.py` pass.
- [ ] **Step 4: Commit changes**
  `git commit -m "feat(timestamper-local): add anibon/websearch.py with local caching"`

---

### Task 4: Prompts & World Identity Context Module (`anibon/prompts.py`)

Extract prompt construction for recursive mode, group mode, World Identity markdown injection, and optional search/vision context blocks into a dedicated module.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/prompts.py`
- Test: `skills/anibon-timestamper-local/tests/test_prompts.py`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`

- [ ] **Step 1: Write unit tests for prompt building**
  Cover:
  - `build_recursive_prompt` JSON schema with `timestamps` list and continuity flags
  - `build_group_prompt` with previous topic context injection
  - `load_world_identity_context` truncation (`_WI_SNIPPET_LIMIT`) and Pokémon DB note
- [ ] **Step 2: Implement `anibon/prompts.py`**
  Move:
  - `WORLD_IDENTITY_DIR`, `_WI_SNIPPET_LIMIT`
  - `load_world_identity_context(signal, world_identity_dir)`
  - `build_recursive_prompt(...)`
  - `build_group_prompt(...)`
- [ ] **Step 3: Run unit tests**
  Ensure prompt outputs match expected template contracts.
- [ ] **Step 4: Update `process_chunks_local.py` to import from `anibon.prompts`**
- [ ] **Step 5: Commit changes**
  `git commit -m "refactor(timestamper-local): extract anibon/prompts.py module"`

---

### Task 5: Summarizer Pass & Comment Assembly Module (`anibon/summarizer.py`)

Extract Pass 2 assembly, Part splitting under 3,500 bytes (YouTube comment cap safety), and Thai Caveman headers generation into a standalone module.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/summarizer.py`
- Test: `skills/anibon-timestamper-local/tests/test_summarizer.py`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`

- [ ] **Step 1: Write unit tests for part assembly and byte limits**
  Cover:
  - Splitting timestamps into multiple parts when exceeding 3,500 bytes
  - Formatting markdown output with part headers and statistics
  - Header title fallback generation from timestamps
- [ ] **Step 2: Implement `anibon/summarizer.py`**
  Move:
  - `generate_part_summary(stamps)`
  - `run_local_summarizer_pass(stamps, endpoint, model)`
  - `assemble_parts(stamps, part_summaries, output_path, max_bytes)`
- [ ] **Step 3: Run unit tests**
  Verify part splitting and byte calculations pass.
- [ ] **Step 4: Update `process_chunks_local.py` to use `anibon.summarizer`**
- [ ] **Step 5: Commit changes**
  `git commit -m "refactor(timestamper-local): extract anibon/summarizer.py module"`

---

### Task 6: State & Workspace I/O Module (`anibon/state.py` & Multi-modal Loaders)

Consolidate state persistence, chunk discovery, and multimodal context files (LiveChat, Activity, Mood) into clean utilities.

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/state.py`
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`
- Test: `skills/anibon-timestamper-local/tests/test_state.py`

- [ ] **Step 1: Write unit tests for state save/load and multimodal loaders**
- [ ] **Step 2: Implement `anibon/state.py`**
  Move:
  - `load_state(workspace)`
  - `save_state(workspace, state)`
  - `load_chunk_livechat(workspace, chunk_idx)`
  - `load_chunk_activity(workspace, chunk_idx)`
  - `load_chunk_mood(workspace, chunk_idx)`
  - `discover_chunks(workspace)`
- [ ] **Step 3: Update `process_chunks_local.py` to use `anibon.state`**
- [ ] **Step 4: Run full integration check on `process_chunks_local.py` CLI**
  Verify `--help` works and imports resolve without errors.
- [ ] **Step 5: Commit changes**
  `git commit -m "refactor(timestamper-local): extract anibon/state.py and streamline orchestrator"`

---

### Task 7: Directory Cleanup & Re-organization

Clean up symlinks, duplicate scripts, and ensure consistency between `anibon-timestamper-local` and the parent plugin.

**Files:**
- Review: `skills/anibon-timestamper-local/scripts/`
- Documentation: `skills/anibon-timestamper-local/SKILL.md`

- [ ] **Step 1: Verify all symlinks in `scripts/` are valid and working**
  Check `whisper_dispatcher.py`, `pack_timestamps.py`, `check_sections.py`, `audit_gaps.py`, `validate_tags.py`.
- [ ] **Step 2: Run test suite across all new modules**
  `python3 -m unittest discover -s skills/anibon-timestamper-local/tests`
- [ ] **Step 3: Update `SKILL.md` architecture diagram and code references**
- [ ] **Step 4: Commit and push**
  `git commit -m "docs(timestamper-local): update documentation and finalize modular architecture"`
