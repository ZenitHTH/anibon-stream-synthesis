# ✅ Restructure Plan: anibon-stream-synthesis — COMPLETE

**Date**: 2026-07-27
**Files**: 51 → 35 .py files (16 removed), 19 dead scripts + 2 tests + 7 sdd artifacts deleted
**Lib**: 9 new `lib/anibon/` modules created
**Symlinks**: 2 divergent copies replaced
**Path fixes**: 7 broken SKILL.md refs + 4 detect_topics refs updated

---

## Phase 0: Fix Broken Cross-Skill Paths

These SKILL.md files reference `scripts/` they **don't own** — scripts exist elsewhere.

| SKILL.md | Line | Current ref | Script lives in | Fix |
|---|---|---|---|---|
| `anibon-world-identity/SKILL.md` | 21 | `scripts/fetch_story_ref.py` | `anibon-timestamper/scripts/` | Change to `../anibon-timestamper/scripts/fetch_story_ref.py` |
| same | 27 | `scripts/align_ref_timeline.py` | same | same |
| same | 45 | `scripts/fetch_story_ref.py` | same | same |
| same | 57-58 | `scripts/fetch_fgo_db.py` | same | same |
| same | 59-60 | `scripts/fetch_ygo_db.py` | same | same |
| `anibon-local-transcription/SKILL.md` | 36 | `scripts/clean_transcript.py` | `cleaning-auto-transcripts/scripts/` | Change to `../cleaning-auto-transcripts/scripts/clean_transcript.py` |

> **Note**: `anibon-world-identity` also references `skills/reference/FGO and DATA/` and `skills/reference/Yu-Gi-Oh DATA/` — these paths are relative to *timestamper* root, not world-identity. If we fix the script paths, these data paths also need adjusting.

---

## Phase 1: Nuke Dead Weight

### 1a. Delete root `scripts/` directory
- **13 files**, 0 consumers (no SKILL.md, no hooks, no config references it)
- All 13 are copies of files in skill-local `scripts/` dirs
- One file (`pack_timestamps.py`) has diverged from all copies — its `--break-at` feature must be merged into timestamper's copy first
- **After merge, delete root scripts/**

### 1b. Delete all `detect_topics.py` (3 files)
- All 3 variants marked DEPRECATED
- Replacement: `detect_signals.py`
- Locations:
  - `scripts/detect_topics.py` (dies with root scripts/)
  - `skills/anibon-timestamper/scripts/detect_topics.py`
  - `skills/anibon-timestamper-local/scripts/detect_topics.py`
- Update SKILL.md reference: `anibon-timestamper-local/SKILL.md:126`

### 1c. Delete `analyze_transcript.py` (1 file)
- **`skills/anibon-timestamper/scripts/analyze_transcript.py`** — 61 lines
- Has test (`test_analyze_transcript.py`) but zero SKILL.md consumers
- Never called from any skill pipeline. Dead code.
- Delete test file too: `tests/test_analyze_transcript.py`

### 1d. Delete `assemble_timestamps.py` (2 files)
- **`scripts/assemble_timestamps.py`** (root — dies with root scripts/)
- **`skills/anibon-timestamper/scripts/assemble_timestamps.py`** — has test, but no SKILL.md consumer
- `pack_timestamps.py` outputs parts.json directly — assemble_timestamps was supposed to reassemble but pipeline skips it
- Delete test file too: `tests/test_assemble_timestamps.py`

### 1e. Clean `.superpowers/sdd/` (7 stale artifact files)
```
review-2ca8082..683db1b.diff
review-c5db772..2ca8082.diff
review-c5db772..74b2d53.diff
review-c5db772..86fbbaf.diff
task-1-brief.md / task-1-report.md
task-2-brief.md / task-2-report.md
```

### 1f. Add `__pycache__` and `.DS_Store` to `.gitignore`

---

## Phase 2: Reconcile Divergent Copies

### 2a. `pack_timestamps.py` — 3 variants
| Copy | Features | Action |
|---|---|---|
| root `scripts/` | greedy fill, `--break-at` | MERGE `--break-at` into timestamper, then DELETE |
| timestamper | DP balanced partition, `load_tag_macros()`, `_load_garbled_cleaner()` | KEEP as canonical |
| timestamper-local | simple greedy, no DP, no resources | REPLACE with symlink to timestamper copy |

### 2b. `detect_signals.py` — 2 completely different scripts
| Copy | Algorithm | Action |
|---|---|---|
| root `scripts/` | TF-IDF frequency-based (pure math, no deps) | KEEP as root canonical |
| timestamper | Knowledge-base + Wikipedia API + git commit | KEEP as skill-local (has web deps) |
These are different tools with same name — rename one:

### 2c. `assemble_timestamps.py` — 2 completely different
| Copy | Input | Action |
|---|---|---|
| root `scripts/` | Takes `parts.json`, wraps in separator blocks | DELETE (root scripts/ dies) |
| timestamper | Takes raw timestamps + topics.json, splits into sections | KEEP (different API) |

### 2d. `check_sections.py` — 2 variants
- **timestamper** has `load_asr_garbled_patterns()`, `_scan_asr_garbles()`, updated `BLOCK_RE`
- **timestamper-local** has older `BLOCK_RE`, no ASR scan
- Action: UPDATE timestamper-local to match timestamper (or symlink)

---

## Phase 3: Extract Shared `lib/anibon/` Package

### Functions to extract (across 25 unique .py files)

| Proposed module | Functions | Current locations | Consumers |
|---|---|---|---|
| `lib/anibon/time.py` | `fmt_ts(float)→str` | `_chunker.py`, `_transcript.py` | 2 |
| | `fmt_hhmmss(int)→str` | `plan_highlight.py`, `verify_highlight.py` | 2 |
| | `parse_ts(str)→int` | `merge_timestamps.py`, `assemble_timestamps.py`, `pack_timestamps.py` | 3 |
| `lib/anibon/parsers.py` | `LINE_RE`, `parse_timestamps(lines)→list` | `pack_timestamps.py:29` | 1 now, could be 3 |
| | `parse_timestamp_line(line)→dict` | `merge_timestamps.py:11`, `assemble_timestamps.py` | 2 |
| `lib/anibon/chunk_io.py` | `load_chunks(path)→yield (name, start_sec, items)` | `anibon_analyzer_core.py:18`, `detect_signals.py:32`, `detect_topics.py:22` | 4 |
| | `load_chunk_json(path)`, `load_chunk_xml(path)` | scattered | — |
| | `chunk_sort_key(f)→int` | `detect_signals.py (timestamper)` | 1 |
| | `write_chunk(path, items, fmt)` | `_chunker.py:21` | 1 |
| `lib/anibon/cleaner.py` | `clean_text(text, mappings)→str` | `_chunker.py:8` | 1 |
| | `clean_chunk(data)→changes` | `clean_garbled_english.py:51` | 1 |
| | `scan_garbles(text)→warnings` | `check_sections.py:87` | 1 |
| `lib/anibon/ytdlp.py` | `download_transcript(url, workspace)` | `_transcript.py:25` | 1 |
| | `download_video(url, workspace, format)` | `_vision.py:11`, `cut_highlight.py` | 2 |
| | `probe_metadata(url)→dict` | `plan_highlight.py:147` | 1 |
| `lib/anibon/resources.py` | `resource_path(name)→Path` | `clean_garbled_english.py:26`, `check_sections.py:5`, `pack_timestamps.py (timestamper)`, `_chunker.py:50` | 4 |
| `lib/anibon/markdown.py` | `format_sections(parts)→str` | `assemble_timestamps.py:20` (root) | 1 |
| | `format_markdown(parts, title)→str` | `pack_timestamps.py:113` | 1 |
| `lib/anibon/analyzer.py` | `classify_chunk(chunk, keywords)→tags` | `anibon_analyzer_core.py:65` | 1 |
| | `detect_timeline_gaps(chunks, limit)→gaps` | same | 1 |
| | `calculate_youtube_blocks(chunks, warn)→blocks` | same | 1 |

### Resulting structure

```
anibon-stream-synthesis/
├── lib/anibon/              ← NEW: shared library
│   ├── __init__.py
│   ├── time.py
│   ├── parsers.py
│   ├── chunk_io.py
│   ├── cleaner.py
│   ├── ytdlp.py
│   ├── resources.py
│   ├── markdown.py
│   └── analyzer.py
├── scripts/                  ← DELETE (Phase 1a)
├── skills/
│   ├── anibon-timestamper/scripts/
│   │   ├── prepare_video.py   ← thin CLI, imports anibon.transcript/chunker/vision
│   │   ├── anibon-analyzer.py ← thin CLI, imports anibon.analyzer
│   │   ├── pack_timestamps.py ← KEEP (DP algo, skill-specific)
│   │   ├── detect_signals.py  ← KEEP (knowledge-base, skill-specific)
│   │   ├── check_sections.py  ← KEEP (after extracting resource loader to lib)
│   │   ├── analyze_transcript.py ← KEEP (standalone)
│   │   ├── merge_timestamps.py   ← KEEP (standalone)
│   │   ├── clean_garbled_english.py ← KEEP (standalone)
│   │   ├── validate_part_coherence.py ← KEEP (standalone)
│   │   ├── fetch_story_ref.py  ← KEEP (standalone)
│   │   ├── align_ref_timeline.py ← KEEP (standalone)
│   │   ├── fetch_fgo_db.py    ← KEEP (standalone)
│   │   └── fetch_ygo_db.py    ← KEEP (standalone)
│   ├── anibon-timestamper-local/scripts/
│   │   ├── prepare_video.py   ← thin CLI or SYMLINK → timestamper copy
│   │   ├── pack_timestamps.py ← SYMLINK → timestamper copy (after merge)
│   │   ├── check_sections.py  ← SYMLINK → timestamper copy
│   │   ├── fetch_fgo_db.py    ← remains (or symlink)
│   │   └── fetch_ygo_db.py    ← remains (or symlink)
│   ├── cleaning-auto-transcripts/scripts/
│   │   ├── prepare_video.py   ← thin CLI or SYMLINK → timestamper copy
│   │   ├── clean_transcript.py ← KEEP (unique, standalone)
│   │   ├── _chunker.py        ← DELETE (imports from lib)
│   │   ├── _transcript.py     ← DELETE (imports from lib)
│   │   └── _vision.py         ← DELETE (imports from lib)
│   ├── creating-highlight-video/scripts/
│   │   ├── plan_highlight.py  ← KEEP (unique)
│   │   ├── cut_highlight.py   ← KEEP (unique)
│   │   └── verify_highlight.py ← KEEP (unique)
│   ├── synthesizing-knowledge/scripts/
│   │   └── resolve_markdown_links.py ← KEEP (unique)
│   └── ... rest unchanged
```

---

## Phase 4: Update SKILL.md Paths

After restructuring, every SKILL.md that references a moved/deleted script must be updated.

### Affected SKILL.md files (12 files, ~45+ path references)

| File | Change |
|---|---|
| `anibon-timestamper/SKILL.md` | `scripts/foo.py` → `[SKILL_ROOT]/scripts/foo.py` (absolute-ize) |
| `anibon-timestamper-local/SKILL.md` | Remove `detect_topics.py` ref (line 126) |
| `anibon-world-identity/SKILL.md` | Fix all 7 broken refs to point to `../anibon-timestamper/scripts/` |
| `anibon-local-transcription/SKILL.md` | Fix `scripts/clean_transcript.py` → point to cleaning skill |
| `cleaning-auto-transcripts/SKILL.md` | Update `_chunker/_transcript/_vision` refs if moved |
| `creating-highlight-video/SKILL.md` | Keep as-is (self-contained) |
| `creating-highlight-video/references/highlight-planner.md` | Keep as-is |
| `creating-highlight-video/references/highlight-cutter.md` | Keep as-is |
| `creating-highlight-video/references/highlight-verifier.md` | Keep as-is |
| `anibon-timestamper-local/references/timestamper-handoff.md` | Keep as-is (`[SKILL_ROOT]/scripts/` still valid) |
| `synthesizing-knowledge/SKILL.md` | Keep as-is |
| `writing-plugin-readme/SKILL.md` | Keep as-is (generic examples) |

### Also update `hooks.json` line 9
`skills/anibon-timestamper/scripts/check_sections.py` — still valid path, no change needed.

---

## Phase 5: Optional — Symlink Strategy vs Copy Strategy

After extracting lib/, each skill needs access to it. Two approaches:

### Option A: PYTHONPATH (cleaner)
```python
# In each thin CLI wrapper:
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
import anibon.transcript as t
```
+ Single source of truth. Edit once, all skills benefit.
- PYTHONPATH hack still there, but at least in one place per CLI.

### Option B: Install-time copy (npm postinstall)
```json
// package.json scripts
"postinstall": "python3 tools/sync_lib.py"
```
+ No PYTHONPATH. Each skill fully self-contained.
- Duplication reappears if skills aren't re-synced.

### Option C: Symlinks (minimal change)
```
skills/cleaning-auto-transcripts/scripts/_chunker.py -> ../../../lib/anibon/chunker.py
```
+ Zero code change in existing CLIs that import `_chunker`.
- Symlinks confuse some tools; fragile on Windows.

**Recommendation: Option A (PYTHONPATH)** — simplest, most maintainable. The CLI wrappers (`prepare_video.py`, `anibon-analyzer.py`) already use `sys.path.insert`, so this is an incremental improvement.

---

## Execution Order ✓ COMPLETE

```
Phase 0 ✓: Fix broken cross-skill SKILL.md paths                    [7 edits]
Phase 1 ✓: Delete dead files                                        [28 files]
Phase 2 ✓: Reconcile divergent copies                               [2 symlinks]
Phase 3 ✓: Extract lib/anibon/ package                              [9 new files]
Phase 4 ✓: Update SKILL.md paths for dead scripts                   [4 edits]
Phase 5 ✓: Rewrite CLI wrappers to use lib imports                  [5 rewrites + 7 deletes]
```

### Remaining cleanup (optional, not blocking)

| Item | Reason |
|---|---|
| `import re` in `clean_transcript.py:4` | unused, but harmless |
| `_vision.py` in 3 skills | still skill-specific, could be consolidated later |
| `creating-highlight-video/scripts/` uses own yt-dlp calls | could import `anibon.ytdlp.download_video` |

---

## Summary of Impact

| Metric | Before | After | Δ |
|---|---|---|---|
| .py files on disk | 51 | 35 | −16 |
| lib modules | 0 | 9 | +9 |
| Broken SKILL.md paths | 7 | 0 | −7 |
| detect_topics refs | 3 | 0 | −3 |
| Divergent copy pairs | 5 | 0 | −5 (2 symlinked, 3 deleted) |
| Internal _*.py modules per skill | 3×3=9 | 1×3=3 (_vision only) | −6 |
| Dead scripts deleted | 0 | 19 .py + 2 tests + 7 sdd | −28 files | |

### Files deleted (total 19 .py + 2 test + 7 sdd)

```
DELETE: scripts/*.py                                    ×13
DELETE: detect_topics.py (3 copies)                     ×3
DELETE: analyze_transcript.py + test                    ×2
DELETE: assemble_timestamps.py (2 copies) + test        ×3
DELETE: .superpowers/sdd/*                              ×7
```

### Files created (8 new lib modules + 4 rewritten CLIs)

```
CREATE: lib/anibon/__init__.py
CREATE: lib/anibon/time.py
CREATE: lib/anibon/parsers.py
CREATE: lib/anibon/chunk_io.py
CREATE: lib/anibon/cleaner.py
CREATE: lib/anibon/ytdlp.py
CREATE: lib/anibon/resources.py
CREATE: lib/anibon/markdown.py
CREATE: lib/anibon/analyzer.py
REWRITE: timestamper/scripts/prepare_video.py
REWRITE: timestamper/scripts/anibon-analyzer.py
REWRITE: timestamper-local/scripts/prepare_video.py
REWRITE: cleaning-auto-transcripts/scripts/prepare_video.py
SYMLINK: timestamper-local/scripts/pack_timestamps.py → timestamper copy
SYMLINK: timestamper-local/scripts/check_sections.py → timestamper copy
```
