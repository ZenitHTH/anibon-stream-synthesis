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
   
   - **Parallel Strategy (Cloud Models)**: For streams over 2 hours, if using a large cloud model, you can spawn parallel subagents to process the chunks output by the command above.
   - **Sequential Subagent Loop (Local Models / Ollama)**: If running on a local AI (e.g., `gemma4` or `qwen2.5-coder` on Ollama) where context window and token limits are strict:
     - **DO NOT spawn parallel subagents.**
     - Instead, process chunks **sequentially** using a single-agent loop: Spawn **exactly 1 subagent** to analyze `chunk_00.json`.
     - Once the subagent returns its output, write it to `chunk_00_output.md`.
     - Immediately spawn a **new subagent** to process `chunk_01.json`, write to `chunk_01_output.md`, and repeat.
     - This keeps active context/tokens per turn extremely small, preventing memory overflow while ensuring the local AI does not forget formatting rules.
   - **Low-Context Detection**: ALWAYS verify the maximum context window of the assigned subagent model (e.g., `gemma4:31b` or `e2b` usually have strict 4k-8k limits).
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
    Use this template when delegating chunks to subagents:
    "You are processing Chunk <N>.
    CONTEXT: Stream recorded on <Upload Date> (<Time_Ago>).
    
    You MUST execute your task following this step-by-step processing workflow:
    
    ### Step 1: Scan and Detect Signals
    Read the transcript text below. Look for specific topics, transitions, or game content.
    - Standard signals: Gacha pulls, gameplay, talk/news, tokusatsu, watch parties, greetings.
    - Match card names or game terms against FGO/YGO database records if provided.
    
    ### Step 2: Time Alignment
    For every major transition, game switch, or topic change:
    - Locate the exact starting time of that event in the transcript.
    - Format the timestamp as `HH:MM:SS` (or `MM:SS` if the stream is under an hour).
    
    ### Step 3: Select the Correct Tag
    Use only standard tags matching the sub-skill detection rules:
    - `[Greeting]`: Stream intro / saying hi
    - `[Talk]`: Generic chatting / chat interaction / story tangents
    - `[News]`: Reading news or commenting on real-world events (apply safety metaphors!)
    - `[Gameplay]`: Playing a game / fighting stages
    - `[Gacha]`: Drawing cards / summoning
    - `[Boss]`: Boss fight / final stage battles
    - `[WatchParty]`: Watch along reaction / episode reviews
    - `[Reaction]`: General reaction to trailers or videos
    
    ### Step 4: Write Description
    - Write a short, descriptive summary of the event in <User's Requested Language>.
    - Keep it concise, precise, and use correct terms/names from the FGO/YGO databases.
    
    ### Step 5: Format Output
    Output your result using this exact format for every line:
    `HH:MM:SS - [Tag] Description`
    
    Do NOT include any introduction, thinking process, or additional text outside of this format.
    
    CRITICAL RULES: <Orchestrator: Pre-read the matching sub-skills yourself and inject a distilled 3-4 bullet summary of their Iron Rules here. Do NOT tell the subagent to read files.>
    TRANSCRIPT:
    <Orchestrator: Inject the raw text of the 5-minute chunk directly here>"

4. **Reduce Stage (Final Assembly)**
   
   - Once all subagents return their timestamps, combine them chronologically.
   - **Splitting Parts & YouTube Limits**: When a specific game or talk section spans a very long duration, you MUST split it into numbered parts (e.g., "Talk & Gacha Game Discussions - Part 1", "Talk & Gacha Game Discussions - Part 2").
   - **CRITICAL BYTE LIMIT**: YouTube validates comments by **UTF-8 byte size**, not character count. Thai characters are 3 bytes each, so a block with 2,000 Thai characters already costs ~6,000 bytes — exceeding YouTube's ~4,500-byte server cap. **NEVER** let the full pasted block (header + body) exceed **4,500 bytes**. If a section would exceed this, split it **before** assembly:
     - For a long Gaming or Talk section: split so each block stays under **3,500 bytes** (the WARN threshold — leave margin).
     - Do NOT wait until after assembly to discover the block is too long — estimate during Topic Scan (Step 5).
     - Rule of thumb: If a talk session lasts >15 minutes of continuous content, plan at least 2 parts. If a gameplay session lasts >60 minutes, plan at least 2 parts.
   - **DEFAULT FORMAT**: แบ่งตามด่าน/หัวข้อ (by stage/section) with game section headers (e.g., `═══════ 🎮 Stage Name ═══════`). If the user requests a different format, override before assembly.
   - **Length Limits**: See Step 5 of the Step-by-Step Guide.
   - **⚠️ SINGLE FILE RULE**: ALL topic parts MUST go into ONE file. Do NOT create separate files per topic. Use visual separator blocks between topics (see Step 5 for the exact format).

## Helper Scripts & Writing Code

Available scripts (all in the `scripts/` directory next to this SKILL.md):
- **`prepare_video.py`** — downloads transcript, cleans, and chunks (Step 2).
- **`clean_transcript.py`** — cleans raw json3 and/or outputs chunks (called by prepare_video).
- **`check_sections.py`** — checks section sizes in the final timestamp `.md` file, flags sections over 4,500/5,000 chars, and suggests midpoint split timestamps. Run after assembly.

## 🧭 Orchestration Workflow (Cloud / Standard)

1. **Environment Check**: Verify `yt-dlp` and `python3` are installed.
2. **Download & Chunk**: Run `python3 scripts/prepare_video.py <URL>` to chunk the transcript.
3. **FGO / YGO Databases**: If transcript contains FGO/YGO content, ensure databases are updated:
   - FGO: `python3 scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"`
   - YGO: `python3 scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"`
4. **Parallel Analysis**: Spawn parallel subagents to process the chunks concurrently using the template below.
5. **Final Assembly**: Concatenate subagent outputs chronologically, split into parts of under 4,500 characters, and verify with `check_sections.py`.

**Subagent Template:**
```
You are processing Chunk <N> (MM:SS - MM:SS).
1. Scan transcript for gameplay, gacha, or talk.
2. Align timestamps in HH:MM:SS format.
3. Choose Tag: [Greeting], [Talk], [News], [Gameplay], [Gacha], [Boss], [WatchParty], [Reaction].
4. Output: "HH:MM:SS - [Tag] Description" (Thai language).
TRANSCRIPT: <raw transcript text>
```

## Iron Rules

- **ALWAYS check video publish date first**.
- **Use Dynamic Subagent Routing**: Do not guess the stream type for the whole video upfront. Tell the subagents to load the specific sub-skill based on what they see in their 15-minute chunk!
- **ONE FILE, NOT MANY**: The final output is always ONE `.md` file. Visual separators replace separate files. Never create `part1.md`, `part2.md`, etc.
- **4,500 BYTE HARD CAP (Thai)**: Each full pasted block MUST be under 4,500 UTF-8 bytes. Thai chars cost 3 bytes each — a 5,000-char block can be ~15,000 bytes. Target **3,500 bytes** as your ceiling. Run `check_sections.py` after assembly — it now measures bytes of the full block. Split until every section shows ✅.
- **PRE-SPLIT IN STEP 5**: Talk session > 20 min or Gaming session > 60 min → plan A/B split before assembly. Catching it late means extra editing work.
- **TOPIC SCAN BEFORE ASSEMBLY**: Always run Step 5 (Topic Scan) before Step 6 (Assembly). Never concatenate blindly without knowing where topic boundaries are.
- **SEPARATOR FORMAT IS FIXED**: Always use the `═══` block format shown in Step 6b. Do not improvise with `---`, `###`, or plain text.
- **NO GAPS / MISSING SEGMENTS**: Never allow gaps of more than 10 minutes without a timestamp unless the transcript is verified to be silent or pure repetition. Check sequence file lists to ensure no chunk was skipped during assembly.
