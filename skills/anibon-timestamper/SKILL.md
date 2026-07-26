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

### 3. Signal Detection → Knowledge Routing

Run TF-IDF across all chunks. Signal terms auto-match knowledge files by filename substring (see `references/INDEX.md`). Inject `[DETECTION SIGNAL]` + matched knowledge into each subagent's prompt. No hardcoded terms.

```bash
python3 scripts/detect_signals.py ~/youtube_<id>_workspace/chunks \
  --output json \
  --match-knowledge skills/anibon-timestamper/references/ > signals.json
```

### 4. Spawn Subagents (Parallel)

Use `subagent-prompt-template.md`. Inject per-chunk signal + knowledge files. Each subagent returns 0-2 timestamps. Collect chronologically.

### 5. World Identity Verify

If stream covers post-cutoff games → load `anibon-world-identity` before writing story stamps. Priority: local refs → cached story refs → SRT → websearch.

### 6. Reduce & Assemble

Collect all timestamps → delegate to `summarizer-subagent-guide.md` for dedup, part splitting, header review. Run `check_sections.py` on output. Single `.md` file with `═══` section blocks.

## Helper Scripts

All in `scripts/`. Run `<name>.py --help` for full usage:

- `prepare_video.py` — download, clean, chunk
- `anibon-analyzer.py` — pre-flight: gap detection, chunk classification, byte cap check
- `detect_signals.py` — TF-IDF signal + knowledge matching (replaces `detect_topics.py`)
- `clean_transcript.py` — raw json3 cleaner (called by prepare_video)
- `check_sections.py` — validate byte caps on assembled output
- `fetch_story_ref.py` — fetch/cache story synopses (user consent required for websearch)
- `pack_timestamps.py` — pack flat timestamp list into byte-limited parts
- `align_ref_timeline.py` — align reference SRT timestamps with stream chunks
- `fetch_fgo_db.py`, `fetch_ygo_db.py` — build card databases (for World Identity)

## Iron Rules

- **Use detect_signals.py** — no ad-hoc grep/inline scanning. TF-IDF only.
- **ONE FILE** — single `.md` with `═══` section blocks. No `part1.md`.
- **NO GAPS** — max 10 min between timestamps unless verified silent.
- **INTRO BREAKDOWN** — intro >10 min → break into 3-5 min sub-topic milestones.
- **NO AD-HOC TIMESTAMPS** — only via subagent pipeline → `pack_timestamps.py`.
