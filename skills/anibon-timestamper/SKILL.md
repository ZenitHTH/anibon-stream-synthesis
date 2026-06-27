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
   
   - For streams over 2 hours, **YOU MUST** spawn parallel subagents to process the chunks output by the command above (use whatever parallel task/subagent mechanism the current tool provides: `subagent-driven-development` in Antigravity, `Task` in Claude Code, or concurrent tool calls in OpenCode).
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
   TASK: Scan the transcript for detection signals, identify topics, generate timestamps. Output ONLY the timestamps. Format: `HH:MM:SS - [Tag] Description` (Write the description in <User's Requested Language>).
   CRITICAL RULES: <Orchestrator: Pre-read the matching sub-skills yourself and inject a distilled 3-4 bullet summary of their Iron Rules here. Do NOT tell the subagent to read files.>
   TRANSCRIPT:
   <Orchestrator: Inject the raw text of the 5-minute chunk directly here>"

4. **Reduce Stage (Final Assembly)**
   
   - Once all subagents return their timestamps, combine them chronologically.
   - **Splitting Parts & YouTube Limits**: When a specific game or talk section spans a very long duration, you MUST split it into numbered parts (e.g., "Talk & Gacha Game Discussions - Part 1", "Talk & Gacha Game Discussions - Part 2"). 
   - **CRITICAL CHARACTER LIMIT**: The YouTube comment character limit is **5,000 characters (Thai language density)**. **NEVER** let a single part block exceed 5,000 characters. If a section would exceed this, you MUST split it **before** assembly:
     - For a long Gaming section: split every ~4,500 characters into separate sub-parts (2A, 2B, 2C...).
     - Do NOT wait until after assembly to discover the block is too long — estimate during Topic Scan (Step 5).
     - Rule of thumb: If a session lasts >90 minutes of continuous gameplay, it will likely need at least 2 parts.
   - **DEFAULT FORMAT**: แบ่งตามด่าน/หัวข้อ (by stage/section) with game section headers (e.g., `═══════ 🎮 Stage Name ═══════`). If the user requests a different format, override before assembly.
   - **Length Limits**: See Step 5 of the Step-by-Step Guide.
   - **⚠️ SINGLE FILE RULE**: ALL topic parts MUST go into ONE file. Do NOT create separate files per topic. Use visual separator blocks between topics (see Step 5 for the exact format).

## Helper Scripts & Writing Code

<PONYTAIL-GATE>
**BEFORE WRITING ANY NEW SCRIPT CODE**: Ask YAGNI? Does the standard library do it? Can it be one line? Build the absolute minimum that works. A 1-line bash pipe or python snippet is better than 100 lines of `argparse` boilerplate. No unrequested abstractions.
</PONYTAIL-GATE>

Available scripts (all in the `scripts/` directory next to this SKILL.md):
- **`prepare_video.py`** — downloads transcript, cleans, and chunks (Step 2).
- **`clean_transcript.py`** — cleans raw json3 and/or outputs chunks (called by prepare_video).
- **`check_sections.py`** — checks section sizes in the final timestamp `.md` file, flags sections over 4,500/5,000 chars, and suggests midpoint split timestamps. Run after assembly.

**CRITICAL**: NEVER build custom CLI tools for searching or dumping JSON. Use native tools like `jq` or Python one-liners.

## STRICT Step-by-Step Guide for Local LLMs

**CRITICAL DIRECTIVE**: You are REQUIRED to follow this guide strictly, step-by-step. Local LLMs (like gemma, llama3, qwen) may struggle with long reasoning chains or complex tool execution. 

**GOLDFISH BRAIN PROTOCOL**: Your working memory is extremely limited. To prevent yourself from getting lost or hallucinating, you MUST "think out loud":
1. **State your current step**: Before taking any action, write down exactly what step you are on (e.g., "I am currently on Step 2. I am going to search for the script.").
2. **Acknowledge the result**: After a tool finishes, explicitly state what happened (e.g., "The command succeeded. I am now moving to Step 3.").
3. **Never batch actions**: Do exactly ONE tool call or logical step at a time. Do not try to read, process, and write in a single turn.

- You MUST execute ONE step at a time.
- You MUST complete a step and output its result before reading or attempting the next step.
- DO NOT skip ahead under any circumstances.

### Step 1: MANDATORY Environment Check

**DO NOT SKIP**: You MUST run this check and output the result BEFORE attempting Step 2. Do not guess.
**Action**: Determine if the OS is Linux/macOS or Windows, and if the shell is Bash/Zsh or PowerShell.

- Run `echo $SHELL` and `uname -a` (Unix) OR `$PSVersionTable` (Windows).
- Run `command -v yt-dlp` (Unix) or `Get-Command yt-dlp` (Windows) to verify tools.
  **CRITICAL**: You are FORBIDDEN from downloading the transcript until you have verified your shell and tools.

### Step 2: Prepare Workspace, Download, and Chunk Transcript

**Action**: Run the `prepare_video.py` script. This single script automatically handles creating the `youtube_VIDEO_ID_workspace`, downloading the transcript safely, and chunking it into `chunks/chunk_00.json`.

- **Locate and Run the Script**:
  1. The `prepare_video.py` script is sitting in the home directory of the skill. Find its exact absolute path by restricting your search to the skill/plugin folders: 
     `find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name "prepare_video.py" 2>/dev/null`
  2. Once you have the absolute path from the output, run the script using Python:
     `python "/absolute/path/to/prepare_video.py" "VIDEO_URL"`

**When Stuck (YouTube 429 Blocked / Sign-in required)**:

- **Anti-Bot Block Handling**: If the script fails because YouTube blocks it, ask the user which browser they use to append `--cookies-from-browser` (locally) OR ask them to manually upload `raw_transcript.json`.
  **When Stuck (No Transcript Available)**: Stop and inform the user. Do not invent timestamps.

### Step 4: Analyze Chunks (The Loop)
**Action**: Process `chunks/chunk_00.json`, then `chunk_01.json`, sequentially until NO CHUNKS REMAIN. Read ONE chunk file at a time.
**CRITICAL WRITING & LOOPING RULE FOR LOCAL LLMs**: Your built-in `write` tool OVERWRITES files; it does not append. If you try to write all chunks into one file, you will erase your previous work!
1. Read ONE chunk file.
2. Use your `write` tool to save the timestamps into a **SEPARATE, uniquely named file** for that chunk (e.g., `chunk_00_output.md`, `chunk_01_output.md`). 
3. **Context Flushing**: Once the file is written, forget everything about that chunk. Do not summarize it in your scratchpad. Assume the job for that chunk is 100% complete.
4. **STOP & WAIT MARKER**: You MUST output exactly `[READY FOR NEXT CHUNK]` and then stop. Do not read the next chunk until the orchestrator replies "continue" or "next chunk".
**CRITICAL PATH RULE**: File-reading tools DO NOT expand `$HOME` or `~`. You MUST use the true **absolute path**. Run `pwd` or `Get-Location` first to find the exact directory, then append the file path.
   - **Detect signals first** (see Step 3 Detection Signals table), then pre-read the matching sub-skills from `skills/` and summarize their Iron Rules in your scratchpad before analyzing the chunk.

### Step 5: Topic Analysis — Identify Major Topic Blocks BEFORE Assembly

**⚠️ THIS STEP IS MANDATORY FOR STREAMS LONGER THAN 1 HOUR. DO NOT SKIP.**

Before concatenating chunk outputs, you MUST do a "Topic Scan" across the assembled raw timestamps. This lets you define where one major topic ends and another begins.

**Why this matters**: YouTube comments have a ~5,000 character limit. A 5-hour stream may produce 3–5 distinct major topic blocks. Each block needs a separator header in the final file so viewers know which comment to paste where.

**HOW TO IDENTIFY TOPIC BLOCKS:**

1. **Quick-scan ALL chunk output files** using a shell command (do NOT read them one by one in your head):
   - Windows: `Get-Content chunk_*_output.md | Select-String -Pattern "\[WatchParty\]|\[Gameplay\]|\[Greeting\]|\[News\]" | Select-Object -First 30`
   - Unix: `grep -h '\[WatchParty\]\|\[Gameplay\]\|\[Greeting\]\|\[News\]' chunk_*_output.md | head -30`

2. **Find the first timestamp of each major activity change**. Examples:
   - If `[Greeting]` appears at `00:00:30` → That's the start of the **Opening/Talk** block.
   - If `[Gameplay]` first appears at `00:45:00` → That's where **Gaming** begins.
   - If `[WatchParty]` first appears at `02:10:00` → That's where the **Watch Party** begins.

3. **Write a Topic Map** in your scratchpad BEFORE assembly. Example:
   ```
   Topic Map:
   - Part 1: Opening & Talk     → chunk_00 to chunk_08  (00:00:00 – 00:44:59)
   - Part 2: Gaming Session     → chunk_09 to chunk_25  (00:45:00 – 02:09:59)
   - Part 3: Watch Party        → chunk_26 to chunk_40  (02:10:00 – 03:20:00)
   - Part 4: Closing Talk       → chunk_41 to chunk_48  (03:20:01 – 04:00:00)
   ```

4. **Decide on Part Names** (in Thai, since that is the target language for Anibon streams). Examples:
   - `📌 ส่วนที่ 1 — เปิดสตรีม / พูดคุยทั่วไป`
   - `📌 ส่วนที่ 2 — เล่นเกม: [ชื่อเกม]`
   - `📌 ส่วนที่ 3 — ดูอนิเมะ / Watch Party: [ชื่อซีรีส์]`

---

### Step 6: Final Assembly — ONE FILE, MULTIPLE TOPIC SECTIONS

**Action**: Combine all chunk outputs into ONE final artifact file named exactly `timestamp_<video_id>.md`.

**⚠️ THE GOLDEN RULE**: You are writing ONE file. You are NOT creating one file per topic. Topics are separated by a visual block INSIDE the same file.

#### Sub-step 6a: Raw Concatenation (PowerShell)

First, concatenate all chunk outputs in order:
```powershell
Get-Content -Encoding UTF8 (Get-ChildItem chunk_*_output.md | Sort-Object Name) | Set-Content -Encoding UTF8 timestamp_VIDEO_ID.md
```
- Replace `VIDEO_ID` with the actual YouTube video ID (e.g., `rP8AHWOIXtI`).
- Do NOT use `*_output.md` without `Sort-Object Name` — the glob may produce wrong order on Windows.

#### Sub-step 6b: Insert Topic Separator Headers

After concatenation, you MUST insert topic separator blocks at the **exact timestamp boundaries** you found in Step 5.

**SEPARATOR FORMAT** (copy this exactly — do not invent your own):
```
═══════════════════════════════════════════════════════════
📌 ส่วนที่ N — [ชื่อหัวข้อ]
   ⏱ เริ่ม: HH:MM:SS  |  เนื้อหา: [สรุปสั้นๆ]
═══════════════════════════════════════════════════════════
```

**HOW TO INSERT**: Open the final file, find the line with the matching timestamp (e.g., `00:45:00`), and paste the separator block **directly above** that line.

**Example of correct final file structure:**
```
═══════════════════════════════════════════════════════════
📌 ส่วนที่ 1 — เปิดสตรีม / พูดคุยทั่วไป
   ⏱ เริ่ม: 00:00:00  |  เนื้อหา: ทักทาย, คุยข่าว
═══════════════════════════════════════════════════════════
00:00:30 - [Greeting] บ๊อตเปิดสตรีม ทักทายแชท
00:02:10 - [Talk] คุยเรื่องข่าวอนิเมะประจำสัปดาห์
...
═══════════════════════════════════════════════════════════
📌 ส่วนที่ 2 — เล่นเกม: Kakuseihunter Omegahorn
   ⏱ เริ่ม: 00:45:00  |  เนื้อหา: เล่นเกม, บอส, กาชา
═══════════════════════════════════════════════════════════
00:45:00 - [Gameplay] เริ่มเล่น Kakuseihunter Omegahorn
00:52:30 - [Boss] เจอบอส ด่านที่ 3
...
═══════════════════════════════════════════════════════════
📌 ส่วนที่ 3 — Watch Party: Kamen Rider Zeztz EP 40
   ⏱ เริ่ม: 02:10:00  |  เนื้อหา: ดูซีรีส์, รีแอค, วิเคราะห์
═══════════════════════════════════════════════════════════
02:10:00 - [WatchParty] เริ่ม Watch Party มาสค์ไรเดอร์เซสซึ EP 40
02:15:44 - [Reaction] บ๊อตรีแอคฉากแอ็กชั่น
...
```

#### Sub-step 6c: YouTube Comment Block Size Check

After inserting separators, run **`check_sections.py`** — do NOT count manually:
```bash
python "$(find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name check_sections.py 2>/dev/null | head -1)" timestamp_VIDEO_ID.md
```

The script will:
- Print each section's char count with ✅ OK / ⚠️ WARN (>4,500) / ❌ OVER (>5,000) status.
- For any flagged section, print the **exact timestamp to split at** (midpoint of that section).

If any section is flagged ⚠️ or ❌, you MUST split it:
  - Rename the header to `📌 ส่วนที่ NA — ...`
  - Insert a new separator at the suggested split timestamp: `📌 ส่วนที่ NB — ...`
  - Re-run `check_sections.py` to confirm all sections pass.
  - Keep splitting (NC, ND...) until the script shows ✅ for every section.

**When to pre-split (plan this in Step 5 BEFORE assembly — saves a full re-run)**:
  - Continuous gameplay session > 90 minutes → plan at least 2 parts.
  - Continuous talk session > 30 minutes → plan at least 2 parts.
  - Use the 4,500-char warn threshold as your target ceiling, not 5,000.

#### Sub-step 6d: Register Artifact

Save the final file to the artifact directory:
```powershell
Copy-Item timestamp_VIDEO_ID.md "C:\Users\SMTE-PC\.gemini\antigravity-cli\brain\<conversation-id>\timestamp_VIDEO_ID.md"
```
Then use the `write_to_file` tool with `Overwrite=true` to register it as an artifact (if your environment supports it).

#### Sub-step 6e: Missing Segment & Topic Gap Verification (MANDATORY)

Before completing the task, you MUST perform a gap analysis check on the output `timestamp_<video_id>.md` to ensure nothing was missed:
1. **Sequence Check**: Verify that the chunk files processed cover the entire video timeline sequentially (e.g., from 00:00:00 to the end of the stream) without leaving gaps (e.g., a missing 15-minute chunk).
2. **High-Value Gaps**: Scan the final list for any time jump of more than **10 minutes** without a timestamp. If such a gap exists, doublecheck the raw transcript for that time period to ensure no major event (like a new game switch, a gacha pull, or a topic change) was missed.
3. **Missing Tag Check**: Ensure that if FGO or YGO topics were discussed (as verified by the DB download triggers), the corresponding `[Gacha]`, `[Gameplay]`, or `[PatchNote]` tags exist in the output.

---

## Iron Rules

- **ALWAYS check video publish date first**.
- **Use Dynamic Subagent Routing**: Do not guess the stream type for the whole video upfront. Tell the subagents to load the specific sub-skill based on what they see in their 15-minute chunk!
- **ONE FILE, NOT MANY**: The final output is always ONE `.md` file. Visual separators replace separate files. Never create `part1.md`, `part2.md`, etc.
- **5,000 CHAR HARD CAP (Thai)**: Each part block MUST be 5,000 chars or fewer. Target 4,500 as your ceiling to leave margin. Run `check_sections.py` after assembly — never check manually. Split until the script shows ✅ for every section.
- **PRE-SPLIT IN STEP 5**: Talk session > 30 min or Gaming session > 90 min → plan A/B split before assembly. Catching it late means extra editing work.
- **TOPIC SCAN BEFORE ASSEMBLY**: Always run Step 5 (Topic Scan) before Step 6 (Assembly). Never concatenate blindly without knowing where topic boundaries are.
- **SEPARATOR FORMAT IS FIXED**: Always use the `═══` block format shown in Step 6b. Do not improvise with `---`, `###`, or plain text.
- **NO GAPS / MISSING SEGMENTS**: Never allow gaps of more than 10 minutes without a timestamp unless the transcript is verified to be silent or pure repetition. Check sequence file lists to ensure no chunk was skipped during assembly.
