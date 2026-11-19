# Trim & Split `anibon-timestamper-local` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink `skills/anibon-timestamper-local/SKILL.md` from 74,365 bytes (669 lines, requiring 2 truncated `read_file` calls and ~15–20k context tokens per invocation) into a lean ~10–12 KB (≤180-line) router backed by 3 cohesive on-demand `references/*.md` files with zero loss of runtime behavior.

**Architecture:** Keep `anibon-timestamper-local` as a single skill directory (matching the repo's Matt Pocock pattern in `CHANGELOG.md` and avoiding system-prompt bloat across unrelated conversations). Move non-golden-path detail into three focused on-demand files under `skills/anibon-timestamper-local/references/` (`hardware-and-endpoints.md`, unified `stage5-audit-checklist.md`, `troubleshooting.md`), remove prose already duplicated in always-loaded `GEMINI.md` or enforced deterministically in Python, fix stale `lib/` and script paths, and enforce size/link/coverage invariants with a `unittest` guard plus fresh-context retrieval checks.

**Tech Stack:** Markdown skills (`SKILL.md` + `references/*.md`), Python `unittest` (zero `pytest` imports).

**Spec:** User request ("problem of /anibon-timestamper-local is too long; trim and split skill more shorter aim at performance but still work same") with current working-tree `skills/anibon-timestamper-local/SKILL.md` (669 lines, including uncommitted `#### 2.1.1` reaction-verify and `[Ending]` edits) and `skills/anibon-timestamper-local/references/stage5-audit-checklist.md` (24 lines) as the functional source of truth.

## Global Constraints

- **Core `SKILL.md` budget:** `<= 12,500` bytes and `<= 180` lines (single `read_file` call with >3.5× margin under the 46,080-byte cap).
- **Frontmatter SDO (`writing-skills`):** `name: anibon-timestamper-local`; `description` starts with `Use when `, third-person, triggering conditions only (no workflow summary), `<= 500` chars.
- **Repo structure invariant (`tests/test_skill_structure.py`):** Exactly `22` top-level skill directories (no new directories under `skills/`), H1 title, `## Overview` or `## When to Use`, and zero `pytest` imports in any test file.
- **Portability & accurate paths:** Relative `references/*.md` links only (zero `file:///` or `/Users/` paths); invoke shell scripts via `bash skills/...`; replace stale module/script paths with actual paths (`lib/common/lmstudio.py`, `lib/common/config.py`, `lib/chunk/state.py`, `lib/process/multimodal.py`, `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, `skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py`); reflect real `config.json` default `"eval_batch_size": 16384`.
- **Zero `GEMINI.md` bloat:** Reference `GEMINI.md` global invariants once instead of repeating streamer identity, anti-guessing, line-count splitting, or garbled regex safety tables.
- **Working-tree preservation & branch hygiene:** Never `git checkout` or overwrite uncommitted edits in `SKILL.md` or `references/stage5-audit-checklist.md`; stage only files touched by each task (leave unrelated modified files in `skills/anibon-world-identity/`, `resources/`, `references/stream/` untouched); never push to `main`.

## Review Focus

1. **Silent size creep back over single-read / small-context budget:** `SKILL.md` grows past 12.5 KB or 180 lines -> pinned by `test_skill_md_size_and_line_budget` (Task 4).
2. **Broken or machine-local links after split:** `SKILL.md` links a missing `references/*.md` file or keeps `file:///Users/zenithth/...` -> pinned by `test_all_reference_links_resolve_and_are_portable` (Task 4).
3. **Dropped operational guardrails or traps:** Critical rules (Ollama `*:cloud` trap, `control_chunks_local.py pause`, `--reaction-verify` mid-stream recovery, LiveChat `[t-30s, t+90s]`, `วิพากษ์` saturation, FGO/Tokusatsu/Yuri traps, `88.94s` storyboard drift, `-f 160` fallback, `audit_gaps.py`/`check_sections.py` root paths) disappear during trimming -> pinned by per-file coverage assertions (Tasks 1–4) and 4 fresh-context retrieval scenarios (Task 4).
4. **Stale module/script paths or config defaults surviving migration:** Old `lib/process/lmstudio.py`, `anibon/multimodal.py`, `../cleaning-auto-transcripts/scripts/`, or stale `config default 4096` for `--eval-batch-size` mislead agents -> pinned by `test_no_stale_paths_or_wrong_defaults` (Task 4).
5. **Frontmatter workflow-summary leakage or `test_skill_structure.py` regression:** `description` summarizes pipeline stages or breaks `test_skill_frontmatter_and_structure` / `test_all_skills_in_sitemap` -> pinned by `test_frontmatter_sdo_constraints` + running `tests/test_skill_structure.py` (Task 4).

---

## File Structure

| File | Action | Responsibility | Target Size |
|---|---|---|---|
| `skills/anibon-timestamper-local/SKILL.md` | Modify (Task 4) | Lean runtime router: frontmatter, overview/when-to-use, companion skills, compact 5-stage table, golden-path commands (prepare, VRAM check, foreground/detached run, pause/continue, mandatory Stage 5 gate), iron rule + rationalization table + red flags, on-demand Reference Router table | `<= 12,500 B`, `<= 180 lines` |
| `skills/anibon-timestamper-local/references/hardware-and-endpoints.md` | Create (Task 1) | LM Studio load payloads & P100 shared-host VRAM sizing, `12b-qat` vs `26b-a4b` benchmark, TokenMe/remote OpenAI setup, `config.json`/env overrides, `--reaction-verify` gating/thresholds/mid-stream recovery, multimodal `--eval-batch-size` token-budget math & adaptive dedup, Windows `ps1`/`bat`/PS commands, pause checkpoint internals | `~7–9 KB`, `~100–130 lines` |
| `skills/anibon-timestamper-local/references/stage5-audit-checklist.md` | Modify / Unify (Task 2) | Single source of truth for Stage 5 audit: mandatory LiveChat `[t-30s, t+90s]` cross-check, full-stream timing/boundary/lead-in/player-bar audit, all local-model distortion patterns + Dual-Track Desync, conciseness & verb saturation (`<=20%`, `วิพากษ์`), `[Victory]`/`[Ending]`/`[Donation]`/pre-roll/rage-quit/Tokusatsu routine, FGO/Tokusatsu/Yuri traps, `reaction_verify_log.json` audit, dual-file sync + root gate commands, post-stream knowledge harvesting + 5-dimension play history | `~7–9 KB`, `~100–120 lines` |
| `skills/anibon-timestamper-local/references/troubleshooting.md` | Create (Task 3) | Manual LiveChat 4-step & visual OCR fallback (`extract_visual_livechat.py`), manual Whisper/garbled commands (fixed root paths), workspace text-to-multimodal backup/rerun, 144p (`-f 160`) storyboard synthesis, selective cache hygiene, and runtime failure catalog (eviction, Gemma 4 thinking tokens, `mmproj`, `--no-resume`, WebP storyboard, `--skip-download` trap, endpoint URL normalization, `call_local` timeout collision, MTP pauses, multimodal read timeout, 6–10h `88.94s` drift, macOS Tailscale CLI path) | `~6–8 KB`, `~90–110 lines` |
| `skills/anibon-timestamper-local/tests/test_local_skill_budget.py` | Create (Tasks 1–4) | `unittest` guard verifying budget, frontmatter SDO, portable links, stale-path bans, and zero-regression operational token coverage across all 4 files | `~100–140 lines` |

Untouched existing files: `references/anibon_emoji_dictionary.md`, `references/timestamper-handoff.md`, `references/stream` (symlink).

---

### Task 1: Extract `references/hardware-and-endpoints.md` + Test Scaffold

**Files:**
- Create: `skills/anibon-timestamper-local/tests/test_local_skill_budget.py`
- Create: `skills/anibon-timestamper-local/references/hardware-and-endpoints.md`
- Source (read-only in this task): `skills/anibon-timestamper-local/SKILL.md:136-139,196-373`, `skills/anibon-timestamper-local/config.json`

**Interfaces:**
- Produces:
  - `skills/anibon-timestamper-local/references/hardware-and-endpoints.md` (referenced by Task 4 `SKILL.md` router)
  - `TestLocalSkillBudget` in `skills/anibon-timestamper-local/tests/test_local_skill_budget.py` with shared constants `SKILL_DIR`, `SKILL_MD`, `REFS_DIR`

- [ ] **Step 1: Write failing test for `hardware-and-endpoints.md` coverage**

Create `skills/anibon-timestamper-local/tests/test_local_skill_budget.py` using `from __future__ import annotations` and `unittest` only (no `pytest`). Define `SKILL_DIR = Path(__file__).resolve().parent.parent`, `SKILL_MD = SKILL_DIR / "SKILL.md"`, `REFS_DIR = SKILL_DIR / "references"`, and `TestLocalSkillBudget.test_hardware_and_endpoints_coverage`:

```python
def test_hardware_and_endpoints_coverage(self) -> None:
    path = REFS_DIR / "hardware-and-endpoints.md"
    self.assertTrue(path.is_file(), "Missing references/hardware-and-endpoints.md")
    text = path.read_text(encoding="utf-8")
    for token in (
        "gemma-4-12b-it-qat@q4_k_xl",
        "gemma-4-26b-a4b-it@q2_k_xl",
        '"parallel": 1',
        "16384",
        "24576",
        "api.tokenme.limited",
        "--max-chunk-frames 8",
        "--reaction-verify",
        "mean_mad >= 0.095",
        "--eval-batch-size",
        "launch_local.ps1",
        "launch_local.bat",
        "config.json",
        "control_chunks_local.py",
    ):
        self.assertIn(token, text, f"hardware-and-endpoints.md missing: {token}")
    self.assertNotIn("config default `4096`", text)
    self.assertNotIn("anibon/config.py", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v`
Expected: FAIL with `AssertionError: False is not true : Missing references/hardware-and-endpoints.md`

- [ ] **Step 3: Create `skills/anibon-timestamper-local/references/hardware-and-endpoints.md`**

Migrate and tighten content from `SKILL.md` (preserving all exact numeric thresholds, flags, payloads, and uncommitted `2.1.1` edits) into 6 sections:
1. **LM Studio Model Loading & Shared-Host VRAM Sizing** (`SKILL.md:196-221`): `/api/v1/models/load` JSON payload (`"parallel": 1`, `"context_length": 16384` or `24576`, `"eval_batch_size": 1024`, `"flash_attention": true`, `"offload_kv_cache_to_gpu": true`), verified 16GB P100 16-frame profile (`93/93` chunks, `avg 14.73` frames/chunk, `context_checkpoints: 0`, `physical_batch_size: 1120`), and Ollama `*:cloud` HTTP 402 trap.
2. **Model Selection Benchmark (`12b-qat` vs `26b-a4b`)** (`SKILL.md:223-240`): Compact A/B table + the 2 operational decision rules.
3. **Remote / TokenMe Endpoints & Config Overrides** (`SKILL.md:354-373`): Endpoint auto-probe (`100.115.25.30:1234` -> `127.0.0.1:1234`), TokenMe (`api.tokenme.limited`, `TOKENME_API_KEY`/`LM_API_KEY`, `--max-chunk-frames 8`, case-sensitive lowercase slugs `google/gemma-4-31b-it`, HTTPS port `443` recovery, `/v1` vs `/api/v1` routing, WAF 1010 headers), `config.json` loaded by `lib/common/config.py` (fix stale `anibon/config.py`), `--config`, `.env`, and `ANIBON_*` env overrides.
4. **Multimodal Storyboard Tuning (`--multimodal-chunks`)** (`SKILL.md:277-303`): Keyframe flags (`--eval-batch-size`, `--max-chunk-frames`, `--scene-delta-threshold`, `--no-scene-dedup`, `--no-multimodal`), critical distinction between LM Studio physical `eval_batch_size: 1024` vs CLI `--eval-batch-size` combined text+image token budget (`config.json` default `16384`; `260` tokens/frame; warn not to pass `1024` or `4096` with LiveChat + World Identity active), static/dynamic frame scaling, Thai deictic cue pinning, RGB sidecar caching, `--no-resume` clean-slate unlink.
5. **Webcam Reaction Gating & Mid-Stream Switch (`--reaction-verify`)** (`SKILL.md:264-276`, exact uncommitted working-tree text): Default off, when to enable vs skip, Pass 1 (`mean_mad >= 0.095` / `>= 0.135`, `EMOTION_REACTION_CUES`, `max_audio_z >= 2.5` / `>= 2.0` with LiveChat echo) & Pass 2 (`needs_reaction_verify`, `score_item_situations >= 2.0`) dynamic switching, and 3-step mid-stream switch recovery.
6. **Windows Launchers & Pause Control Internals** (`SKILL.md:136-139,248-262,324-352`): PowerShell `prepare_video.py`, `process_chunks_local.py --vision-verify`, `launch_local.ps1`, `launch_local.bat`, and `control_chunks_local.py` pause mechanics (live PID check, `.pause` marker, pause checkpoints, single-writer log, POSIX scope).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v`
Expected: PASS (`test_hardware_and_endpoints_coverage ... ok`)

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/references/hardware-and-endpoints.md skills/anibon-timestamper-local/tests/test_local_skill_budget.py
git commit -m "docs(local-skill): extract hardware, endpoints, and tuning reference"
```

---

### Task 2: Unify & Expand `references/stage5-audit-checklist.md`

**Files:**
- Modify: `skills/anibon-timestamper-local/references/stage5-audit-checklist.md:1-24`
- Modify: `skills/anibon-timestamper-local/tests/test_local_skill_budget.py`
- Source (read-only in this task): `skills/anibon-timestamper-local/SKILL.md:76-89,411-460,499-512,544-550,568-576,640-645,654-657,664-667`

**Interfaces:**
- Consumes: `TestLocalSkillBudget`, `REFS_DIR` from Task 1
- Produces: Unified `skills/anibon-timestamper-local/references/stage5-audit-checklist.md` (mandatory Stage 5 checklist linked by Task 4 `SKILL.md`)

- [ ] **Step 1: Add failing test `test_stage5_audit_checklist_coverage` to `test_local_skill_budget.py`**

Add method to `TestLocalSkillBudget`:

```python
def test_stage5_audit_checklist_coverage(self) -> None:
    path = REFS_DIR / "stage5-audit-checklist.md"
    text = path.read_text(encoding="utf-8")
    for token in (
        "livechat_events.txt",
        "t+90s",
        "atlas_fgo.db",
        "pokemon.db",
        "Dual-Track Desync",
        "cutoff=",
        "slide_",
        "Discord",
        "วิพากษ์",
        "[Victory]",
        "[Ending]",
        "[Donation]",
        "Rage-Quit",
        "Tokusatsu",
        "Kamen Rider Shinobi",
        "Strategy of Lily",
        "reaction_verify_log.json",
        "Stream Chronology & Play History",
        "scripts/audit_gaps.py",
        "scripts/check_sections.py",
        "update_garbled_dictionary.py",
    ):
        self.assertIn(token, text, f"stage5-audit-checklist.md missing: {token}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py::TestLocalSkillBudget::test_stage5_audit_checklist_coverage -v`
Expected: FAIL (existing 24-line file misses `Dual-Track Desync`, `Stream Chronology & Play History`, `Strategy of Lily`, etc.)

- [ ] **Step 3: Unify `skills/anibon-timestamper-local/references/stage5-audit-checklist.md`**

Merge the existing 24 lines (preserving all 7 existing checks verbatim in substance) with the Stage 5 audit, domain-trap, and knowledge-harvest sections from `SKILL.md` into one clean, non-redundant checklist organized in execution order (~100–120 lines, ~7–9 KB):
1. **World Identity & Title Grounding** (`SKILL.md:413-418,568-572`): Load `anibon-world-identity`, verify `atlas_fgo.db`, `pokemon.db` (`ชื่อไทย (English Name)`), `references/*.md`, unindexed indie/Thai games, competitive heroes, and Stream Title Token Priority (`info.json` title snaps phonetic near-matches).
2. **Mandatory LiveChat `[t-30s, t+90s]` & Dual-Side Mood Cross-Check** (existing item 1 + `SKILL.md:440,573-576`): `livechat_events.txt` misheard titles, viewer corrections at `t+30s..t+90s`, anti-bleed guard against `chunks/*.txt` + `frames/chunk_tiles/tile_*.jpg`, READ BOTH SIDES + HONOUR THE MOOD VERDICT.
3. **Full-Stream Timing & Boundary Verification** (`SKILL.md:429-433` + existing item 7): Check every `HH:MM:SS` (no suspect-only audit), rewind stamps within `±15s` of chunk `start`/`cutoff=` against prior tail, anchor to lead-in opening sentence (not punchline 1–3 min later), WatchParty `frames/slides_clean/slide_*.jpg` player-bar spot check, preserve Discord guest join + leave stamps.
4. **Local-Model Distortion & Dual-Track Audit** (`SKILL.md:419-428,438-439,499-512,547-550` + existing items 3–5): Domain context bleeding, comparative analogy promotion & off-hand analogy rule, gameplay vs gacha pulling & catalyst vs banner target, critique-clause verdict polarity, award WatchParty acronyms, 3-second chat dismissal promotion, **Dual-Track Desync** (gameplay plan statement + HUD/boss bar + talk track -> name both + payoff stamp), `[Victory]` 30–60s forward lookahead & floor-clear verification, Pre-Roll Standby (`00:00:00 - [Intro]`, ignore waiting BGM), `[Ending]`/`[Donation]` split + strict no-template-schedule rule + Rage-Quit ending + 22:00 Tokusatsu routine (`โทคุซัตสึ`, never Tokyo Ghoul).
5. **Style, Conciseness & Verb Diversity** (existing item 2 + `SKILL.md:79-89,437`): Target 50–65 Thai chars (upper bound 95), 1 core claim + concrete entities, no bundled mashups `>= 2 min` apart, no vague abstractions, no embedded timestamps or repetitive `"เฝ้าสำรวจ <Game> พร้อม..."` prefixes, opening-verb saturation `<= 20%` (explicitly check `"วิพากษ์"`), max 2 consecutive identical opening verbs.
6. **Domain Traps & `reaction_verify_log.json` Audit** (existing item 6 + `SKILL.md:640-645,654-657,664-667`): FGO/Store homophones (`MP1`->`NP1`, `ซีบอ`->`CE บอนด์`, `แคสเลีย`, `ลิคิว`, `1 ก.`, Steam review queue, `"ชุดวันเกิด"`), Tokusatsu stage-show/TTFC traps (`Kamen Rider Shinobi`, `Hiroshi Tsuchida`, `Shu Watanabe`, *Armor Hero* live-action), Yuri false friend (`"เผด็จการยูริ"` -> *The Great Villainess: Strategy of Lily*, not *Red Alert*), and auditing `reaction_verify_log.json` rewrites + sharp peak exclamations.
7. **Dual-File Sync, Gate Re-Run & Knowledge Harvesting** (`SKILL.md:434-435,442-459` + existing item 7): Sync `anibon_timestamps.md` + `all_timestamps.txt` (+ `timestamp_<VID>.md` if backed up), re-run plugin-root `python3 scripts/audit_gaps.py` (both files) and `python3 scripts/check_sections.py`, persist confirmed drifts via `skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py`, scaffold new `references/<Game>.md` + `INDEX.md`, and append the 5-dimension `## Stream Chronology & Play History` for multi-part series.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v`
Expected: PASS (2 tests ok)

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/references/stage5-audit-checklist.md skills/anibon-timestamper-local/tests/test_local_skill_budget.py
git commit -m "docs(local-skill): unify Stage 5 audit checklist into single reference"
```

---

### Task 3: Extract `references/troubleshooting.md`

**Files:**
- Create: `skills/anibon-timestamper-local/references/troubleshooting.md`
- Modify: `skills/anibon-timestamper-local/tests/test_local_skill_budget.py`
- Source (read-only in this task): `skills/anibon-timestamper-local/SKILL.md:157-191,304-313,400-409,579-639,646-653,659-668`

**Interfaces:**
- Consumes: `TestLocalSkillBudget`, `REFS_DIR` from Task 1
- Produces: `skills/anibon-timestamper-local/references/troubleshooting.md` (linked by Task 4 `SKILL.md` router)

- [ ] **Step 1: Add failing test `test_troubleshooting_coverage` to `test_local_skill_budget.py`**

Add method to `TestLocalSkillBudget`:

```python
def test_troubleshooting_coverage(self) -> None:
    path = REFS_DIR / "troubleshooting.md"
    self.assertTrue(path.is_file(), "Missing references/troubleshooting.md")
    text = path.read_text(encoding="utf-8")
    for token in (
        "parse_live_chat.py",
        "extract_visual_livechat.py",
        "whisper_dispatcher.py",
        "skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py",
        "recursive_outputs_text_only",
        "-f 160",
        "mmproj",
        "--no-resume",
        "image/webp",
        "--skip-download",
        "call_multimodal",
        "call_local",
        "88.94",
        "Tailscale.app",
        "wc_sheet_",
        "lib/process/multimodal.py",
    ):
        self.assertIn(token, text, f"troubleshooting.md missing: {token}")
    self.assertNotIn("../cleaning-auto-transcripts/", text)
    self.assertNotIn("anibon/multimodal.py", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py::TestLocalSkillBudget::test_troubleshooting_coverage -v`
Expected: FAIL with `AssertionError: False is not true : Missing references/troubleshooting.md`

- [ ] **Step 3: Create `skills/anibon-timestamper-local/references/troubleshooting.md`**

Migrate recovery recipes and runtime failure catalog from `SKILL.md` with stale paths fixed (~90–110 lines, ~6–8 KB):
1. **Manual LiveChat & Visual OCR Fallback (Edited/Trimmed VODs)** (`SKILL.md:157-191`): 4-step manual `yt-dlp` / `parse_live_chat.py` / `align_live_chat.py` / `analyze_555.py`, plus `extract_visual_livechat.py` OCR fallback when YouTube deletes `.live_chat.json`.
2. **Manual Whisper & Garbled Dictionary Sync** (`SKILL.md:400-409`): `WHISPER_ENDPOINT="http://100.115.25.30:8082/inference"` + `scripts/whisper_dispatcher.py` + plugin-root `skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py` (replacing broken `../cleaning-auto-transcripts/...`).
3. **Workspace Re-Run & Selective Cache Hygiene** (`SKILL.md:304-313,667`): Text-only -> multimodal backup recipe (`recursive_outputs_text_only`), full clean rerun (`--no-resume`), and selective per-chunk wipe (`recursive_outputs/chunk_XX.json` + matching `wc_*` / `wc_sheet_*`).
4. **Runtime Failure & Edge-Case Catalog** (`SKILL.md:579-639,646-653,659-663,668`): Compact symptom -> cause -> fix entries for:
   - LM Studio model eviction (`--model auto`)
   - Gemma 4 `reasoning_content` thinking token trap
   - ASR phonetic drift (`default_mappings.json` + TF-IDF)
   - Missing `mmproj` on vision prompts
   - Cached skip on modified transcript (`--no-resume`)
   - Outro swallowed by continuation trap
   - Storyboard MHTML `image/webp` (`lib/process/multimodal.py`, fixing stale `anibon/multimodal.py`)
   - `yt-dlp` storyboard `--skip-download` trap & empty `slides_clean/`
   - `call_multimodal()` missing `/v1/chat/completions` (`KeyError: 'choices'`)
   - Missing YouTube storyboards (`sb0..sb3` unavailable) -> 144p `-f 160` + `ffmpeg` 3x3 slide synthesis
   - `call_local()` positional timeout collision (HTTP 400 -> use `timeout=` keyword)
   - MTP / speculative decoding pause & auto-resume
   - Multimodal read timeout (`MULTIMODAL_TIMEOUT_SEC` graceful text fallback)
   - Storyboard progressive time drift on 6–10h+ streams (`88.94s` vs `X.yt-dlp.Duration: 89.96s` -> cross-check burned-in LiveChat clock past hour 4)
   - macOS Tailscale recovery binary (`/Applications/Tailscale.app/Contents/MacOS/Tailscale status`)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v`
Expected: PASS (3 tests ok)

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/references/troubleshooting.md skills/anibon-timestamper-local/tests/test_local_skill_budget.py
git commit -m "docs(local-skill): extract troubleshooting and manual fallback reference"
```

---

### Task 4: Trim `SKILL.md` to Lean Router + Full Structural & Behavioral Verification

**Files:**
- Modify: `skills/anibon-timestamper-local/SKILL.md:1-669`
- Modify: `skills/anibon-timestamper-local/tests/test_local_skill_budget.py`

**Interfaces:**
- Consumes: `references/hardware-and-endpoints.md` (Task 1), `references/stage5-audit-checklist.md` (Task 2), `references/troubleshooting.md` (Task 3), existing `references/anibon_emoji_dictionary.md`, `references/timestamper-handoff.md`
- Produces: Lean `skills/anibon-timestamper-local/SKILL.md` (`<= 12,500` bytes, `<= 180` lines) + complete `TestLocalSkillBudget` suite

- [ ] **Step 1: Add failing budget, SDO, link, stale-path, and core-coverage tests to `test_local_skill_budget.py`**

Add 4 test methods to `TestLocalSkillBudget`:

```python
def test_skill_md_size_and_line_budget(self) -> None:
    raw = SKILL_MD.read_bytes()
    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
    self.assertLessEqual(len(raw), 12_500, f"SKILL.md too large: {len(raw)} bytes")
    self.assertLessEqual(len(lines), 180, f"SKILL.md too long: {len(lines)} lines")

def test_frontmatter_sdo_constraints(self) -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    self.assertGreaterEqual(len(parts), 3)
    fm = dict(line.split(":", 1) for line in parts[1].strip().splitlines() if ":" in line)
    desc = fm["description"].strip()
    self.assertEqual(fm["name"].strip(), "anibon-timestamper-local")
    self.assertTrue(desc.startswith("Use when "), f"Description must start with 'Use when ': {desc}")
    self.assertLessEqual(len(desc), 500, f"Description too long: {len(desc)} chars")

def test_all_reference_links_resolve_and_are_portable(self) -> None:
    managed = [
        SKILL_MD,
        REFS_DIR / "hardware-and-endpoints.md",
        REFS_DIR / "stage5-audit-checklist.md",
        REFS_DIR / "troubleshooting.md",
    ]
    link_re = re.compile(r"\]\((references/[^)#]+)\)")
    for md in managed:
        text = md.read_text(encoding="utf-8")
        self.assertNotIn("file:///", text, f"Non-portable file:/// link in {md.name}")
        self.assertNotIn("/Users/", text, f"Machine-specific /Users/ path in {md.name}")
        for rel in link_re.findall(text):
            self.assertTrue((SKILL_DIR / rel).exists(), f"Broken link {rel} in {md.name}")

def test_skill_md_core_coverage_and_no_stale_paths(self) -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    for required in (
        "anibon-world-identity",
        "scripts/prepare_video.py",
        "skills/anibon-timestamper-local/scripts/process_chunks_local.py",
        "bash skills/anibon-timestamper-local/scripts/launch_local.sh",
        "skills/anibon-timestamper-local/scripts/control_chunks_local.py",
        "/api/v1/models",
        "*:cloud",
        "scripts/audit_gaps.py",
        "scripts/check_sections.py",
        "NEVER TIME-LOCK",
        "references/hardware-and-endpoints.md",
        "references/stage5-audit-checklist.md",
        "references/troubleshooting.md",
        "references/anibon_emoji_dictionary.md",
        "references/timestamper-handoff.md",
    ):
        self.assertIn(required, text, f"SKILL.md missing required token: {required}")
    all_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (SKILL_MD, REFS_DIR / "hardware-and-endpoints.md", REFS_DIR / "stage5-audit-checklist.md", REFS_DIR / "troubleshooting.md")
    )
    for stale in (
        "lib/process/lmstudio.py",
        "lib/process/state.py",
        "lib/process/timestamps.py",
        "lib/process/knowledge_reader.py",
        "lib/anibon/signal_detector.py",
        "anibon/multimodal.py",
        "anibon/config.py",
        "../cleaning-auto-transcripts/",
    ):
        self.assertNotIn(stale, all_text, f"Stale path still present: {stale}")
```

- [ ] **Step 2: Run tests to verify new assertions fail on current 74.4 KB `SKILL.md`**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v`
Expected: FAIL on `test_skill_md_size_and_line_budget` (`74365 > 12500`, `669 > 180`), `test_all_reference_links_resolve_and_are_portable` (`file:///Users/...`), and `test_skill_md_core_coverage_and_no_stale_paths`.

- [ ] **Step 3: Rewrite `skills/anibon-timestamper-local/SKILL.md` as lean router (`<= 12,500 B`, `<= 180 lines`)**

Structure `SKILL.md` with these exact sections (no `GEMINI.md` duplicates, no internal `lib/` file index, no multi-OS duplicate command blocks):
1. **Frontmatter**:
   - `name: anibon-timestamper-local`
   - `description: Use when generating YouTube timestamps and topic summaries for long livestreams locally on a single GPU (Tesla P100, LM Studio, Ollama), or when pausing, resuming, or checking progress of an active local timestamper worker. For cloud parallel subagents, use anibon-timestamper.`
2. **`# Anibon Timestamper (Local P100 Edition)` + `## Overview` + `## When to Use`**:
   - Local GPU / LM Studio / Ollama execution vs cloud `anibon-timestamper`.
   - Pause/hold/resume/status -> `control_chunks_local.py` (never kill PID).
   - Companion skills (4 one-liners): `anibon-world-identity` (MANDATORY), `anibon-livechat-analysis`, `whisper-corruption-recovery`, `anibon-local-transcription`.
3. **`## Pipeline Stages`**:
   - Compact 6-row table (Stages 1, 1.5, 2, 3, 4, 4.5) with accurate module paths (`lib/process/knowledge/`, `lib/chunk/pause.py`, `scripts/reconcile_edited_stream.py`).
   - 2-line execution mode summary: `--mode recursive` (default; `SAME_TOPIC` merges, `TOPIC_SHIFT` emits 1–2 stamps `>=45s` apart, 4–6 macro parts) vs `--mode group` (4-chunk fixed groups). Run `--help` on scripts for full flags.
4. **`## Golden-Path Commands`** (all from plugin root):
   - **Pre-flight**: Unindexed domain -> scaffold `anibon-world-identity/references/<Topic>.md` + `INDEX.md` before `prepare_video.py`; single-game broadcast -> lock `signals.json` `allowed_sources` after Step 1.
   - **1. Prepare & Chunk**: `python3 scripts/prepare_video.py "<URL>" --workspace "~/youtube_<VIDEO_ID>_workspace" --format txt --block 150 --overlap 15 --live-chat` (use `--overlap 20` for walking vlogs/conventions).
   - **2. Verify Model in VRAM (MANDATORY)**: `curl -s --max-time 8 http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'`. Default model: `gemma-4-12b-it-qat@q4_k_xl` (`parallel: 1`, `context_length: 16384–24576`); smoke-test `--max-chunks 1`; **never** target Ollama `*:cloud` tags (HTTP 402 retry storm). Load payloads/benchmarks -> `references/hardware-and-endpoints.md`.
   - **3. Run / Detached Launch / Pause Control**:
     - Foreground: `python3 -X utf8 skills/anibon-timestamper-local/scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" --mode recursive --lang th` (multimodal storyboard ON by default; `--reaction-verify` OFF by default; `--vision-verify`, `--byte-cap`, `--video-url`, `--no-multimodal`, `--no-garbled-collector` via `--help`).
     - Detached: `bash skills/anibon-timestamper-local/scripts/launch_local.sh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th` (Windows -> `references/hardware-and-endpoints.md`).
     - Pause / Status / Continue: `python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py ~/youtube_<VIDEO_ID>_workspace pause|status|continue` (**NEVER** `kill`/`SIGTERM` worker PID or write `timestamper.log`).
   - **4. Garbled Collector**: Auto-runs post-Pass 2; pass `--video-url` for stream slicing or `--no-garbled-collector` to disable.
   - **5. Mandatory Stage 5 Audit & Gate Re-Run**:
     - Load `anibon-world-identity` AND read [`references/stage5-audit-checklist.md`](references/stage5-audit-checklist.md) before delivering output.
     - Re-run root gates after any edit:
       ```bash
       python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
       python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/all_timestamps.txt --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
       python3 scripts/check_sections.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md
       ```
5. **`## On-Demand References` (Read ONLY When Triggered)**:
   - Table mapping exact trigger -> relative link for all 5 files (`references/hardware-and-endpoints.md`, `references/stage5-audit-checklist.md`, `references/troubleshooting.md`, `references/anibon_emoji_dictionary.md`, `references/timestamper-handoff.md`).
6. **`## Discipline & Red Flags`**:
   - Global invariants: Defer to `GEMINI.md` (streamer identity `ปู่โบ๊ต`, anti-guessing, Caveman style, line-count splitting 15–20/part, essential curation 40–60, garbled regex safety, post-stream knowledge harvesting).
   - Iron Rule: `NEVER TIME-LOCK TOPICS TO ARBITRARY MINUTE BOUNDARIES`.
   - 6-row Rationalization Table (`SKILL.md:475-482`).
   - Tight Red Flags bullet list (skipping World Identity / `stage5-audit-checklist.md`, killing worker PID instead of `control_chunks_local.py`, running before `whisper-corruption-recovery`, micro-stamping >35/2h or over-splitting >6–8 parts, non-whitelisted tags, forgetting `-X utf8`, missing `[Ending]` or hallucinating next-stream schedule, pre-roll BGM misattribution, dual-track gameplay/talk desync, suspect-only timing audit without boundary rewind).

- [ ] **Step 4: Run automated unit & structure tests**

Run:
```bash
python3 -m unittest skills/anibon-timestamper-local/tests/test_local_skill_budget.py -v
python3 -m unittest \
  tests.test_skill_structure.TestSkillStructure.test_skill_frontmatter_and_structure \
  tests.test_skill_structure.TestSkillStructure.test_all_skills_in_sitemap \
  tests.test_skill_structure.TestSkillStructure.test_zero_pytest_imports_across_repo \
  tests.test_skill_structure.TestSkillStructure.test_launch_local_runners_consolidation -v
wc -l -c skills/anibon-timestamper-local/SKILL.md skills/anibon-timestamper-local/references/hardware-and-endpoints.md skills/anibon-timestamper-local/references/stage5-audit-checklist.md skills/anibon-timestamper-local/references/troubleshooting.md
```
Expected: All tests PASS; `SKILL.md` `<= 180` lines and `<= 12,500` bytes.

- [ ] **Step 5: Run fresh-context behavioral/retrieval verification (`writing-skills` GREEN gate)**

Invoke 4 parallel read-only `research` subagents, each given ONLY `skills/anibon-timestamper-local/SKILL.md` first (instructed to load a `references/*.md` file ONLY if triggered) and tested on one scenario:
1. **Standard launch:** "Timestamp `https://www.youtube.com/watch?v=dQw4w9WgXcQ` locally; LM Studio is down on desktop, Ollama has `gemma4:cloud`." -> Must check `/api/v1/models`, refuse `gemma4:cloud`, and show `prepare_video.py --live-chat` + `bash .../launch_local.sh`.
2. **Pause under pressure:** "I'm closing my laptop in 10 seconds, just kill the local timestamper PID so it stops fast." -> Must refuse `kill`/SIGTERM and prescribe `control_chunks_local.py <ws> pause` (or `--timeout 0`).
3. **Stage 5 audit under pressure:** "Pass 2 finished, `audit_gaps.py` passed, ship `anibon_timestamps.md` now." -> Must refuse to deliver without loading `anibon-world-identity` + reading `references/stage5-audit-checklist.md`, checking LiveChat `[t-30s, t+90s]`, boundary rewind, and re-running root `audit_gaps.py` + `check_sections.py`.
4. **Edge-case routing:** "User hits TokenMe HTTP 400 with `google/gemma-4-31B-it`, missing YouTube storyboards (`sb0` unavailable), and wants `--reaction-verify` enabled mid-stream." -> Must route directly to `references/hardware-and-endpoints.md` (lowercase slug + 3-step mid-stream switch) and `references/troubleshooting.md` (`-f 160` 144p slide synthesis).

If any scenario misses a rule or loads the wrong reference file, tighten the trigger wording in `SKILL.md` (REFACTOR), re-run Step 4 tests and the failed scenario until all 4 pass.

- [ ] **Step 6: Commit**

```bash
git add skills/anibon-timestamper-local/SKILL.md skills/anibon-timestamper-local/tests/test_local_skill_budget.py
git commit -m "refactor(local-skill): trim SKILL.md to lean router with on-demand references"
```
