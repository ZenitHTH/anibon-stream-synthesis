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
   - **Explicit Parameters for Chunking**: ALWAYS use `--block 300 --overlap 30` (5-min segments). Do NOT invent arbitrary block sizes.
   - **Subagent Scripting Rule**: Subagents shouldn't need to write custom parsing scripts. They can read the generated chunks directly.

3. **Transcript Auto-Detection → Sub-Skill Routing**

   **DETECT FIRST, ROUTE SECOND.** Before routing any chunk, scan the transcript text for the signals below. This is not optional — do it for every chunk, including when using subagents.

   ### Detection Signals (scan the raw transcript text)

   | Signal found in chunk | → Load sub-skill |
   |---|---|
   | Long monologues, reading chat, news discussion, lore/story tangents, "coded" political talk (e.g., One Piece metaphors for Thai news) | `anibon-talk-stream` |
   | Game-specific jargon (boss names, stage names, skill names) dominate with sparse verbal reactions | `anibon-gaming-stream` |
   | Multiple distinct game titles appear in sequence, clear "switching" transitions | `anibon-marathon-stream` |
   | Patch note reading, new event content, theorycrafting, dense game terminology released recently | `anibon-event-stream` |
   | Tokusatsu franchise names (Kamen Rider, Super Sentai, Ultraman, etc.), episode watch party, multi-speaker panel discussion about tokusatsu | `anibon-tokusatsu-stream` |

   **Rules:**
   - A chunk **may match multiple signals** — load ALL matching sub-skills simultaneously.
   - If uncertain between `talk` and `gaming`: default to `anibon-talk-stream` (Boat almost always talks).
   - If the chunk is clearly mixed (e.g., gaming + political lore): load both `anibon-gaming-stream` + `anibon-talk-stream`.

   Because Boat never follows a set agenda and his streams are highly chaotic, a single 15-minute chunk may contain multiple distinct activities. **Subagents are permitted and encouraged to load MULTIPLE sub-skills simultaneously** if their chunk is highly mixed.

   **Sub-skill locations** (nested under this skill):
   - `skills/anibon-talk-stream/SKILL.md`
   - `skills/anibon-gaming-stream/SKILL.md`
   - `skills/anibon-marathon-stream/SKILL.md`
   - `skills/anibon-event-stream/SKILL.md`
   - `skills/anibon-tokusatsu-stream/SKILL.md`

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

## Helper Scripts & Writing Code

Available scripts (all in the `scripts/` directory next to this SKILL.md):
- **`prepare_video.py`** — downloads transcript, cleans, and chunks (Step 2).
- **`anibon-analyzer.py`** — runs on the workspace folder to detect >10m timeline gaps, classify chunks for routing, and pre-calculate YouTube block byte sizes (warns >3500 bytes). Run BEFORE analysis to plan part splits.
- **`clean_transcript.py`** — cleans raw json3 and/or outputs chunks (called by prepare_video).
- **`check_sections.py`** — checks section sizes in the final timestamp `.md` file, flags sections over 4,500/5,000 chars, and suggests midpoint split timestamps. Run after assembly.
- **`assemble_timestamps.py`** — assembles a list of timestamp sections from a JSON file into a formatted Markdown output file. This is the reusable CLI replacement for ad-hoc assembly scripts.

  **Usage:**
  ```bash
  # Store parts.json INSIDE the workspace, then assemble (output lands beside it automatically)
  python3 scripts/assemble_timestamps.py ~/youtube_<video_id>_workspace/parts.json
  # → produces ~/youtube_<video_id>_workspace/anibon_timestamps.md

  # Or with an explicit path if needed
  python3 scripts/assemble_timestamps.py ~/youtube_<video_id>_workspace/parts.json --output ~/youtube_<video_id>_workspace/anibon_timestamps.md
  ```

  **`parts.json` format** — a JSON array where each object has:
  ```json
  [
    {
      "title": "ชื่อหัวข้อ",
      "start": "HH:MM:SS",
      "body": "HH:MM:SS - [Tag] คำอธิบาย\nHH:MM:SS - [Tag] คำอธิบาย"
    }
  ]
  ```
  > **Important:** Never hardcode the parts list or output path inside a one-off script. Always use `assemble_timestamps.py` with a `parts.json` input file. This keeps data and assembly logic separate and reusable across streams.

## 🧭 Orchestration Checklist (Cloud)
1. Environment: Verify `yt-dlp`, `python3`.
2. Download & Chunk: `python3 scripts/prepare_video.py "URL" --format xml --block 300 --overlap 30 --vision`
3. Pre-flight: `python3 scripts/anibon-analyzer.py /path/to/workspace`. **MANDATORY: Resolve all detected gaps > 10 min BEFORE spawning subagents.** Do not skip.
4. DB Bootstrap: Run check/build for FGO/YGO if needed.
5. Parallel Analysis: Spawn chunk subagents using [subagent-prompt-template.md](subagent-prompt-template.md).
6. Gap Verification: After collecting all subagent results, scan chronological timestamp list for gaps > 10 min. Inject intermediate timestamps from raw transcript before assembly.
7. Final Assembly: Save `parts.json` to workspace, then run:
   `python3 scripts/assemble_timestamps.py ~/youtube_<video_id>_workspace/parts.json`
   `python3 scripts/check_sections.py ~/youtube_<video_id>_workspace/anibon_timestamps.md`
   **If `check_sections.py` shows ⚠️ WARN or ❌ FAIL, fix `parts.json` before proceeding.**

## Iron Rules
- **Publish date first**: Always check.
- **Dynamic Routing**: Subagents load skills based on chunk content. No upfront guessing.
- **ONE FILE**: Output is one `.md` file. Use `═══` blocks. No `part1.md`.
- **OUTPUT IN WORKSPACE**: Save `parts.json` and `anibon_timestamps.md` to `~/youtube_<video_id>_workspace/`.
- **4,500 BYTE CAP**: Target 3,500 bytes per pasted block. Run `check_sections.py`.
- **PRE-SPLIT**: Pack timestamps to hit 3,500-byte limit first. Combine small topics. Only split if combining overflows limit.
- **NO GAPS**: Max 10 mins without timestamp unless verified silent. **No exceptions — verify gaps before AND after assembly.**
- **FORMAT LOCK**: The separator format is defined in `summarizer-subagent-guide.md` (lines 64–71). Any change to `assemble_timestamps.py` formatting MUST match that spec exactly. The unit tests in `tests/test_assemble_timestamps.py` are the contract — if tests pass but the format still diverges from the guide, fix the guide, not the tests.
- **IMAGE FIRST**: If a chunk item has an `"image"` field, load and inspect it with `view_file` BEFORE naming any game or activity.
