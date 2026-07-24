---
name: anibon-timestamper
description: Use when generating detailed timestamps or topic summaries for long-form live streams and videos featuring speaker "Boat" (Pu Boat) from Anibon Official. This is the orchestrator skill.
---

# Anibon Timestamper (Orchestrator)

## Overview

A routing skill for analyzing data, conversations, or transcripts from live streams to generate timestamps in YouTube Description/Comment format. It dynamically detects the stream type (Talk, Gaming, Marathon, Event) and delegates the actual processing to specialized sub-skills.

## When to Use

- You need to extract key moments and generate timed topic labels for a video or stream by speaker "Boat" from **Anibon Official**.

---

## Process Flow: Dynamic Subagent Routing

> [!IMPORTANT]
> **REQUIRED SUB-SKILL (FIRST):** Before anything else, run `preparing-tools` to verify all system dependencies (`yt-dlp`, `ffmpeg`, `python3`, `sqlite3`). Do NOT proceed if any tool is missing.

0. **Environment Setup**
   
   - **Native PATH**: Rely entirely on the OS `$env:PATH` to resolve python and tools. Do NOT write boilerplate to detect python paths or set PYTHONPATH.
   - **File Conventions**: Store working files in a session working directory. Example filenames: `anibon_<video_id>_transcript.json`, `anibon_<video_id>_chunks/`.

1. **Initialization & Context**
   
   - Greet the user and **Ask for Output Language**: "What language would you like the timestamps generated in? (e.g., Thai, English, etc.)" Do not proceed to timestamp generation until the user confirms.
   - **Channel Ownership Check**: Verify the channel is Anibon Official (uploader name matches Phuboat, ปู่โบ๊ต, โบ๊ต, Boat, or ANIBON). If not, do NOT call the speaker "Boat".
   - **Video Publish Date Check**: Run `yt-dlp --print uploader,upload_date "<url>"` via a shell command (`Bash` in Claude Code, `run_command` in Antigravity, native bash in OpenCode). If `yt-dlp` is unavailable, fetch the page via the available web-fetch tool. **Compare the stream's upload date to the CURRENT DATE** to determine if you are analyzing a retrospective/old video, as news context changes over time. **CRITICAL**: Do NOT write ad-hoc `python -c` scripts to scrape YouTube HTML.
   - **Transcript & Preparation**: See Step 2 and Step 3 of the Step-by-Step Guide for downloading and chunking.

2. **MapReduce Strategy for Long Streams**
   
   - **Parallel Subagent Processing**: For long streams, spawn multiple parallel subagents to process the JSON chunks concurrently. This map-reduce strategy is optimized for cloud models with large context windows.
   - **REQUIRED SUB-SKILL:** Load `anibon-macro-density` before dispatching subagents. It overrides default density rules to keep final output compact (≤ 20 YouTube comments for a 9-hour stream).
   - **Explicit Parameters for Chunking**: Default is `--block 300 --overlap 30` (5-min segments). For long talk-heavy streams, prefer `--block 600 --overlap 60` (10-min segments) to halve subagent count and enforce macro density naturally.
   - **Subagent Scripting Rule**: Subagents shouldn't need to write custom parsing scripts. They can read the generated chunks directly.

3. **Transcript Auto-Detection → Sub-Skill Routing**

   **DETECT FIRST, ROUTE SECOND.** Before routing any chunk, classify its content type. Use `detect_topics.py` (see Helper Scripts) for keyword-based signal scanning instead of ad-hoc python/grep commands.

   ```bash
   # Quick classification scan across all chunks
   python3 scripts/detect_topics.py ~/youtube_<video_id>_workspace/chunks \
     -w "Kamen Rider,Super Sentai,Ultraman,โทคุซัทสึ" -c tokusatsu -o compact

   # Detailed per-chunk matches for gaming content
   python3 scripts/detect_topics.py ~/youtube_<video_id>_workspace/chunks \
     -w "FGO,Fate,Arknights,กาชา,SSR,banner" -c gaming -o table

   # Scan single chunk for political/royal keywords
   python3 scripts/detect_topics.py ~/youtube_<video_id>_workspace/chunks/chunk_05.json \
     -w "รัชกาล,สวรรคต,มาตรา 112" -c royal -o json
   ```

   ### Detection Signals (scan the raw transcript text)

   | Signal found in chunk | → Load sub-skill |
   |---|---|
   | Long monologues, reading chat, news discussion, lore/story tangents, "coded" political talk (e.g., One Piece metaphors for Thai news) | `anibon-talk-stream` |
   | Game-specific jargon (boss names, stage names, skill names) dominate with sparse verbal reactions | `anibon-gaming-stream` |
   | Multiple distinct game titles appear in sequence, clear "switching" transitions | `anibon-marathon-stream` |
   | Patch note reading, new event content, theorycrafting, dense game terminology released recently | `anibon-event-stream` |
   | Tokusatsu franchise names (Kamen Rider, Super Sentai, Ultraman, etc.), episode watch party, multi-speaker panel discussion about tokusatsu | `anibon-tokusatsu-stream` |
   | Interactive bracket voting, Ideal Type World Cup, uwufufu.com website, character elimination ranks | `references/uwufufu-knowledge.md` |

   **Rules:**
   - A chunk **may match multiple signals** — load ALL matching sub-skills simultaneously.
   - If uncertain between `talk` and `gaming`: default to `anibon-talk-stream` (Boat almost always talks).
   - If the chunk is clearly mixed (e.g., gaming + political lore): load both `anibon-gaming-stream` + `anibon-talk-stream`.

   Because Boat never follows a set agenda and his streams are highly chaotic, a single 15-minute chunk may contain multiple distinct activities. **Subagents are permitted and encouraged to load MULTIPLE sub-skills simultaneously** if their chunk is highly mixed.

   **Sub-skill locations** (available in `references/`):
   - `references/talk-stream.md`
   - `references/gaming-stream.md`
   - `references/marathon-stream.md`
   - `references/event-stream.md`
   - `references/tokusatsu-stream.md`
   - `references/donation-classifier.md` ← **cross-stream**: load alongside any primary skill when the chunk contains [Donation] entries
   - `references/timestamp-description.md` ← **cross-stream**: load alongside ANY subagent when writing timestamp descriptions; defines the 4-pillar framework (Point → Analysis → Impact → Live Comment → one sentence)
   - `references/fgo-knowledge.md` ← **game-knowledge**: FGO servant naming conventions & Thai community nicknames dictionary
   - `references/uwufufu-knowledge.md` ← **interactive-knowledge**: UWUFUFU World Cup bracket rules & milestone density caps

   **Live Service Games Knowledge Base References**:
   - See [INDEX.md](../reference/INDEX.md) for all game lore, mechanics, and DB query guides.

   **⚡ DB Bootstrap** (Run before lookup):
   - FGO: `python3 scripts/fetch_fgo_db.py --check --db "skills/reference/FGO and DATA/atlas_fgo.db" || python3 scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"`
   - YGO: `python3 scripts/fetch_ygo_db.py --check --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db" || python3 scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"`

   **Canonical Subagent Prompt Template:**
   Read [subagent-prompt-template.md](subagent-prompt-template.md) for the full prompt to send to each chunk subagent.

   **Key rule injected into every subagent prompt:**
   - 5-min chunk → **1 timestamp default, 2 MAX**
   - New timestamp ONLY on: game switch, speaker join/leave, completely new activity
   - Multiple sub-topics in same conversation → MERGE into 1
   - Subagent must run Density Self-Check (Step 8) and merge down to ≤ 2 before submitting
   - **IMAGE VERIFICATION (MANDATORY)**: If any transcript item has an `"image"` field, you MUST call `view_file` to load the image and visually confirm the game title / activity shown on screen BEFORE writing the timestamp description. Never name a game from transcript text alone if an image is available.

4. **Reduce Stage (Final Assembly)**

   - **Gather**: Combine all chunk subagent results chronologically.
   - **Delegate to Summarizer Subagent**: Read [summarizer-subagent-guide.md](summarizer-subagent-guide.md) for the full prompt to send to the Summarizer Subagent. Do NOT write summaries or decide splits yourself — prevents context fatigue and errors.
   - **⚠️ SINGLE FILE RULE**: Save ALL parts into ONE `.md` file. Never create `part1.md`, `part2.md`, etc.

## Local Audio Transcription (Alternative)

If YouTube has no subtitles or auto-captions, transcribe the audio locally using `whisper.cpp`:
1. **Audio Extraction**: Download audio stream as a mono 16kHz WAV file:
   ```bash
   yt-dlp -x --audio-format wav --audio-quality 16K "VIDEO_URL" -o "audio.wav"
   ```
2. **Local Transcription**: Run GPU-accelerated `whisper.cpp` build:
   - For Windows (Vulkan/AMD):
     ```powershell
     .\whisper-cli.exe -m ggml-large-v3-turbo.bin -l th -f audio.wav -ot 540000 2>&1
     ```
     *(Note: Set the start offset `-ot 540000` (9 min) to skip silent start screens and avoid repetition loop bugs).*
   - For full build options, platform configurations, and parameters, see [BUILD_GPU.md](BUILD_GPU.md).
3. **Format Conversion**: Convert `whisper-cli` raw JSON output to pipeline-standard `raw_transcript.json`.

## Helper Scripts & Writing Code

Available scripts (all in the `scripts/` directory next to this SKILL.md):
- **`prepare_video.py`** — downloads transcript, cleans, and chunks (Step 2).
- **`anibon-analyzer.py`** — runs on the workspace folder to detect >10m timeline gaps, classify chunks for routing, and pre-calculate YouTube block byte sizes (warns >3500 bytes). Run BEFORE analysis to plan part splits.
- **`detect_topics.py`** — keyword scanner across chunk JSONs. Takes file/dir + comma-separated words. Outputs table/json/compact. Replaces ad-hoc python -c/grep for topic detection. Run `-h` for full usage.
- **`clean_transcript.py`** — cleans raw json3 and/or outputs chunks (called by prepare_video).
- **`check_sections.py`** — checks section sizes in the final timestamp `.md` file, flags sections over 4,500/5,000 chars, and suggests midpoint split timestamps. Run after assembly.
- **`pack_timestamps.py`** — packs a flat chronological timestamp list into byte-limited parts (3,500B target) and outputs formatted Markdown with separator blocks. Also writes a `parts.json` alongside for manual editing/reassembly.

  **Usage:**
  ```bash
  # Pack timestamps list into parts (auto-named output)
  python3 scripts/pack_timestamps.py ~/youtube_<video_id>_workspace/timestamps.txt
  # → produces ~/youtube_<video_id>_workspace/timestamps_packed.md
  # → produces ~/youtube_<video_id>_workspace/timestamps_parts.json

  # Custom output path
  python3 scripts/pack_timestamps.py ~/youtube_<video_id>_workspace/timestamps.txt --output ~/youtube_<video_id>_workspace/anibon_timestamps.md
  ```

  **Input format** — flat timestamp list, one per line:
  ```
  HH:MM:SS - [Tag] Description
  ```
  > **Important:** Never hardcode the parts list or output path inside a one-off script. Always use `pack_timestamps.py` with a flat timestamp list input. This keeps data and assembly logic separate and reusable across streams.

## 🧭 Orchestration Checklist (Cloud)
1. Environment: Verify `yt-dlp`, `python3`.
2. Download & Chunk: `python3 scripts/prepare_video.py "URL" --format xml --block 300 --overlap 30 --vision`
3. Pre-flight: `python3 scripts/anibon-analyzer.py /path/to/workspace`. **MANDATORY: Resolve all detected gaps > 10 min BEFORE spawning subagents.** Do not skip.
4. DB Bootstrap: Run check/build for FGO/YGO if needed.
5. Parallel Analysis: Spawn chunk subagents using [subagent-prompt-template.md](subagent-prompt-template.md).
6. Gap Verification: After collecting all subagent results, scan chronological timestamp list for gaps > 10 min. Inject intermediate timestamps from raw transcript before assembly.
7. Final Assembly: Save chronological timestamp list to workspace, then pack:
   `python3 scripts/pack_timestamps.py ~/youtube_<video_id>_workspace/timestamps.txt --output ~/youtube_<video_id>_workspace/anibon_timestamps.md`
   `python3 scripts/check_sections.py ~/youtube_<video_id>_workspace/anibon_timestamps.md`
   **If `check_sections.py` shows ⚠️ WARN or ❌ FAIL, adjust `--byte-limit` or split timestamps before proceeding.**

## Iron Rules
- **Publish date first**: Always check.
- **Use detect_topics.py, not ad-hoc scanning**: Keyword detection across chunks must use `scripts/detect_topics.py`. No `python3 -c "..."`, no `grep`, no ad-hoc scripts. See `-h` for usage.
- **Dynamic Routing**: Subagents load skills based on chunk content. No upfront guessing.
- **ONE FILE**: Output is one `.md` file. Use `═══` blocks. No `part1.md`.
- **OUTPUT IN WORKSPACE**: Save `parts.json` and `anibon_timestamps.md` to `~/youtube_<video_id>_workspace/`.
- **4,500 BYTE CAP**: Target 3,500 bytes per pasted block. Run `check_sections.py`.
- **PRE-SPLIT**: Pack timestamps to hit 3,500-byte limit first. Combine small topics. Only split if combining overflows limit.
- **NO GAPS**: Max 10 mins without timestamp unless verified silent. **No exceptions — verify gaps before AND after assembly.**
- **FORMAT LOCK**: The separator format is defined in `summarizer-subagent-guide.md` (lines 64–71). Any change to `pack_timestamps.py` formatting MUST match that spec exactly. The unit tests in `tests/test_pack_timestamps.py` are the contract — if tests pass but the format still diverges from the guide, fix the guide, not the tests.
- **IMAGE FIRST**: If a chunk item has an `"image"` field, load and inspect it with `view_file` BEFORE naming any game or activity.
- **VISION VERIFICATION FOR AMBIGUOUS CONTEXT**: When the streamer discusses technical setups, file formats/codecs (WebM/AV1), on-screen errors, or game UI details that audio transcripts gloss over, extract relevant video frames via `ffmpeg` and inspect them with `view_file` to confirm exact context before writing descriptions.
- **COMPLETE PART HEADERS**: Part titles in `═══` header blocks must be concise, short summaries (~5–10 words) that capture the section theme and end on complete words. Never truncate titles mid-sentence.
