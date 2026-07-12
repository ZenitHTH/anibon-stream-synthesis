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

0. **Environment Setup**
   
   - **Native PATH**: Rely entirely on the OS `$env:PATH` to resolve python and tools. Do NOT write boilerplate to detect python paths or set PYTHONPATH.
   - **File Conventions**: Store working files in a session working directory. Example filenames: `anibon_<video_id>_transcript.json`, `anibon_<video_id>_chunks/`.

1. **Initialization & Context**
   
   - Greet the user and **Ask for Output Language**: "What language would you like the timestamps generated in? (e.g., Thai, English, etc.)" Do not proceed to timestamp generation until the user confirms.
   - **Channel Ownership Check**: Verify the channel is Anibon Official. If not, do NOT call the speaker "Boat".
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

   **Live Service Games Knowledge Base References** (nested under this skill):
   - [Honkai: Star Rail Reference](skills/reference/Honkai_Star_Rail.md)
   - [Wuthering Waves Reference](skills/reference/Wuthering_Waves.md)
   - [Zenless Zone Zero Reference](skills/reference/Zenless_Zone_Zero.md)
   - [Arknights: Endfield Reference](skills/reference/Arknights_Endfield.md)
   - [Limbus Company Reference](skills/reference/Limbus_Company.md)
   - [Pokémon PvP & Champions Reference](skills/reference/Pokemon_PvP.md)
   - [Pokémon Translation & Names Reference](skills/reference/Pokemon_Names.md)
   - [Pokémon Radical Red Reference](skills/reference/Pokemon_Radical_Red.md)
   - [Arknights Reference](skills/reference/Arknights.md)
   - [Honkai Impact 3rd Reference](skills/reference/Honkai_Impact_3.md)
   - [Honkai Impact 3rd Part 2 Reference](skills/reference/Honkai_Impact_3_Part2.md)
   - [Genshin Impact Reference](skills/reference/Genshin_Impact.md)
   - [miHoYo Connected Lore Reference](skills/reference/miHoYo_Connected_Lore.md)
   - [Fate/Grand Order Core Mechanics & Lore Reference](skills/reference/FGO%20and%20DATA/fgo_knowledge_base.md)
   - [Fate/Grand Order "Past Chaldea" Patch Analysis Reference](skills/reference/FGO%20and%20DATA/fgo_patch_analysis.md)
   - [Fate/Grand Order Chat Export Reference](skills/reference/FGO%20and%20DATA/fgo_chat_export.md)
   - [Fate/Grand Order Live DB Query Guide](skills/reference/FGO%20and%20DATA/FGO_DB_Reference.md) ← **Read this for all name/ID lookups**
   - [Yu-Gi-Oh! Card DB Query Guide](skills/reference/Yu-Gi-Oh%20DATA/YGO_DB_Reference.md) ← **Read this for all card/archetype lookups**

   **⚡ FGO Database Bootstrap** (run BEFORE any FGO name/ID lookup):
   When FGO content is detected, check if `atlas_fgo.db` exists:
   ```
   python3 scripts/fetch_fgo_db.py --check --db "skills/reference/FGO and DATA/atlas_fgo.db"
   ```
   If exit code is 1 (missing/invalid), build it:
   ```
   python3 scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"
   ```
   Then query it with sqlite3. See [FGO_DB_Reference.md](skills/reference/FGO%20and%20DATA/FGO_DB_Reference.md) for SQL patterns.
   The DB is ~1.9 MB and downloads in ~18 seconds. It is **auto-refreshed** when Atlas Academy releases new game data.

   **⚡ Yu-Gi-Oh! Database Bootstrap** (run BEFORE any YGO card/archetype lookup):
   When Yu-Gi-Oh content is detected, check if `ygo_cards.db` exists:
   ```
   python3 scripts/fetch_ygo_db.py --check --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
   ```
   If exit code is 1 (missing/stale), build it:
   ```
   python3 scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
   ```
   Then query it with sqlite3. See [YGO_DB_Reference.md](skills/reference/Yu-Gi-Oh%20DATA/YGO_DB_Reference.md) for SQL patterns.
   The DB is ~10–20 MB and downloads in ~60–180 seconds. It is **auto-refreshed** when YGOPRODeck releases a new database_version.

   **Canonical Subagent Prompt Template:**
   Read [subagent-prompt-template.md](subagent-prompt-template.md) for the full prompt to send to each chunk subagent.

   **Key rule injected into every subagent prompt:**
   - 5-min chunk → **1 timestamp default, 2 MAX**
   - New timestamp ONLY on: game switch, speaker join/leave, completely new activity
   - Multiple sub-topics in same conversation → MERGE into 1
   - Subagent must run Density Self-Check (Step 8) and merge down to ≤ 2 before submitting

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
      "desc": "สรุปภาพรวมของช่วงนี้ 1-2 บรรทัด",
      "body": "HH:MM:SS - [Tag] คำอธิบาย\nHH:MM:SS - [Tag] คำอธิบาย"
    }
  ]
  ```
  > **Important:** Never hardcode the parts list or output path inside a one-off script. Always use `assemble_timestamps.py` with a `parts.json` input file. This keeps data and assembly logic separate and reusable across streams.

## 🧭 Orchestration Checklist (Cloud)

1. Environment Check → verify `yt-dlp` and `python3`.
2. Download & Chunk (add --vision to extract visual frames for pronoun/visual referent resolution):
```bash
find $HOME/.gemini $HOME/.config/opencode $HOME/.agents \
  -path "*/anibon-stream-synthesis/scripts/prepare_video.py" 2>/dev/null | head -1

python3 "/absolute/path/to/scripts/prepare_video.py" "VIDEO_URL" --format xml --block 300 --overlap 30 --vision
```
3. Pre-flight Analysis → run `python3 /absolute/path/to/scripts/anibon-analyzer.py /path/to/workspace`.
   - Use output to route chunks (e.g. tokusatsu vs gaming).
   - Resolve `GAP DETECTED` warnings before delegating tasks.
   - Plan chunk byte limits (split blocks if they read OVER).
4. DB Bootstrap → run `--check` for FGO/YGO if detected; build if exit 1.
5. Parallel Analysis → spawn subagents per chunk using the **Canonical Subagent Prompt Template** above.
6. Final Assembly → write `parts.json` to the workspace folder (`~/youtube_<video_id>_workspace/parts.json`), then run:
```bash
python3 /absolute/path/to/scripts/assemble_timestamps.py ~/youtube_<video_id>_workspace/parts.json
# Output: ~/youtube_<video_id>_workspace/anibon_timestamps.md
python3 /absolute/path/to/skills/anibon-timestamper/scripts/check_sections.py ~/youtube_<video_id>_workspace/anibon_timestamps.md
```
Both `parts.json` and `anibon_timestamps.md` MUST be saved inside the workspace folder, NOT the session artifacts dir.

## Iron Rules

- **ALWAYS check video publish date first**.
- **Use Dynamic Subagent Routing**: Do not guess the stream type upfront. Subagents load matching sub-skills based on what they see in their chunk.
- **ONE FILE, NOT MANY**: Final output is always ONE `.md` file. Visual separators replace separate files. Never create `part1.md`, `part2.md`, etc.
- **OUTPUT IN WORKSPACE**: `parts.json` and the final `anibon_timestamps.md` MUST be written to `~/youtube_<video_id>_workspace/`. Do NOT place them in the session artifacts directory.
- **4,500 BYTE HARD CAP (Thai)**: Each pasted block MUST be under 4,500 UTF-8 bytes. Thai chars cost 3 bytes each. Target **3,500 bytes** as ceiling. Run `check_sections.py` — split until all sections show ✅.
- **PRE-SPLIT**: Talk session > 20 min or Gaming > 60 min → plan A/B split before assembly.
- **SEPARATOR FORMAT IS FIXED**: Always use the `═══` block format. Never improvise with `---` or plain text.
- **NO GAPS**: Never allow gaps > 10 minutes without a timestamp unless transcript is verified silent. Check chunk sequence before final assembly.
