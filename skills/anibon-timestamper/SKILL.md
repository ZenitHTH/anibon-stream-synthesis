---
name: anibon-timestamper
description: Use when generating detailed timestamps or topic summaries for long-form live streams and videos featuring speaker "Boat" (Pu Boat) from Anibon Official. This is the orchestrator skill.
---

# Anibon Timestamper (Orchestrator)

A routing skill for analyzing live stream transcripts to generate timestamps in YouTube format. Dynamically detects stream type and delegates to specialized sub-skills.

## When to Use

Streams or videos by "Boat" from Anibon Official that need timed topic labels.

## Sub-Skills

**REQUIRED (first):** Load `preparing-tools` to verify dependencies (`yt-dlp`, `ffmpeg`, `python3`).

Loaded by signal (add to prompt when needed):
- `anibon-world-identity` — verify game/char names against references before story stamps
- `anibon-local-transcription` — whisper.cpp fallback if YouTube has no captions

## Pipeline

### 0. Environment Setup

Use OS PATH to resolve tools. Store working files in `youtube_<video_id>_workspace/`.

### 1. Initialize & Context

Ask output language. Verify channel is Anibon Official (Phuboat/ปู่โบ๊ต/Boat/ANIBON). Check upload date vs current date.

### 2. Download, Clean & Chunk

`python3 scripts/prepare_video.py "URL" --format xml --block 300 --overlap 30 --vision`
Talk-heavy → `--block 600 --overlap 60` for larger chunks.

### 2.5 Clean Garbled English (NEW)

Run after chunking, before signal detection. Normalises Thai-Whisper garbled English:
`one พman` → `One Punch Man`, `JC Star` → `JC Staff`, `foage` → `footage`.

```bash
python3 scripts/clean_garbled_english.py \
  --chunks ~/youtube_<id>_workspace/chunks/
```

Add `--dry-run` to preview changes without modifying files.

### 3. Signal Detection → Knowledge Routing

Run TF-IDF across all chunks. Signal terms auto-match knowledge files by filename substring (see `references/INDEX.md`). Inject `[DETECTION SIGNAL]` + matched knowledge into each subagent's prompt. No hardcoded terms.

```bash
python3 scripts/detect_signals.py ~/youtube_<id>_workspace/chunks \
  --output json \
  --match-knowledge skills/anibon-timestamper/references/ > signals.json
```

### 3.5 Pre-pass — Detect Topic Boundaries (NEW)

Before spawning subagents, compute topic transitions from signal data.
This identifies exactly where topics shift (GL/BL→Umigari, Umigari→Mewgenics).
Pass boundaries to `pack_timestamps.py` via `--topic-json`.
Subagents receive boundary info so they do not fabricate across topic lines.

```bash
python3 scripts/detect_boundaries.py ~/youtube_<id>_workspace/chunks/ \
  --output boundaries.json \
  --signals signals.json
```

If `detect_boundaries.py` is not yet available, manually identify topic
transition timestamps by scanning chunk-level topic signals and mark them
with `--break-at` in Step 6.

### 4. Spawn Subagents (Parallel)

Use `subagent-prompt-template.md`. Inject per-chunk signal + knowledge files.
Fill `PREVIOUS_CHUNK_PRIMARY_TOPIC` and `CURRENT_CHUNK_PRIMARY_TOPIC`
placeholders with chunk-level topics from `signals.json`.
Each subagent returns 0-2 timestamps. Collect chronologically.

### 5. World Identity Verify

If stream covers post-cutoff games → load `anibon-world-identity` before writing story stamps. Priority: local refs → cached story refs → SRT → websearch.

### 6. Reduce & Assemble

Collect all timestamps → delegate to `summarizer-subagent-guide.md` for dedup, part splitting, header review.

Pack into byte-limited sections with optional forced topic breaks:
```bash
python3 scripts/pack_timestamps.py all_timestamps.txt \
  --break-at 04:35:28,05:15:00
```
Use `--break-at` to force new sections at specific timestamps (prevents topic bleed across sections).

Validate output with ASR garbled check:
```bash
python3 scripts/check_sections.py output.md
```
Use `--no-garbled-check` to skip ASR scan. Single `.md` file with `═══` section blocks.

### 6.5 Validate Topic Coherence (NEW)

Run BEFORE publishing. Uses `signals.json` from Step 3 as ground truth for game names:

```bash
python3 scripts/validate_part_coherence.py output.md \
  --signals signals.json
```

Checks performed:
- **Tag diversity** — mixed tag macros in same part
- **Game diversity** — different games mentioned in same part
- **Signal cross-reference** — timestamp game name vs chunk-level signals (flags fabricated names)
- **Keyword coherence** — description tokens share common thread
- **Tag continuity** — no flips between disparate categories

If validation FAILS:
1. Read flagged parts — identify which stamps are off-topic
2. Move or delete offending stamps
3. Re-run `pack_timestamps.py` with corrected list + `--topic-json` or `--break-at`

Optional: cross-reference against chunk transcripts for deeper verification:
```bash
python3 scripts/validate_part_coherence.py output.md \
  --signals signals.json \
  --chunks ~/youtube_<id>_workspace/chunks/
```

## Helper Scripts

All in `scripts/`. Run `<name>.py --help` for full usage:

- `prepare_video.py` — download, clean, chunk
- `anibon-analyzer.py` — pre-flight: gap detection, chunk classification, byte cap check
- `detect_signals.py` — TF-IDF signal + knowledge matching (replaces `detect_topics.py`)
- `clean_transcript.py` — raw json3 cleaner (called by prepare_video)
- `check_sections.py` — validate byte caps on assembled output
- `fetch_story_ref.py` — fetch/cache story synopses (user consent required for websearch)
- `pack_timestamps.py` — pack flat timestamp list into byte-limited parts (supports `--topic-json`)
- `validate_part_coherence.py` — validate topic coherence per part (NEW)
- `align_ref_timeline.py` — align reference SRT timestamps with stream chunks
- `fetch_fgo_db.py`, `fetch_ygo_db.py` — build card databases (for World Identity)

## Iron Rules

- **Use detect_signals.py** — no ad-hoc grep/inline scanning. TF-IDF only.
- **ONE FILE** — single `.md` with `═══` section blocks. No `part1.md`.
- **NO GAPS** — max 10 min between timestamps unless verified silent.
- **INTRO BREAKDOWN** — intro >10 min → break into 3-5 min sub-topic milestones.
- **NO AD-HOC TIMESTAMPS** — only via subagent pipeline → `pack_timestamps.py`.
