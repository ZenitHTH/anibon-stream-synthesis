---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon streams on a LOCAL model (Ollama, gemma4, qwen). Focuses on step-by-step sequential looping, minimal context, and goldfish brain rules.
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
5. **No dry-running**: NEVER describe a file operation in plain text without doing it. Every `read`, `write`, or `bash` action MUST be a real tool call. If you say "I will read chunk_00.txt", you MUST immediately call the tool — not narrate it. If you cannot call a tool, output exactly: `[STUCK: cannot call tool, awaiting user input]` and stop.
6. **STOP LOOP rule**: If you notice yourself saying "Wait", "Actually", "One more thing", or restarting your reasoning — you are in a loop. **STOP IMMEDIATELY and call a tool.** The rule is: decide → act → done. Never revise a decision more than once.
7. **Handoff when full**: If context window becomes exhausted during processing, save state using `anibon-timestamper-handoff` and tell the user to reset the session.
8. **Forward Slashes Only**: ALWAYS use forward slashes (`/`) for file paths in tool calls and bash commands (e.g., `C:/Users/peter/...`). Single backslashes will be stripped by the shell and cause errors.

---

## 🧭 Step-by-Step Guide

### Step 1: Resolve Plugin Path & Verify Tools
Shell is MINGW64/bash. Use Unix commands only.
1. Run: `uname -a && command -v yt-dlp && python3 --version`
2. Resolve `[PLUGIN_ROOT]`: Look at the `<skill location="...">` XML tag at the top of your instructions. Extract the directory path up to (but not including) `skills/`. Replace all `\` with `/`. Example result: `C:/Users/peter/.pi/agent/git/github.com/ZenitHTH/anibon-stream-synthesis`

### Step 2: Download & Chunk Transcript
Run this exact command. Do NOT search for the script:
```bash
python3 "[PLUGIN_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```
*(If blocked by YouTube, ask user for cookies or a raw_transcript.json upload.)*

### Step 3: Sequential Chunk Loop
For each chunk, starting at `chunk_00.txt`:
1. **Read chunk**: `read C:/Users/peter/<workspace>/chunks/chunk_XX.txt`
2. **FGO / YGO Bootstrap**: Only if the chunk text contains `FGO`, `Fate`, `YGO`, or `遊戯王` — run the check for the matching game:
   - FGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - YGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
   - If exit code 1, re-run without `--check` to build it. Otherwise skip entirely.
3. **Generate timestamps**: Apply the Prompt Template rules below. Write them to memory.
4. **Write output**: Save to `C:/Users/peter/<workspace>/chunk_outputs/chunk_XX_output.md`
5. **Auto-resume**: Immediately proceed to `chunk_XX+1.txt`. Do NOT wait for user confirmation.
6. **Context Handoff**: If the model is slow or forgetting instructions, write `anibon_timestamper_state.json` inside the workspace and stop:
```json
{
  "video_id": "YOUR_YOUTUBE_VIDEO_ID",
  "video_url": "YOUR_YOUTUBE_VIDEO_URL",
  "workspace_path": "C:/Users/peter/youtube_<video_id>_workspace",
  "total_chunks": 48,
  "current_chunk": 12,
  "db_checked": { "fgo": true, "ygo": false },
  "phase": "chunk_loop",
  "last_updated": "2026-06-29T09:23:00Z"
}
```

---

#### 📄 Chunk TXT Format
```
CHUNK NN | HH:MM:SS–HH:MM:SS | cutoff=HH:MM:SS
(HH:MM:SS) transcript line text
...
```
**Cutoff rule**: Skip any line whose timestamp > the cutoff shown in the header.

---

#### 📄 Prompt Template Rules

- Use the `(HH:MM:SS)` timestamps directly from the file. Do NOT recalculate.
- Skip any entry whose timestamp > chunk cutoff.
- **Max 10 timestamps per chunk.**
- **Grouping**: Multiple lines within 1-2 minutes on the SAME topic → emit ONE timestamp at the start.
- **Tag changes reset the gap rule.** Use the first timestamp of each new tag, regardless of proximity to the previous one.
- **TAGS (use exactly these, no others)**:
  - `[Greeting]`: Hello/goodbye, thanking subs/members/donations.
  - `[Talk]`: General chatting, life updates, Q&A.
  - `[News]`: Reading or analyzing news, dramas, or patch notes.
  - `[Gameplay]`: Playing games, story quests, farming.
  - `[Gacha]`: Rolling/pulling in gacha games.
  - `[Boss]`: Fighting a major boss.
  - `[WatchParty]`: Reacting to official streams or trailers.
  - `[Reaction]`: Sudden strong reactions (laughing, jumpscared).
- **When unsure between [Talk] and [News]**: If she is *reading or quoting* a source → `[News]`. If she is *commenting or chatting* → `[Talk]`. Pick and move on.
- **Description**: State what was actually discussed (e.g. `บ๊อตอธิบาย MOU 43-44`). No internal feelings.
- If no events found: output exactly → `HH:MM:SS - [Talk] (ไม่มีเหตุการณ์สำคัญ)`

---

#### 📋 Output Format
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->
00:00:12 - [Greeting] บ๊อตทักทายผู้ชม เริ่มสตรีม
00:01:34 - [Talk] คุยเรื่องข่าวสาร
00:03:45 - [Gacha] ดึงการ์ด FGO รอบแรก
```
- First line is the HTML comment header — required for merge.
- No thinking, apologies, or meta-commentary in this file.

---

#### ⚠️ Timing Edge Cases (check only if gap > 10 min or timestamps seem wrong)
- If transcript text doesn't match expected content: trust `item.start` — it comes from YouTube's caption file.
- If two consecutive timestamps are >10 minutes apart with nothing in between: leave a note `[GAP: no transcript data]`. Do NOT invent a timestamp.

---

### Step 4: Assembly
When all chunks are done:
```bash
cat chunk_outputs/chunk_*_output.md > raw_timestamps.txt
```

Assemble `timestamp_VIDEO_ID.md`. Split into sections by major topic shift. If any section exceeds **50 lines**, split it into Part 1, Part 2, etc.

For each section header, write one line:
```
📌 ส่วนที่ N: [1-2 sentence summary of what happened]
(หัวข้อ: [short title] | ⏱ เริ่ม: HH:MM:SS)
---------------------------------------------------------
```
Use the timestamp of the VERY FIRST event in the section. Remove all `<!-- chunk_XX -->` markers.

### Step 5: Verification
```bash
python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/check_sections.py" timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️).
