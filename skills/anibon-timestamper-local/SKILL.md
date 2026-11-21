---
name: anibon-timestamper-local
description: Use when generating YouTube timestamps and topic summaries for long livestreams locally on a single GPU (Tesla P100, LM Studio, Ollama), or when pausing, resuming, or checking progress of an active local timestamper worker. For cloud parallel subagents, use anibon-timestamper.
---

# Anibon Timestamper (Local P100 Edition)

## Overview

Single-GPU local pipeline for generating YouTube timestamps and summaries from long livestreams via Dynamic Recursive Rolling Summary (`--mode recursive`) or group batching (`--mode group`), storyboard/LiveChat fusion, and two-pass YouTube comment formatting.

## When to Use

- Processing livestreams locally (Tesla P100 16GB, Apple Silicon, LM Studio, Ollama, TokenMe) without cloud API costs.
- Pausing, holding, resuming, or inspecting an active local worker cleanly without killing its PID: use `skills/anibon-timestamper-local/scripts/control_chunks_local.py`.
- **When NOT to use**: For cloud/frontier parallel subagents (Claude, Gemini Pro), use `anibon-timestamper`.

## Companion Skills

- **`anibon-world-identity` (MANDATORY)**: Verify character, game, Pokémon (`ชื่อไทย (English Name)`), and pop-culture names against `references/*.md`, `atlas_fgo.db`, `pokemon.db`, and `garbled_replacements.json` before finalizing output.
- **`anibon-livechat-analysis`**: Download/align LiveChat replays or extract burned-in chat via vision OCR fallback (`mood_555.json` pulses + viewer reaction peaks).
- **`whisper-corruption-recovery`**: Re-render Whisper repetition loops or silence-stutter segments before timestamping.
- **`anibon-local-transcription`**: Extract 16kHz audio and run local GPU `whisper.cpp` when YouTube has no subtitles.

## Pipeline Stages

All commands run from plugin root (`anibon-stream-synthesis`). Shared utilities live in `scripts/` and `lib/`; local runners live in `skills/anibon-timestamper-local/scripts/`.

| Stage | Entrypoint / Modules | Role |
|---|---|---|
| **1. Prepare & Chunk** | `scripts/prepare_video.py` | Downloads subtitles, storyboards, chunks transcript (`--keep-silent-chunks` preserves quiet gaps), aligns `--live-chat`, computes `mood_555.json`. |
| **2. Prep-First Enrichment (MANDATORY BEFORE PASS 1)** | `scripts/enrich_chunks.py`, `lib/process/chunk_enrichment.py`, `lib/process/chunk_storyboard_prep.py` | Pre-prepares **all** chunk evidence into `enrichment/chunk_NN.json` before LM inference: storyboard screen tiles, webcam frame crops aligned with soundwave loud peaks & silence shock drops, and Shazam song detection -> `audio.cpp` vocal split -> `whisper.cpp` speech recovery. Runs automatically at the start of `process_chunks_local.py` (disable only via `--no-enrich`). |
| **2.5 Clean & Glossary** | `lib/process/audit.py`, `lib/process/knowledge/` | Applies `garbled_replacements.json` + `default_mappings.json` on disk, writes `signals.json` + `entity_glossary.json`. |
| **3. Pass 1 Full-Context Segmentation** | `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, `control_chunks_local.py`, `scripts/validate_mood.py` | Feeds **untrimmed** storyboard screen tiles + pre-cropped webcam peak/silence sheets + detected song/recovered speech + full chunk transcript lines + full livechat + full World Identity reference into rolling state-machine (`lib/chunk/state.py`, `lib/chunk/pause.py`) → `all_timestamps.txt`. |
| **4. Garbled Collector** | `lib/process/garbled_collector.py`, `scripts/whisper_dispatcher.py` | Slices audio on-the-fly via local `whisper.cpp`, updates `garbled_replacements.json`, cleans `all_timestamps.txt` & `chunks/`. |
| **5. Pass 2 Summary & Gates** | `lib/process/summarizer.py`, `lib/process/byte_cap.py`, `lib/process/parity_gates.py` | Prunes essential stamps (~40–60), assembles 4–6 macro parts (`<= 20` lines/part), audits glossary & runs gap/section gates → `anibon_timestamps.md`. (Post-Pass-1 webcam reaction verify is opt-in only via `--post-reaction-verify` because webcam crops are already fed into Pass 1). |
| **5.5 Edited VOD Shift** | `scripts/reconcile_edited_stream.py` | Detects post-broadcast YouTube Studio trims via 1000Hz FFT audio correlation and shifts timestamps. |

**Execution Modes**: `--mode recursive` (default; `SAME_TOPIC` merges unless a >8–10 min monologue needs a distinct sub-angle; `TOPIC_SHIFT` emits 1–2 stamps `>=45s` apart; Pass 2 groups into 4–6 macro parts) vs `--mode group` (fixed 4-chunk groups). Run `--help` on any script for full flags.

## Golden-Path Commands

**Pre-Flight Domain Check**: For unindexed topics (cinema, mythology, indie games), scaffold `skills/anibon-world-identity/references/<Topic>.md` and `INDEX.md` **before** `prepare_video.py`. For single-game streams, inspect `<workspace>/signals.json` after Step 1 and lock non-intro chunks' `allowed_sources` to that game's reference file.

### 1. Prepare & Chunk (Skip if `chunks/chunk_00.txt` exists)

```bash
python3 scripts/prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --workspace ~/youtube_<VIDEO_ID>_workspace --format txt --block 150 --overlap 15 --live-chat
yt-dlp -f 18 -o ~/youtube_<VIDEO_ID>_workspace/video_360p.mp4 "https://www.youtube.com/watch?v=<VIDEO_ID>"
```

Use `--overlap 20` for walking vlogs / convention tours (`2.5`-min blocks).

### 2. Verify Model Resident in VRAM (MANDATORY)

```bash
curl -s --max-time 8 http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'
```

- **Default model**: `gemma-4-12b-it-qat@q4_k_xl` (`"parallel": 1`, `"context_length": 49152` — **2× headroom over peak ~24k tokens to prevent context-brim hallucination**, `"eval_batch_size": 49152`). Full-context mode sends every transcript line, full livechat, full World Identity lore, and all storyboard + webcam peak/silence frames without artificial truncation. Smoke-test `--max-chunks 1` before launching 50+ chunks.
- **Ollama `*:cloud` Trap**: Never point `process_chunks_local.py` at local Ollama `*:cloud` tags (e.g. `gemma4:cloud`); `HTTP 402` triggers blackout-recovery loops. If LM Studio at `100.115.25.30:1234` is down, ask the user to start it. Load payloads, `12b` vs `26b` benchmark, and TokenMe setup → [`references/hardware-and-endpoints.md`](references/hardware-and-endpoints.md).

### 3. Run Timestamper / Detached Launch / Pause Control

```bash
# Pre-enrich soundwave audio cues, webcam crops, and Shazam -> audio.cpp -> whisper.cpp (verify-first default):
WHISPER_ENDPOINT="http://100.115.25.30:8082/inference" \
AUDIOCPP_URL="http://100.115.25.30:8080/v1/tasks/run" USE_AUDIOCPP=1 \
python3 -X utf8 scripts/enrich_chunks.py ~/youtube_<VIDEO_ID>_workspace \
  --video-file ~/youtube_<VIDEO_ID>_workspace/video_360p.mp4 \
  --audiocpp-url "http://100.115.25.30:8080/v1/tasks/run"

# Foreground (verify-first default: storyboard + cached enrichment + --reaction-verify on local video_360p.mp4):
WHISPER_ENDPOINT="http://100.115.25.30:8082/inference" \
AUDIOCPP_URL="http://100.115.25.30:8080/v1/tasks/run" USE_AUDIOCPP=1 \
python3 -X utf8 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace \
  --mode recursive --lang th --reaction-verify \
  --video-file ~/youtube_<VIDEO_ID>_workspace/video_360p.mp4 \
  --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>"

# Detached background (macOS/Linux; Windows scripts in hardware-and-endpoints.md):
bash skills/anibon-timestamper-local/scripts/launch_local.sh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th

# Cooperative pause / status / continue (NEVER kill/SIGTERM worker PID or write timestamper.log):
python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py ~/youtube_<VIDEO_ID>_workspace pause
python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py ~/youtube_<VIDEO_ID>_workspace status
python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py ~/youtube_<VIDEO_ID>_workspace continue
```

### 4. Garbled Collector (Automatic Pre-Pass 2 / Post-Pass 1)

Runs `whisper.cpp` on `<workspace>/garbled_notes_raw/` automatically after Pass 1 / before Pass 2 summarization (`--video-url` enables on-the-fly stream slicing; `--no-garbled-collector` skips).

### 5. Mandatory Stage 5 Audit & Gate Re-Run

1. Invoke `anibon-world-identity` AND read [`references/stage5-audit-checklist.md`](references/stage5-audit-checklist.md) before delivering any timestamp file.
2. After any manual Stage 5 edit, sync **both** `anibon_timestamps.md` and `all_timestamps.txt` and re-run plugin-root gates:

```bash
python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/all_timestamps.txt --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
python3 scripts/check_sections.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md
```

## On-Demand References (Read ONLY When Triggered)

| Trigger / Situation | Reference File |
|---|---|
| Loading LM Studio VRAM, `12b` vs `26b` benchmark, TokenMe remote API (`HTTP 400`, 8-image cap), `config.json`/env overrides, `--eval-batch-size` frame math, `--reaction-verify` triggers/mid-stream switch, Windows commands, pause checkpoint internals | [`references/hardware-and-endpoints.md`](references/hardware-and-endpoints.md) |
| **Mandatory before final delivery**: LiveChat `[t-30s, t+90s]` cross-check, full-stream timing/boundary rewind, Dual-Track Desync, conciseness/verb saturation (`<=20%`, `วิพากษ์`), FGO/Tokusatsu/Yuri traps, `reaction_verify_log.json`, knowledge harvesting | [`references/stage5-audit-checklist.md`](references/stage5-audit-checklist.md) |
| Manual 4-step LiveChat or visual OCR fallback, manual Whisper/garbled commands, text→multimodal workspace backup, missing storyboards (`-f 160`), selective cache wipe, runtime errors (`mmproj`, `88.94s` drift, `call_local`, Tailscale CLI) | [`references/troubleshooting.md`](references/troubleshooting.md) |
| Channel-exclusive YouTube emote IDs (`:_CunnyBoat:`, `:_BoatSOM:`, etc.) and mood pulse weights | [`references/anibon_emoji_dictionary.md`](references/anibon_emoji_dictionary.md) |
| Saving/resuming `anibon_timestamper_state.json` across fresh sessions on context exhaustion (load *after* this skill) | [`references/timestamper-handoff.md`](references/timestamper-handoff.md) |

## Discipline & Red Flags

**Global Invariants**: Follow `GEMINI.md` rules for streamer identity (`ปู่โบ๊ต`), anti-guessing, Caveman timestamp style (no leading `'ปู่โบ๊ต'`, varied opening verbs), line-count part splitting (15–20 lines/part, max 25), essential curation (40–60 stamps), garbled regex safety, and post-stream knowledge harvesting.

**Iron Rule**: `NEVER TIME-LOCK TOPICS TO ARBITRARY MINUTE BOUNDARIES`

| Rationalization | Reality | Counter-Measure |
|---|---|---|
| *"Single chunk is faster to run."* | Emits 35+ noisy micro-stamps. | Use `--mode recursive` with rolling summaries. |
| *"I can invent tags like `[วิเคราะห์]`."* | Breaks comment parsers & benchmarks. | Normalizer remaps to whitelisted tags (`[Talk]`). |
| *"Summarize the whole 3h transcript in 1 prompt."* | Exceeds single-pass output attention and degrades entity recall. | Process chunk-by-chunk with full chunk evidence (storyboard + webcam crops + audio/song + full transcript) and rolling state-machine. |
| *"Write a custom Python script to go faster."* | Breaks state, resume logic, and UTF-8. | Use `process_chunks_local.py` flags only. |
| *"Kill the worker PID to pause, relaunch later."* | Aborts active chunk and risks duplicate PIDs. | Run `control_chunks_local.py <ws> pause` / `continue` (pass `--timeout 0` if urgent). |
| *"Output looks good without World Identity check."* | Hallucinates games or drops Thai Pokémon names. | Run `anibon-world-identity` + `stage5-audit-checklist.md`. |

**Red Flags — STOP and Reset:**
- Delivering timestamps without completing `anibon-world-identity` and [`references/stage5-audit-checklist.md`](references/stage5-audit-checklist.md).
- Killing `process_chunks_local.py` PID (`kill`, `SIGTERM`, `Ctrl-C`) or writing `timestamper.log` instead of calling `control_chunks_local.py`.
- Running timestamper before `whisper-corruption-recovery`, or forgetting `-X utf8`.
- Emitting `>35` stamps for a 2h stream, `>6–8` micro-parts, or non-whitelisted tags (`[วิเคราะห์]`, `[เปิดตัว]`).
- Omitting `[Ending]`, hallucinating unstated next-stream schedules, or mistaking pre-roll waiting BGM for an anime watchparty.
- Swallowing running gameplay state during a long talk tangent (Dual-Track Desync) or running suspect-only checks without auditing chunk tails/boundaries.
