---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon streams on a LOCAL model (Ollama, gemma4, qwen). Focuses on step-by-step sequential looping, minimal context, and goldfish brain rules.
---

# 🎬 Anibon Timestamper (Local AI Edition)

Optimized for local LLMs with limited context windows (e.g. Gemma 4, Qwen 2.5).
Processes video transcripts in sequential chunks to preserve memory.

---

## 🧠 Goldfish Brain Rules (CRITICAL)
1. **ANTI-LOOP PROTOCOL (CRITICAL)**: If you catch yourself saying "Wait", "Actually", "Hold on", "Let's go", or "(No more thinking)", you are trapped in an infinite reasoning loop. You MUST IMMEDIATELY STOP GENERATING TEXT AND CALL A TOOL. Do NOT output a finalized plan. Do NOT say "Ready". Just call the tool.
2. **One chunk at a time**: Process exactly one `.txt` file per turn. Do not look ahead.
3. **One tool per turn**: Never run batch actions.
4. **Save and forget**: Write output for each chunk to a file, then forget it.
5. **Process inline**: Read the `.txt` file, write timestamps yourself. No subagents.
6. **No dry-running**: Every `read`, `write`, or `bash` MUST be a real tool call. If you cannot call a tool, output exactly: `[STUCK: cannot call tool, awaiting user input]` and stop.
7. **No `<think>` tags**: Never output or wrap your thinking process in `<think>` or `</think>`. Instead, write your thinking process directly as plain text.
8. **No Curiosity / No Exploration**: Do NOT run `ls`, `find`, or explore the filesystem. Do NOT ask clarifying questions. Do NOT try to learn about the environment. Just blindly execute the exact paths provided in these steps.
9. **Handoff early (1/9 capacity)**: If the context window reaches roughly 1/9 of its maximum capacity, IMMEDIATELY invoke the `anibon-timestamper-handoff` skill to handle saving state and resetting context. Do not try to do it yourself.
10. **Emergency Stop (Hang)**: If the user says "hang", "stuck", or "stop", IMMEDIATELY write the `anibon_timestamper_state.json` file to save progress and stop.
11. **Forward Slashes Only**: Always `C:/Users/peter/...`. Backslashes get stripped.

---

## 🗺️ Plugin Directory Map (Do NOT use `ls`)
You already know where everything is. Never search for files.
- **Main Scripts**: `[PLUGIN_ROOT]/scripts/prepare_video.py`
- **Sub-scripts**: `[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/` (`fetch_fgo_db.py`, `fetch_ygo_db.py`, `check_sections.py`)
- **Workspace**: `C:/Users/peter/youtube_<video_id>_workspace/`
  - `/chunks/chunk_XX.txt`
  - `/chunk_outputs/chunk_XX_output.md`
  - `/anibon_timestamper_state.json`

---

## 🧭 Steps

### Step 1: Resolve Plugin Path & Verify
Shell is MINGW64/bash. Run:
1. **Find Plugin Root**: Look at the `<skill location="...">` tag at the top of your prompt. Delete the exact text `skills\anibon-timestamper-local\SKILL.md` from the end of it. Replace all backslashes `\` with forward slashes `/`. This remaining path is your `[PLUGIN_ROOT]`.
   - 🚨 **ANTI-TYPO WARNING**: You (the AI) are prone to confusing hyphens (`-`) and underscores (`_`) when typing from memory. The repository is `anibon-stream-synthesis` (HYPHENS). The skill folder is `anibon-timestamper` (HYPHENS). NEVER use underscores for these! Copy the path directly, do not retype it.
2. **Verify**:
```bash
uname -a && python3 --version
```

### Step 2: Download & Chunk
```bash
python3 "[PLUGIN_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```
*(If blocked by YouTube, ask user for cookies or raw_transcript.json.)*

### Step 3: Sequential Chunk Loop
For each chunk `chunk_00.txt`, `chunk_01.txt`, ...:
**CRITICAL**: Chunk numbers are ALWAYS zero-padded to two digits (e.g. `chunk_02.txt`, NOT `chunk_2.txt`).
1. **Read**: `read C:/Users/peter/<workspace>/chunks/chunk_XX.txt`
2. **DB check** (only if chunk text contains `FGO`, `Fate`, `YGO`, or `遊戯王`):
   - FGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - YGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
   - Exit 1 → re-run without `--check` to build. Otherwise skip.
3. **Generate timestamps**: follow the Prompt Template below.
4. **Write**: save to `C:/Users/peter/<workspace>/chunk_outputs/chunk_XX_output.md`
5. **Auto-resume**: Immediately call the `read` tool for `chunk_XX+1.txt`. Do NOT ask the user for permission to continue. Just initiate the next chunk yourself to keep the loop going.
6. **Handoff** if overwhelmed — write state file:
```json
{
  "video_id": "VIDEO_ID",
  "video_url": "VIDEO_URL",
  "workspace_path": "C:/Users/peter/youtube_<video_id>_workspace",
  "total_chunks": 48,
  "current_chunk": 12,
  "db_checked": { "fgo": true, "ygo": false },
  "phase": "chunk_loop",
  "last_updated": "2026-06-29T09:23:00Z"
}
```

---

### 📄 Prompt Template

Read the chunk. Group consecutive lines that discuss the **same topic** into a block. Write a **short Thai header title** for each block, then list timestamps below it.

**Rules:**
- Use `(HH:MM:SS)` directly from the file. Do NOT recalculate.
- Skip any line whose timestamp > the cutoff in the chunk header.
- Max **10 timestamp lines** per chunk (headers don't count).
- Same topic within 1-2 minutes → one block, one header.
- New topic → new header. That's the only decision you need to make.
- Description: what was actually said/done (Thai). No internal feelings.
- If nothing notable: one line → `HH:MM:SS ไม่มีเหตุการณ์สำคัญ`

**Output format for each chunk file:**
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->

### ทักทาย
00:03:52 -  บ๊อตทักทายผู้ชม เริ่มสตรีม
00:04:01 -  พูดถึงช่วงเว้นว่างจากข่าวการเมืองในช่วง 3 สัปดาห์ที่ผ่านมา

### หัวข้อถัดไป
HH:MM:SS -  description
```

- First line: HTML comment (required for merge).
- `### Title` on its own line before each topic block. (This is a temporary header for grouping).
- `HH:MM:SS -  description` — timestamp, dash, two spaces, Thai text. No tags.
- No meta-commentary or apologies in this file.

**Edge cases (check only if gap > 10 min or timestamps seem wrong):**
- Trust `item.start` over your intuition — timestamps come from YouTube captions.
- Gap > 10 min with nothing in between → write `HH:MM:SS [GAP: no transcript data]`.

---

### Step 4: Assembly
```bash
cat chunk_outputs/chunk_*_output.md > raw_timestamps.txt
```

Assemble `timestamp_VIDEO_ID.md`. Read through `raw_timestamps.txt` and convert the temporary `### Title` blocks into the final format. 
If a section exceeds **15 timestamp lines** (Thai characters consume 3x bytes and hit YouTube limits faster), split it: duplicate the header as Part 1 / Part 2 and divide the lines between them.

For each section, use this exact format:
```
📌 ส่วนที่ N: [1 sentence summary of what happened in this section]
(หัวข้อ: [short title from the ### header] | ⏱ เริ่ม: HH:MM:SS)
-------
[timestamps here — e.g. 00:03:52 -  description]
```
- Use a running counter `N` across the whole file.
- `HH:MM:SS` in the header must be the timestamp of the VERY FIRST event in this section.
- Remove all `<!-- chunk_XX -->` markers and `###` headers.

### Step 5: Verify
```bash
python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/check_sections.py" timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️).
