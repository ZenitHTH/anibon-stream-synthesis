# Implementation Plan: Dead Code Cleanup & System De-duplication

- **Target Plugin:** `anibon-stream-synthesis`
- **Branch:** `feat/chaining-weight-signal-detector`
- **Standard:** Robert C. Martin (*Clean Code*), Ponytail Lean Architecture

---

## 1. Problem Statement
The repository contains ~1,027 lines of dead prototypes, redundant utilities, and duplicate logic that accumulated during early iterations:
1. **`lib/chunk/topic_scanner.py`**: Hardcoded 10-game dictionary completely superseded by `anibon-world-identity` and dynamic markdown lore ingestion in `process.signals`.
2. **`lib/chunk/analyzer.py` & `anibon-analyzer.py`**: Naive 5-category keyword scanner superseded by `process.signals` and `preflight-gate.py`.
3. **`lib/process/vision.py`**: Broken 480p full-video downloader causing runtime `AttributeError` when invoking `prepare_video.py --vision`, superseded by `anibon-stream-activity` storyboard extraction.
4. **`detect_boundaries.py`**: 430-line abandoned n-gram Jaccard calculator with zero active callers.
5. **`clean_transcript.py`, `merge_timestamps.py`, `dump_chunk_text.py`**: Orphaned script prototypes stranded in skill folders.
6. **`skills/anibon-stream-synthesis-ffmpeg/`**: Complete folder-level duplicate of `skills/edit-cut-video-ffmpeg/`.
7. **Ad-hoc Time Math**: 8 duplicate time parsing/formatting implementations bypassing `lib/common/time.py`.
8. **Gap Rule Drift**: Inconsistent 15-minute (`900s`) checks in preflight/assembly gates violating the canonical 10-minute (`600s`) threshold.

---

## 2. Proposed Module Structure & Boundaries
lib/
├── chunk/
│   ├── __init__.py           # Exports only: align, chunker, ranker
│   ├── align.py              # Transcript alignment
│   ├── chunker.py            # Token/time-based chunking
│   └── ranker.py             # Topic scoring & rank
├── common/
│   ├── __init__.py           # Exports only: time, markdown, logging
│   ├── logging.py            # Clean standard logging
│   ├── markdown.py           # Markdown table/bullet formatters
│   └── time.py               # Canonical time math (fmt_ts, fmt_hhmmss, parse_ts)
├── process/
│   ├── __init__.py
│   ├── signals.py            # Dynamic keyword & lore signal detection
│   └── text.py               # Repetition cleanup & hallucination removal
└── video/
    ├── __init__.py
    └── storyboard.py         # Storyboard unpacking & frame extraction logic


---

## 3. Step-by-Step Execution Tasks

### Task 1: Delete Dead Files & Clean `prepare_video.py`
- Delete:
  - `lib/chunk/topic_scanner.py`
  - `lib/chunk/analyzer.py`
  - `lib/process/vision.py`
  - `skills/anibon-timestamper/scripts/anibon-analyzer.py`
  - `skills/anibon-timestamper/scripts/detect_boundaries.py`
  - `skills/anibon-timestamper/scripts/dump_chunk_text.py`
  - `skills/anibon-timestamper/scripts/merge_timestamps.py`
  - `skills/cleaning-auto-transcripts/scripts/clean_transcript.py`
- In `scripts/prepare_video.py`:
  - Remove deprecated `--vision` block (lines 115–119) that attempts to import deleted `process.vision`.

### Task 2: Clean Public Interfaces & Barrel Exports
- `lib/chunk/__init__.py`: Remove `TopicScanner`, `Topic`, `ChunkAnalyzer`, `AnalysisResult`.
- `lib/common/__init__.py`: Clean out stale utility re-exports.
- `lib/interface.py`: Remove dead dataclasses and unused boundary contracts.

### Task 3: Consolidate Time Math into `lib/common/time.py`
- Ensure `lib/common/time.py` provides:
  - `fmt_ts(seconds: float) -> str` (e.g., `HH:MM:SS` or `MM:SS`)
  - `fmt_hhmmss(seconds: float) -> str` (strictly 3-segment `00:00:00`)
  - `parse_ts(timestamp_str: str) -> float`
- Replace ad-hoc regex/math in:
  - `scripts/assembly-gate.py`
  - `scripts/preflight-gate.py`
  - `scripts/audit_gaps.py`
  - `scripts/unpack_storyboard.py`
  - `skills/anibon-stream-activity/scripts/unpack_storyboard.py`
  - `skills/whisper-corruption-recovery/scripts/fix_hallucinations.py`

### Task 4: Extract Library Modules from Standalone Scripts
- Move core storyboard unpacking loop from `skills/anibon-stream-activity/scripts/unpack_storyboard.py` into `lib/video/storyboard.py`. The CLI script becomes a thin wrapper (< 50 lines).
- Move repetition/loop detector logic from `skills/whisper-corruption-recovery/scripts/fix_hallucinations.py` into `lib/process/text.py`.

### Task 5: Consolidate Redundant FFmpeg Skills
- Merge unique guidance or filter options from `skills/anibon-stream-synthesis-ffmpeg/` into `skills/edit-cut-video-ffmpeg/SKILL.md`.
- Remove redundant directory `skills/anibon-stream-synthesis-ffmpeg/`.

### Task 6: Align Gap Check Thresholds & Fix SKILL.md Paths
- Update `scripts/preflight-gate.py` and `scripts/assembly-gate.py` to use `600` seconds (10 minutes) instead of `900` seconds for gap warnings.
- Fix broken script paths referenced in `skills/anibon-timestamper/SKILL.md` (remove references to deleted `detect_boundaries.py` and `merge_timestamps.py`).

### Task 7: Verification & Test Suite
- Run `pytest tests/` across all test suites.
- Verify `python3 scripts/prepare_video.py --help` runs without import errors.
- Confirm zero references to deleted modules remain via repository search.

---

## 4. Uncle Bob Clean Code Self-Audit Checklist
- [ ] Every function ≤ 20 lines (SRP strictly enforced).
- [ ] Max indentation ≤ 2 levels (guard clauses used).
- [ ] No boolean flag arguments in library signatures.
- [ ] All reusable logic isolated under `lib/`; scripts act solely as I/O wiring.