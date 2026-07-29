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
- `whisper-corruption-recovery` — recover transcript if repetition loops / corruption detected in Whisper output

## Pipeline (Linear, Top-to-Bottom)

All paths relative to `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/`.

### 0. Environment

`scripts/` directory contains all helper scripts. Run `<script>.py --help` for flags.
Store working files in `youtube_<video_id>_workspace/`.

### 1. Initialize

Ask output language. Verify channel is ANIBON (Boat/PhuBoat). Check upload date.

### 2. Prepare Video

```bash
python3 scripts/prepare_video.py "URL" --format xml --block 300 --overlap 30
# Talk-heavy → --block 600 --overlap 60
```

Downloads transcript, creates `<workspace>/chunks/chunk_*.xml`.

> [!IMPORTANT]
> **Check Corruption**: If transcript is from local Whisper transcription (or audio ≥2h), verify tail entries for repetition loops. If corruption found (>0.5 match ratio), load `whisper-corruption-recovery` skill to split, re-run corrupted tail segment, and dedup-merge before chunking.

### 3. Clean Transcript (Optional)

Normalizes Thai-Whisper garbled English before signal detection.

```bash
python3 scripts/clean_garbled_english.py --chunks ~/youtube_<id>_workspace/chunks/
```

### 4. Analyze (Pre-flight)

Quick summary of chunk categories, gaps, byte sizes.

```bash
python3 scripts/anibon-analyzer.py ~/youtube_<id>_workspace/
```

### 5. Detect Signals → Match Knowledge Files

TF-IDF across all chunks. Matches keywords to knowledge files per chunk.

```bash
python3 scripts/detect_signals.py \
  --chunks ~/youtube_<id>_workspace/chunks/ \
  --knowledge ./knowledge.json \
  --output ~/youtube_<id>_workspace/signals.json
```

Output: `signals.json` — per-chunk matched knowledge files + signal scores.

### 6. Detect Topic Boundaries (Optional)

For long streams with clear topic shifts. If `detect_boundaries.py` is not available (not yet implemented), identify topic shifts manually from `signals.json`: look for chunks where `matched_files` changes (e.g., gaming→Genshin→FGO). Note timestamps for `--break-at` in Step 9.

### 7. Spawn Subagents (Parallel)

Divide chunks into groups of 4-5 (40-50 min each). One Task agent per group.

**Each subagent prompt MUST contain:**
- Chunk file paths (agent reads XML directly — do NOT read chunks yourself)
- Per-chunk detection signals from `signals.json` (inject `matched_files` + `signal_score`)
- The `subagent-prompt-template.md` output contract (0-2 stamps per chunk, merge same topic → 0)
- Knowledge file content for matched references (e.g., gaming-stream.md, phuboat-anime-talking-style.md, game reference files)

**CRITICAL:** Do NOT write topic descriptions yourself. Let the agent read the XML + signals. Inject signals.json data, not your analysis.

Each agent returns timestamps as plain text lines.

### 8. Merge Timestamps

Write each agent's output to its own file (e.g., `agent_1.txt`, `agent_2.txt`). Then merge + sort chronologically:

```bash
python3 scripts/merge_timestamps.py ~/youtube_<id>_workspace/agent_*.txt \
  -o ~/youtube_<id>_workspace/all_timestamps.txt
```

### 9. Pack into Sections

Split into byte-limited sections (YouTube comment cap ~3500B). Use `--topic-json` with `boundaries.json` from Step 6 for section headings + forced topic splits.

```bash
python3 scripts/pack_timestamps.py ~/youtube_<id>_workspace/all_timestamps.txt \
  --topic-json ~/youtube_<id>_workspace/boundaries.json \
  --title "Video Title | ANIBON" \
  -o ~/youtube_<id>_workspace/output.md
```

### 10. Validate Sections

```bash
python3 scripts/check_sections.py ~/youtube_<id>_workspace/output.md
```

Checks: byte cap per section ✅, no ASR garbled patterns.

### 11. Validate Topic Coherence (Optional)

Cross-references timestamp game names against `signals.json` ground truth. Flags fabricated names or topic bleed between parts.

```bash
python3 scripts/validate_part_coherence.py ~/youtube_<id>_workspace/output.md \
  --signals ~/youtube_<id>_workspace/signals.json \
  --chunks ~/youtube_<id>_workspace/chunks/
```

## Output Format

Single `.md` file with `═══` section blocks:

```
# Title | ANIBON

═════════════════════════════════════════════════════
 Part 1: Section Header (⏱ เริ่ม: HH:MM:SS)
═════════════════════════════════════════════════════
HH:MM:SS - [Tag] Description
...

═════════════════════════════════════════════════════
 Part 2: Section Header (⏱ เริ่ม: HH:MM:SS)
═════════════════════════════════════════════════════
...
```

## Helper Scripts

| Script | Purpose |
|--------|---------|
| `prepare_video.py` | Download + clean + chunk |
| `clean_garbled_english.py` | Normalize Thai-Whisper garbled English |
| `anibon-analyzer.py` | Pre-flight: gaps, categories, byte sizes |
| `detect_signals.py` | TF-IDF signal + knowledge file matching |
| `merge_timestamps.py` | Combine + sort subagent outputs |
| `pack_timestamps.py` | Byte-limited section packing (supports `--break-at`, `--topic-json`) |
| `check_sections.py` | Validate byte cap + ASR garbles |
| `validate_part_coherence.py` | Cross-reference game names vs signals |
| `clean_transcript.py` | Raw json3 cleaner (called by prepare_video) |
| `fetch_story_ref.py` | Fetch/cache story synopses (user consent for websearch) |
| `align_ref_timeline.py` | Align reference SRT timestamps with chunks |
| `fetch_fgo_db.py`, `fetch_ygo_db.py` | Build card databases (World Identity) |

## Iron Rules

- **Use detect_signals.py** — TF-IDF only. No ad-hoc grep/inline scanning.
- **Don't read chunks yourself** — subagents read XML. Inject signals.json data into prompts.
- **ONE FILE** — single `.md` with `═══` section blocks. No `part1.md`.
- **NO GAPS** — max 10 min between timestamps unless verified silent.
- **INTRO BREAKDOWN** — intro >10 min → break into 3-5 min sub-topic milestones.
- **NO AD-HOC TIMESTAMPS** — only via subagent pipeline → `merge_timestamps.py` → `pack_timestamps.py`.
