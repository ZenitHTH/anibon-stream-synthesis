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

---

## 🧭 Step-by-Step Guide

### Step 1: Verify Environment
Verify shell and tools before downloading:
- Run: `uname -a` (Unix) OR `$PSVersionTable` (Windows)
- Run: `command -v yt-dlp` (Unix) OR `Get-Command yt-dlp` (Windows)

### Step 2: Download & Chunk Transcript
Find the `prepare_video.py` script:
```bash
find . -name "prepare_video.py"
```
Run it to fetch and chunk the transcript (5-min blocks, 30s overlap):
```bash
python3 scripts/prepare_video.py "VIDEO_URL"
```
*(If blocked by YouTube, ask user for cookies permission or to upload raw_transcript.json).*

### Step 3: Sequential Chunk Loop
Process `chunk_00.json`, then `chunk_01.json` sequentially. For each chunk:
1. **Pre-read sub-skills**: Check chunk signals (gacha, talk, gameplay, tokusatsu) and load matching sub-skills.
2. **FGO / YGO Bootstrap**: If game matches, run `--check` and build the SQLite database if missing (exit 1).
3. **Spawn 1 Subagent**: Send the chunk text to a single subagent using the template below.
4. **Write Output**: Save subagent timestamps to `chunk_XX_output.md` (never append to one file!).
5. **Auto-resume**: Upon receiving the subagent response, immediately write the file and spawn the next subagent for `chunk_XX+1.json`. Do NOT wait for user confirmation.

**Subagent Template:**
```
You are processing Chunk <N> (MM:SS - MM:SS).
Step 1: Scan transcript for game actions, news, or gacha pulls.
Step 2: Align events to timestamps in format HH:MM:SS.
Step 3: Select tag: [Greeting] [Talk] [News] [Gameplay] [Gacha] [Boss] [WatchParty] [Reaction].
Step 4: Write summary description in Thai (use FGO/YGO DB terms).
Step 5: Output ONLY: "HH:MM:SS - [Tag] Description" (No other text).
TRANSCRIPT: <insert chunk raw text>
```

### Step 4: Topic Map & Assembly
When all chunks are finished, concatenate them:
- Unix: `cat chunk_*_output.md > raw_timestamps.txt`
- Windows: `Get-Content chunk_*_output.md | Set-Content raw_timestamps.txt`

Review the output to map major topic shifts (Talk, Gameplay, WatchParty) and split the file into parts of **4,500 characters or fewer** (YouTube comment limit is 5,000). Use the separator format:
```
═══════════════════════════════════════════════════════════
📌 ส่วนที่ N — [ชื่อหัวข้อ]
   ⏱ เริ่ม: HH:MM:SS  |  เนื้อหา: [สรุปสั้นๆ]
═══════════════════════════════════════════════════════════
```

### Step 5: Verification Check
Run `check_sections.py` on the final file to verify character counts and splits:
```bash
python3 scripts/check_sections.py timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️). Register the final file in your workspace.
