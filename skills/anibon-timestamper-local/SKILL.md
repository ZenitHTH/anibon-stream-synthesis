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
4. **Delegate raw text**: Do NOT read raw transcript files in this main session. Spawn a subagent to do it.
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
python3 "/absolute/path/to/prepare_video.py" "VIDEO_URL"
```
*(If blocked by YouTube, ask user for cookies permission or to upload raw_transcript.json).*

### Step 3: Sequential Chunk Loop
Process `chunk_00.json`, then `chunk_01.json` sequentially. For each chunk:
1. **Pre-read sub-skills**: Check chunk signals (gacha, talk, gameplay, tokusatsu) and load matching sub-skills.
2. **FGO / YGO Bootstrap**: If game matches, run `--check` and build the SQLite database if missing (exit 1).
3. **Spawn 1 Subagent**: Send the chunk JSON content to a single subagent using the template below.
4. **Write Output**: Save subagent timestamps to `chunk_XX_output.md` using the output format below.
5. **Auto-resume**: Upon receiving the subagent response, immediately write the file and spawn the next subagent for `chunk_XX+1.json`. Do NOT wait for user confirmation.
6. **Context Handoff**: If you notice high latency or memory issues, write `anibon_timestamper_state.json` with the current chunk index, explain the handoff to the user, and stop (see `anibon-timestamper-handoff`).

---

#### 📦 Chunk JSON Schema
Each `chunk_XX.json` file contains:
```json
{
  "start_sec": 300,
  "end_sec":   600,
  "items": [
    { "text": "สวัสดีครับทุกคน", "start": 301.4, "duration": 2.1, "timestamp": "00:05:01" },
    { "text": "วันนี้มาเล่น FGO", "start": 305.8, "duration": 1.9, "timestamp": "00:05:05" }
  ]
}
```
- `start_sec` / `end_sec` — chunk window in **seconds from stream start**
- `items[].timestamp` — **pre-calculated HH:MM:SS** — use this directly!
- The last **30 seconds** of every chunk overlaps with the start of the next chunk (overlap zone)

---

#### ⏱️ Timing Rules

**Overlap cutoff:** Only emit timestamps for events with `item.start < end_sec - 30`. Ignore anything in the last 30 seconds of the chunk — the next chunk will cover it cleanly.

**Timing correction — when timestamps feel drifted:**
- If the transcript text at a given second doesn't match what you expect (e.g. text says "end screen" but timestamp is 00:05:10 into a 3-hour stream), **trust `item.start` over your intuition** — the timestamps come directly from YouTube's caption file and are authoritative.
- If two consecutive timestamps are more than **10 minutes apart** with no entries in between, check if you skipped items. Do NOT invent a timestamp to fill the gap — leave it empty and note `[GAP: no transcript data]`.
- If a tag event (e.g. gacha pull) clearly started earlier than the earliest item in your chunk, use `start_sec` as the floor — never go below it.

---

#### 📄 Subagent Template
Send the full JSON content of the chunk file to the subagent:
```
You are processing Chunk <N> (HH:MM:SS – HH:MM:SS).
chunk start_sec = <start_sec>, end_sec = <end_sec>, overlap cutoff = <end_sec - 30>

RULES:
- Use the pre-calculated `item.timestamp` directly. Do NOT calculate the math yourself.
- Only emit timestamps for items where item.start < <end_sec - 30> (skip overlap zone).
- One line per event. Format: HH:MM:SS - [Tag] Description (Thai).
- Tags: [Greeting] [Talk] [News] [Gameplay] [Gacha] [Boss] [WatchParty] [Reaction]
- Output ONLY the timestamp lines. No headers, no explanation, no extra text.
- If no events found: output exactly one line → HH:MM:SS - [Talk] (ไม่มีเหตุการณ์สำคัญ)

CHUNK JSON:
<paste full chunk_XX.json content here>
```

---

#### 📋 Output Format for `chunk_XX_output.md`
Each output file must follow this exact format so `cat` concatenation works cleanly:
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->
00:00:12 - [Greeting] บ๊อตทักทายผู้ชม เริ่มสตรีม
00:01:34 - [Talk] คุยเรื่องข่าวสาร
00:03:45 - [Gacha] ดึงการ์ด FGO รอบแรก
```
- **First line**: HTML comment with chunk index and time range — used as a merge marker
- **Body**: one `HH:MM:SS - [Tag] Description` line per event, chronological order
- **Never** include the subagent's thinking, apologies, or meta-commentary in this file

---

### Step 4: Topic Map & Assembly
When all chunks are finished, concatenate them:
- Unix: `cat chunk_*_output.md > raw_timestamps.txt`
- Windows: `Get-Content chunk_*_output.md | Set-Content raw_timestamps.txt`

Review the output to map major topic shifts (Talk, Gameplay, WatchParty) and split the file into parts of **4,500 characters or fewer** (YouTube comment limit is 5,000). 
**CRITICAL**: You MUST write a brief summary (1-2 sentences) of what actually happens in this section for the `เนื้อหา:` field in the separator. Do NOT just copy the title.

Use the separator format:
```
📌 ส่วนที่ N: [สรุปภาพรวมของช่วงนี้สั้นๆ 1-2 บรรทัด]
(หัวข้อ: [ชื่อหัวข้อ] | ⏱ เริ่ม: HH:MM:SS)
---------------------------------------------------------
```

### Step 5: Verification Check
Find and run `check_sections.py` on the final file to verify character counts:
```bash
# Find the script (use global find, same as Step 2)
CHECK_SCRIPT=$(find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name "check_sections.py" 2>/dev/null | head -1)
python3 "$CHECK_SCRIPT" timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️). Register the final file in your workspace.
