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
| **0. Noise Cleaning & Pre-normalization** | `signal_detector.py` / `process_chunks_local.py` (auto) | `garbled_replacements.json` + `default_mappings.json` | Strips ASR speaker markers (`>>`), sound effect tags (`[เพลง]`, `[Applause]`), music symbols (`♪`), repetitive stutter loops, and corrects phonetic drift before chunk loading/signal detection. |
| **1. Preparation & Chunking** | `prepare_video.py` | YouTube URL → `raw_transcript.json`, `chunks/*.txt` | Downloads subtitles and segments audio/transcript into overlapping chunks. |
| **2. Topic Segmentation (Pass 1)** | `process_chunks_local.py` | `chunks/`, `signals.json`, World Identity | Detects shifts/continuations, emits timestamps via local LLM. |
| **3. Summarizer & Assembly (Pass 2)** | `process_chunks_local.py` | `all_timestamps.txt` → `anibon_timestamps.md` | Clusters timestamps into comment blocks (<3,500 bytes) with Thai headers. |
| **4. Garbled Collector & Whisper Ground Truth** | `whisper_dispatcher.py` (auto post-pass) | `garbled_notes_raw/` → `garbled_notes.json` → `garbled_replacements.json` | Automatically runs after summary: slices audio on-the-fly, transcribes phonetic ground truth via local whisper.cpp, and auto-grows shared dictionary. |


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

#### 0. Denoising & Pre-normalization (Automatic)
Before any signal detection or LLM analysis, `clean_transcript_noise()` automatically cleans ASR artifacts (`>>`, `[เพลง]`, `♪`, character repetitions), and applies 2000+ Whisper ground truths from `garbled_replacements.json` and `default_mappings.json`. No manual invocation needed.

#### 1. Download & Chunk (Skip if chunks/chunk_00.txt exists)
**macOS / Linux:**
```bash
python3 scripts/prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" \
    --workspace "~/youtube_<VIDEO_ID>_workspace" \
    --format txt --block 300 --overlap 30
```

**Windows (PowerShell / Command Prompt):**
```powershell
python scripts\prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" --workspace "$HOME\youtube_<VIDEO_ID>_workspace" --format txt --block 300 --overlap 30
```

#### 2. Run Timestamper Directly (Foreground)
**macOS / Linux:**
```bash
python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
    --mode recursive --lang th
```

**Windows (PowerShell):**
```powershell
python -X utf8 scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th
```

#### 3. Detached Background Launch (3 OS Families)
Runs inference detached in background so agent sessions or timeouts do not kill the run.

**macOS (Zsh / Bash):**
```zsh
./scripts/launch_local.zsh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th
```

**Linux (Bash):**
```bash
./scripts/launch_local.sh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File "scripts\launch_local.ps1" -Workspace "$HOME\youtube_<VIDEO_ID>_workspace" -Endpoint "100.115.25.30"
```

**Windows (CMD Batch):**
```cmd
scripts\launch_local.bat "%USERPROFILE%\youtube_<VIDEO_ID>_workspace" 100.115.25.30 auto th
```

#### 4. Garbled Collector & Whisper Ground Truth (Automatic Post-Pass)
After `anibon_timestamps.md` summary assembly finishes, `process_chunks_local.py` automatically checks for surviving phonetic garbles in `<workspace>/garbled_notes_raw/` and invokes `whisper_dispatcher.py` with local `whisper.cpp` to slice audio and update `garbled_replacements.json`.

- To pass video URL for on-the-fly stream slicing without full audio downloads:
  ```bash
  python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
      --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>"
  ```
- To disable automatic garbled collection pass:
  ```bash
  python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
      --no-garbled-collector
  ```
- To run garbled collection manually at any time:
  ```bash
  python3 scripts/whisper_dispatcher.py ~/youtube_<VIDEO_ID>_workspace \
      --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>" --verbose
  python3 ../cleaning-auto-transcripts/scripts/update_garbled_dictionary.py \
      --from-notes ~/youtube_<VIDEO_ID>_workspace/garbled_notes.json \
      --workspace ~/youtube_<VIDEO_ID>_workspace
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
