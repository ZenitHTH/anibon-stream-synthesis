---
name: anibon-timestamper-local
description: Use when generating YouTube timestamps and topic summaries for long livestreams locally on a single GPU (such as NVIDIA Tesla P100 16GB) without cloud API costs.
---

# Anibon Timestamper (Local P100 Edition)

## Overview

Local processing pipeline for generating YouTube timestamps and summaries from long livestreams via Dynamic Recursive Rolling Summary state-machines (`--mode recursive`) or group batching (`--mode group`), multi-modal context fusion, automatic tag normalization, and two-pass YouTube comment formatting.

## Pipeline Architecture

| Stage | Tool / Script | Input / Output | Function |
| :--- | :--- | :--- | :--- |
| **0. Transcript Pre-normalization** | `process_chunks_local.py` (auto) | `garbled_replacements.json` + `default_mappings.json` | Clean phonetic drift and known ASR noise before loading chunks. |
| **1. Preparation & Chunking** | `prepare_video.py` | YouTube URL → `raw_transcript.json`, `chunks/*.txt` | Downloads subtitles and segments audio/transcript into overlapping chunks. |
| **2. Topic Segmentation (Pass 1)** | `process_chunks_local.py` | `chunks/`, `signals.json`, World Identity | Detects shifts/continuations, emits timestamps via local LLM. |
| **3. Summarizer & Assembly (Pass 2)** | `process_chunks_local.py` | `all_timestamps.txt` → `anibon_timestamps.md` | Clusters timestamps into comment blocks (<3,500 bytes) with Thai headers. |


---

## Execution Modes

### Mode 1: Recursive Rolling Summary (`--mode recursive`, Default & Recommended)
Pu Boat's discussions follow organic content flow rather than clock boundaries. A topic may last 3 minutes or 25 minutes.
- **`SAME_TOPIC`**: If Chunk $N$ continues the ongoing topic, it merges into the rolling summary without emitting a timestamp.
- **`TOPIC_SHIFT`**: When the topic shifts, it flushes the previous summary, stamps the exact start timestamp, and begins a fresh rolling summary.

### Mode 2: Fixed Window Groups (`--mode group`, Alternative)
Combines 4 chunks (~16–20 min) per group with chronological loop-breakers and collision guards.

---

## Core Pipeline & Quick Reference

### Quick Commands

```powershell
# 0. (AUTO) Pre-normalization — garbled_replacements.json is loaded automatically by
#    process_chunks_local.py before any chunk is read. No manual step needed.
#    Priority order applied inside load_chunk_file():
#      1. garbled_replacements.json  (2000+ confirmed Whisper ground-truth corrections)
#      2. default_mappings.json      (phonetic entity heuristics)
#    If garbled_replacements.json is missing, pipeline continues with default_mappings only.

# 1. Download & Chunk (Skip if chunks/chunk_00.txt exists)
python "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/prepare_video.py" "https://www.youtube.com/watch?v=<VIDEO_ID>" --workspace "C:/Users/peter/youtube_<VIDEO_ID>_workspace" --format txt --block 300 --overlap 30

# 2. Run All-in-One Local Timestamper (Recursive Mode + Summarizer Pass)
python -X utf8 "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "C:/Users/peter/youtube_<VIDEO_ID>_workspace" --mode recursive --lang th

# 3. Detached Background Launch (supports custom IP/endpoint, default: 100.115.25.30)
# PowerShell (Windows):
powershell -ExecutionPolicy Bypass -File "scripts/launch_local.ps1" -Workspace "youtube_<VIDEO_ID>_workspace" -Endpoint "100.115.25.30"

# Batch (Windows cmd):
scripts\launch_local.bat "youtube_<VIDEO_ID>_workspace" 100.115.25.30 auto th

# Bash / Zsh (Linux / macOS):
./scripts/launch_local.sh "youtube_<VIDEO_ID>_workspace" 100.115.25.30
# or
./scripts/launch_local.zsh "youtube_<VIDEO_ID>_workspace" 100.115.25.30
```

---

## Discipline & Anti-Rationalization

### The Iron Rule of Local Processing

```
NEVER TIME-LOCK TOPICS TO ARBITRARY MINUTE BOUNDARIES
```

Livestreams flow organically. Use the Recursive Rolling Summary state-machine to detect true content shifts rather than stamping every $N$ minutes.

### Rationalization Table

| Rationalization | Reality | Counter-Measure |
| :--- | :--- | :--- |
| *"Single chunk is faster to run."* | Produces 35+ micro-stamps that clutter comment sections. | Use `--mode recursive` with rolling summaries. |
| *"I can invent tags like [วิเคราะห์] because it fits the content."* | Front-tier benchmarks reject non-standard tags; breaks comment parsers. | Normalizer automatically remaps `[วิเคราะห์]` → `[Talk]`. |
| *"I'll just summarize the whole 3-hour transcript in 1 prompt."* | Exceeds context and degrades entity recall on 12B models. | Sequential rolling state-machine keeps prompt under 2k tokens. |
| *"Let's write a custom Python script to speed this up."* | Ad-hoc scripts break state tracking, resume logic, and encoding. | Strictly use `process_chunks_local.py` flags. |

### Red Flags — STOP and Reset
- Output file contains 35+ timestamps for a 2-hour stream (micro-stamping symptom).
- Output tags include non-whitelisted words (`[วิเคราะห์]`, `[ชำแหละ]`, `[เปิดตัว]`).
- Sections exceed 3,500 bytes (YouTube comment limit violation).
- Script crashes with `UnicodeEncodeError: 'charmap'` (forgot `-X utf8`).

---

## Common Mistakes & Troubleshooting

1. **LM Studio Model Eviction**:
   - *Symptom*: LM Studio unloads Gemma 4 and reloads another model, causing 60-second stalls.
   - *Fix*: Keep `--model auto`. `resolve_model` automatically latches onto the active in-memory model.

2. **Gemma 4 Thinking Token Trap**:
   - *Symptom*: Output timestamp is blank or truncated.
   - *Cause*: Model used token budget in `reasoning_content`.
   - *Fix*: Built-in system prompt limits thinking to <2 sentences; regex extractor extracts structured JSON directly from content or reasoning.

3. **ASR Phonetic Drift**:
   - *Symptom*: Names like "นครโตะ" appear instead of "Naucrate (นอคราเต้)".
   - *Fix*: `process_chunks_local.py` loads `resources/default_mappings.json` and runs TF-IDF signal detection before prompt generation.
