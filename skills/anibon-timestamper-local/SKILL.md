---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon Official streams on a local LLM (Ollama, Gemma, Qwen) on any OS — when cloud context window is unavailable or too costly.
---

# Anibon Timestamper (Local LLM Edition)

Optimized for local LLMs with limited context windows (Gemma 4, Qwen 2.5, etc.).
Sequential chunk loop — no parallel subagents, no cloud.

---

## 🧠 Goldfish Brain Rules (CRITICAL)

**Violating the letter of these rules is violating the spirit of these rules.**

### Red Flags — STOP and Call a Tool
If you catch yourself doing any of the following, STOP GENERATING TEXT AND CALL A TOOL:
- Generating "Wait", "Actually", or "Hold on" (infinite reasoning loop).
- Thinking "I will do both chunks now to be efficient."
- Thinking "I don't remember the prompt format, I'll just guess."
- Running `ls` to check if a file exists.
- Outputting generated timestamps directly into chat instead of calling the write tool.

### Anti-Rationalization Table
| Your Excuse | The Reality |
|---|---|
| "I'll do chunks 18 and 19 in one turn" | You will crash. **ONE chunk per turn. No exceptions.** |
| "I need to check the folder first" | Curiosity wastes context. Blindly use the paths provided. |
| "I'll narrate my tool call" | No dry-running. If you say "I will read", CALL the tool. |
| "I'll output everything to be safe" | MAX 10 lines per chunk. Summarize. Period. |
| "I successfully generated the markdown" | Did you call the write tool? If not, you failed. NEVER skip the write call. |
| "I must continue reading the next chunk" | NO. Stop after state update. Wait for user prompt. |
| "I'll update state at the end of the batch" | No. Update state after EACH chunk. No batching ever. |

### Core Constraints
1. **One tool per turn**: Never batch tool calls across chunks.
2. **Process inline**: Read `.txt`, write timestamps yourself. No subagents.
3. **No `<think>` tags**: Never wrap reasoning in `<think>`.
4. **Handoff trigger**: User says "handoff", "stuck", or "context > 10%" → IMMEDIATELY write state file and halt.

---

## 🗺️ Plugin Directory Map (Do NOT use `ls`)

You already know where everything is. Resolve `[PLUGIN_ROOT]` in Step 0.

- **Scripts**: `[PLUGIN_ROOT]/scripts/prepare_video.py`
- **DB + Check Scripts**: `[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/`
  - `fetch_fgo_db.py`, `fetch_ygo_db.py`, `check_sections.py`, `assemble_timestamps.py`
- **Workspace**: `[WORKSPACE]` — set in Step 0
  - `[WORKSPACE]/chunks/chunk_XX.txt`
  - `[WORKSPACE]/chunk_outputs/chunk_XX_output.md`
  - `[WORKSPACE]/parts.json`
  - `[WORKSPACE]/anibon_timestamps.md`
  - `[WORKSPACE]/anibon_timestamper_state.json`

---

## 🧭 Steps

> [!IMPORTANT]
> **REQUIRED SUB-SKILL (FIRST):** Run `preparing-tools` to verify `yt-dlp`, `python3`, `sqlite3`. Do NOT proceed if any tool is missing.

### Step 0: Resolve Plugin Root & Workspace (Cross-Platform)

**Find `[PLUGIN_ROOT]`**: Look at the `<skill location="...">` tag at the top of your prompt.
- Strip the suffix `skills/anibon-timestamper-local/SKILL.md` (or with backslashes `\` on Windows).
- Replace all `\` with `/`. The result is `[PLUGIN_ROOT]`.

🚨 **ANTI-TYPO**: Plugin repo = `anibon-stream-synthesis` (HYPHENS). Skill folder = `anibon-timestamper` (HYPHENS). NEVER use underscores. Copy paths directly; do not retype from memory.

**Verify Python**:

Mac/Linux:
```bash
uname -a && python3 --version
```
Windows (PowerShell):
```powershell
python --version
```

**Set `[WORKSPACE]`**: Unless user specifies a path, default to:
- Mac/Linux: `~/youtube_<video_id>_workspace`
- Windows: Use forward slashes — `C:/Users/<username>/youtube_<video_id>_workspace`

### Step 1: Initialization

1. **Ask output language**: "What language for the timestamps? (e.g. Thai, English)" — do NOT proceed to timestamp generation until confirmed.
2. **Channel ownership check**: Run:
   ```bash
   yt-dlp --print uploader,upload_date "VIDEO_URL"
   ```
   Verify uploader matches one of: `Phuboat`, `ปู่โบ๊ต`, `โบ๊ต`, `Boat`, `ANIBON`. If no match — do NOT call the speaker "Boat".
3. **Royal/political content**: If transcript mentions Thai royalty, royal succession, or sensitive political topics → use metaphor-based masking.
   **REQUIRED SUB-SKILL:** `masking-royal-news`

### Step 2: Download & Chunk

Mac/Linux:
```bash
python3 "[PLUGIN_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```
Windows (PowerShell):
```powershell
python "[PLUGIN_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```

> **Local LLM Note**: Always use `--format txt`. Do NOT use `--vision` — local models cannot process images.

*(If blocked by YouTube, ask user for cookies file or `raw_transcript.json`. If subtitles/captions are completely missing, transcribe the audio locally using `whisper.cpp` as detailed in [BUILD_GPU.md](../anibon-timestamper/BUILD_GPU.md).)*

### Step 3: Sequential Chunk Loop

Process `chunk_00.txt`, `chunk_01.txt`, ... one at a time.

> **CRITICAL**: Chunk numbers are ALWAYS zero-padded to two digits (`chunk_02.txt`, NOT `chunk_2.txt`).

For each chunk:

1. **Read**: `[WORKSPACE]/chunks/chunk_XX.txt`
2. **DB check** — ONLY if chunk text contains `FGO`, `Fate`, `YGO`, or `遊戯王`:
   - `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
   - Exit code 1 → re-run without `--check` to build DB. Exit code 0 → skip.
3. **Generate timestamps**: follow the Prompt Template below. **DO NOT output the markdown into chat.**
4. **Write** to `[WORKSPACE]/chunk_outputs/chunk_XX_output.md` using the write tool.
5. **Update State (CRITICAL)**: IMMEDIATELY overwrite `[WORKSPACE]/anibon_timestamper_state.json`. Set `"current_chunk"` to XX+1. Do this after EVERY chunk.
6. **End Turn (CRITICAL)**: Stop immediately after state update. Output `[CHUNK COMPLETE. READY FOR NEXT.]` and wait for the user to prompt you.
7. **Handoff** — if overwhelmed, write state file and stop:

```json
{
  "video_id": "VIDEO_ID",
  "video_url": "VIDEO_URL",
  "workspace_path": "/absolute/path/to/youtube_VIDEO_ID_workspace",
  "total_chunks": 48,
  "current_chunk": 12,
  "db_checked": { "fgo": true, "ygo": false },
  "phase": "chunk_loop",
  "last_updated": "2026-07-17T09:23:00Z"
}
```

> **CRITICAL NOTE on `current_chunk`**: Set it to the NEXT chunk to process, NOT the one you just finished. If you finished `chunk_11`, write `"current_chunk": 12`.

---

### 📄 Prompt Template

Read the chunk. Group consecutive lines that discuss the **same topic** into one block. Write a **short header title** (in the output language confirmed in Step 1), then list timestamps below.

**Rules:**
- **SUMMARIZE, DO NOT TRANSCRIBE.** Combine multiple dialogue lines into one summary sentence.
- **MAX 10 LINES** per chunk. Outputting 30 lines = failure.
- Use `HH:MM:SS` directly from the file. Do NOT recalculate timestamps.
- Skip any line whose timestamp > the cutoff in the chunk header.
- Same topic within 1–2 minutes → one block, one header.
- New topic → new header. That is the only decision you need to make.
- Description: what was actually said/done (in chosen language). No internal feelings.
- If nothing notable: one line → `HH:MM:SS ไม่มีเหตุการณ์สำคัญ`

**Output format for each chunk file:**
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->

### ทักทาย
00:03:52 -  บ๊อตทักทายผู้ชม เริ่มสตรีม
00:04:01 -  พูดถึงช่วงเว้นว่างจากข่าวการเมือง

### หัวข้อถัดไป
HH:MM:SS -  description
```

- First line: HTML comment (required for assembly merge).
- `### Title` on its own line before each topic block.
- `HH:MM:SS -  description` — timestamp, dash, TWO spaces, text.
- No meta-commentary or apologies in the output file.

**Edge cases:**
- Trust `item.start` from the file — timestamps come from YouTube captions.
- Gap > 10 min with no transcript data → write `HH:MM:SS [GAP: no transcript data]`

---

### Step 4: Assembly

Concatenate all chunk outputs:

Mac/Linux:
```bash
cat "[WORKSPACE]/chunk_outputs/chunk_"*"_output.md" > "[WORKSPACE]/raw_timestamps.txt"
```
Windows (PowerShell):
```powershell
Get-Content (Get-Item "[WORKSPACE]/chunk_outputs/chunk_*_output.md" | Sort-Object Name) | Set-Content "[WORKSPACE]/raw_timestamps.txt"
```

Build `[WORKSPACE]/parts.json` from `raw_timestamps.txt` — one entry per section:
```json
[
  {
    "title": "ทักทาย",
    "start": "00:03:52",
    "body": "00:03:52 -  บ๊อตทักทายผู้ชม เริ่มสตรีม\n00:04:01 -  พูดถึงช่วงเว้นว่างจากข่าวการเมือง"
  }
]
```

Then run the assembler:
```bash
python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/assemble_timestamps.py" "[WORKSPACE]/parts.json"
```
Output: `[WORKSPACE]/anibon_timestamps.md`

If any section exceeds **15 timestamp lines**, split it into Part 1 / Part 2 in `parts.json`, then re-run the assembler.

### Step 5: Verify
```bash
python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/check_sections.py" "[WORKSPACE]/anibon_timestamps.md"
```
Any ❌ or ⚠️ → fix `parts.json` → re-run `assemble_timestamps.py` → re-verify. Do not proceed until all sections pass.

---

## Iron Rules (Local Edition)

- **ONE chunk per turn**: No batch processing. Ever.
- **Write tool, not chat**: Never paste markdown into the conversation.
- **State after every chunk**: If you crash, state file is your recovery.
- **No `ls`**: You know the paths. Use them.
- **No vision**: Local models use `--format txt`, not `--vision`.
- **Handoff over crash**: If context > 10%, save state and hand off. Do not power through.
