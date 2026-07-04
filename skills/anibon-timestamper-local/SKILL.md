---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon streams on a LOCAL model (Ollama, gemma4, qwen). Focuses on step-by-step sequential looping, minimal context, and goldfish brain rules.
title: "Anibon Timestamper (Local AI Edition)"
summary: "Sequential 5-minute chunk processor for long-form streams. Designed for local LLMs with tight context limits — processes each chunk inline, writes output to file, and auto-resumes until complete."
---

# 🎬 Anibon Timestamper (Local AI Edition)

Optimized for local LLMs with limited context windows (e.g. Gemma 4, Qwen 2.5). 
Processes video transcripts in sequential chunks to preserve memory.

---

## ⚡ Goldfish Brain Rules (CRITICAL)
Your working memory is extremely limited. To prevent hallucination or crashes:
1. **State your step**: Before any action, state what step you are on.
2. **One tool per turn**: Never run batch actions.
3. **Save and forget**: Write output for each chunk to a separate file, then flush it from your memory.
4. **Process inline**: Process each chunk directly in this session. Read the `.txt` file, output timestamps inline, and write to the output file yourself. Do NOT attempt to spawn subagents or run hallucinated scripts.
5. **No `<think>` tags**: Never output or wrap your thinking process in `<think>` or `</think>` tags due to local server parsing bugs. Instead, write your thinking process directly as plain text in the normal response stream (i.e. "think very loud" in normal text).
6. **Handoff when full**: If context window becomes exhausted during processing, save state using `anibon-timestamper-handoff` and tell the user to reset the session.

---

## 🧭 Step-by-Step Guide

### Step 1: Verify Environment
Verify shell and tools before downloading:
- Run: `uname -a` (Unix) OR `$PSVersionTable` (Windows)
- Run: `command -v yt-dlp` (Unix) OR `Get-Command yt-dlp` (Windows)

### Step 2: Download & Chunk Transcript
Find the absolute path of the `prepare_video.py` script globally:
- Unix: `find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name "prepare_video.py" 2>/dev/null | head -1`
- Windows (PowerShell): `Get-ChildItem -Path $env:USERPROFILE -Filter "prepare_video.py" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName`

Run the script using its absolute path to fetch and chunk the transcript (5-min blocks, 30s overlap):
```bash
# Find script globally
find $HOME/.gemini $HOME/.config/opencode $HOME/.agents \
  -path "*/anibon-stream-synthesis/scripts/prepare_video.py" 2>/dev/null | head -1

# Run with txt format
python3 "/absolute/path/to/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```
*(If blocked by YouTube, ask user for cookies permission or to upload raw_transcript.json).*

### Step 3: Sequential Chunk Loop
Process `chunk_00.txt`, then `chunk_01.txt` sequentially. For each chunk:
1. **Pre-read sub-skills**: Check chunk signals (gacha, talk, gameplay, tokusatsu) and load matching sub-skills.
2. **FGO / YGO Bootstrap**: If game matches, run `--check` and build the SQLite database if missing (exit 1).
3. **Setup Output**: Ensure the `chunk_outputs/` directory exists in the workspace.
4. **Process Inline**: Read the content of `chunk_XX.txt`. Generate timestamps following the Prompt Template rules below.
5. **Write Output**: Save your generated timestamps to `chunk_outputs/chunk_XX_output.md` using the output format below.
6. **Auto-resume**: Immediately read and process the next chunk (`chunk_XX+1.txt`). Do NOT wait for user confirmation.
7. **Context Handoff**: If you notice high latency or memory issues, write `anibon_timestamper_state.json` with the current chunk index, explain the handoff to the user, and stop (see `anibon-timestamper-handoff`).

---

#### 📄 Chunk TXT Format
Each `chunks/chunk_NN.txt` file contains:
```
CHUNK NN | HH:MM:SS–HH:MM:SS | cutoff=HH:MM:SS
(HH:MM:SS) transcript line text
(HH:MM:SS) transcript line text
...
```
- **Line 1**: Header with chunk index, time range, and cutoff timestamp
- **Body**: one `(HH:MM:SS) text` line per transcript entry, chronological
- **Cutoff rule**: Skip entries with timestamp > cutoff when selecting timestamps (overlap zone)

---

#### ⏱️ Timing Rules

**Overlap cutoff:** Only emit timestamps for events with `item.start < end_sec - 30`. Ignore anything in the last 30 seconds of the chunk — the next chunk will cover it cleanly.

**Timing correction — when timestamps feel drifted:**
- If the transcript text at a given second doesn't match what you expect (e.g. text says "end screen" but timestamp is 00:05:10 into a 3-hour stream), **trust `item.start` over your intuition** — the timestamps come directly from YouTube's caption file and are authoritative.
- If two consecutive timestamps are more than **10 minutes apart** with no entries in between, check if you skipped items. Do NOT invent a timestamp to fill the gap — leave it empty and note `[GAP: no transcript data]`.
- If a tag event (e.g. gacha pull) clearly started earlier than the earliest item in your chunk, use `start_sec` as the floor — never go below it.

---

#### 📄 Prompt Template
When processing a chunk, strictly follow these rules:

RULES:
- Identify chunk start_sec and end_sec, calculate overlap cutoff = end_sec - 30.
- Use the pre-calculated `(HH:MM:SS)` directly. Do NOT calculate the math yourself.
- Skip any entry whose timestamp > the cutoff shown in the chunk header line.
- **LIMIT**: Maximum 10 timestamps per 5-minute chunk.
- **GROUPING (CRITICAL)**: If multiple sentences within 1-2 minutes discuss the SAME topic, emit ONLY ONE timestamp for the start of that topic. Do not log every single sentence!
- **MINIMUM GAP**: Timestamps must be at least 30-60 seconds apart unless there is a major Tag change (e.g. from [Talk] to [Gameplay]).
- **WARNING**: Do NOT summarize the entire chunk into a single vague timestamp! You must still pick specific discrete events, just limit the quantity.
- One line per event. Format: HH:MM:SS - [Tag] Description (Thai).
- **TAGS (STRICT)**: Use ONLY the exact Tags listed below. Do NOT invent new tags (e.g., do not use [Donation]).
  - `[Greeting]`: Saying hello/goodbye, thanking for subs/members/donations.
  - `[Talk]`: General chatting, updating life, answering Q&A.
  - `[News]`: Reading or analyzing news, dramas, or patch notes.
  - `[Gameplay]`: Playing games normally, doing story quests, or farming.
  - `[Gacha]`: Rolling/pulling in gacha games.
  - `[Boss]`: Fighting a major boss in a game.
  - `[WatchParty]`: Reacting to official streams, trailers, or videos together.
  - `[Reaction]`: Sudden strong reactions (laughing hard, getting jumpscared).
- **DESCRIPTION (ACTIONABLE)**: State the actual subject discussed (e.g. "บ๊อตอธิบายความต่างของ MOU 43-44"). Do NOT write internal feelings (e.g. "ความไม่แน่ใจในข้อมูล").
- Output ONLY the timestamp lines into the output file. Do NOT write markdown headers (e.g. `# Chunk 34`), explanations, or any other extra text.
- If no events found: output exactly one line → HH:MM:SS - [Talk] (ไม่มีเหตุการณ์สำคัญ)

---

#### 📋 Output Format for `chunk_outputs/chunk_XX_output.md`
Each output file must follow this exact format so `cat` concatenation works cleanly:
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->
00:00:12 - [Greeting] บ๊อตทักทายผู้ชม เริ่มสตรีม
00:01:34 - [Talk] คุยเรื่องข่าวสาร
00:03:45 - [Gacha] ดึงการ์ด FGO รอบแรก
```
- **First line**: HTML comment with chunk index and time range — used as a merge marker
- **Body**: one `HH:MM:SS - [Tag] Description` line per event, chronological order
- **Never** include your thinking, apologies, or meta-commentary in this file

---

### Step 4: Topic Map & Assembly
When all chunks are finished, concatenate them:
- Unix: `cat chunk_outputs/chunk_*_output.md > raw_timestamps.txt`
- Windows: `Get-Content chunk_outputs/chunk_*_output.md | Set-Content raw_timestamps.txt`

Now, you MUST assemble the final output file `timestamp_VIDEO_ID.md`. To do this, follow these explicit steps for splitting and formatting:

**Step 4.1: Split by Topic & Size**
Read the concatenated timestamps. Group them into major topic shifts (e.g., Talk, Gameplay, WatchParty). If a section exceeds **50-60 lines of timestamps** (to stay under the YouTube character limit), you must split it into Part 1, Part 2, etc. Do not try to count characters, just count lines.

**Step 4.2: Draft the Header (CRITICAL)**
For each section you create, you must write a header. Do not rush this. Follow this thought process:
1. **Analyze**: Read the timestamps in this section. What are the 2-3 most important things discussed or played?
2. **Title**: Pick a short category title (e.g., "คุยประเด็นข่าวดราม่า", "FGO ลุยเนื้อเรื่องหลัก").
3. **Summary**: Write a 1-2 sentence summary covering the actual core events. (e.g., "บ๊อตวิเคราะห์ประเด็นดราม่าตำรวจด้อม และพูดถึงเรื่อง MOU 43-44 ที่มีข้อโต้เถียงกัน"). **DO NOT** just repeat the title!

**Step 4.3: Apply the Separator Format**
Use this exact format to print the header you drafted in Step 4.2:
```
📌 ส่วนที่ N: [ใส่ Summary 1-2 บรรทัดที่เขียนไว้]
(หัวข้อ: [ใส่ Title ที่คิดไว้] | ⏱ เริ่ม: HH:MM:SS)
---------------------------------------------------------
```
*Note: The `HH:MM:SS` must be the timestamp of the VERY FIRST event in this section. Remove all `<!-- chunk_XX -->` markers during assembly.*

### Step 5: Verification Check
Find and run `check_sections.py` on the final file to verify character counts:
```bash
# Find the script (use global find, same as Step 2)
CHECK_SCRIPT=$(find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name "check_sections.py" 2>/dev/null | head -1)
python3 "$CHECK_SCRIPT" timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️). Register the final file in your workspace.
