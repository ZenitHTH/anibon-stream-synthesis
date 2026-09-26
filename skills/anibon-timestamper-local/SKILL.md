---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon Official streams on a local LLM via LM Studio (default), llama-server, or Ollama on any OS — when cloud context window is unavailable or too costly.
---

# Anibon Timestamper (Local LLM Edition)

## Overview & Triggers

Optimized for local LLMs with limited context windows running sequential chunk loops (no parallel subagents, $0 cloud cost).

> [!IMPORTANT]
> **Supported Backends (LM Studio is Default)**:
> - **LM Studio**: Default endpoint `http://127.0.0.1:1234/v1/chat/completions`. Natively supported out of the box with zero extra setup.
> - **llama-server / llama.cpp**: Compatible with standard OpenAI API flags.
> - **Ollama**: Supported via OpenAI-compatible endpoint `http://127.0.0.1:11434/v1/chat/completions`.
>
> **Model Selection Baseline (12B Recommended)**:
> Use **12B-tier models** (e.g. `google/gemma-4-12b-qat` or `qwen/qwen3.5-9b-q6` / `14b`).
> **Avoid 4B models (`gemma-4-e4b`)** for full transcript timestamping: 4B lacks the parameter density to comprehend Thai livestream subculture, viewer banter, and donation reads, often misclassifying topics or hallucinating proper nouns. 12B fits comfortably in 16GB VRAM (e.g. Tesla P100 @ ~7.2 GB) with ample headroom for 8k–16k context.

---

## 🧠 Goldfish Brain Rules (CRITICAL)

**Violating the letter of these rules is violating the spirit of these rules.**

### Red Flags — STOP and Call a Tool
If you catch yourself doing any of the following, STOP GENERATING TEXT AND CALL A TOOL:
- Generating "Wait", "Actually", or "Hold on" (infinite reasoning loop).
- Thinking "This skill does not support LM Studio" (ABORT. LM Studio IS the primary default backend via port 1234).
- Thinking "I will run prepare_video.py with a relative path" (ABORT. Use the full absolute path from Step 0).
- Thinking "I will download the video file with yt-dlp" (ABORT. NEVER download video MP4/MKV. Run `prepare_video.py` which only downloads subtitles).
- Thinking "I will fetch the YouTube page using fetch_web_content or curl." (ABORT. YouTube blocks web scrapers. Use `prepare_video.py` in shell).
- Thinking "I will ask the user for a sample transcript." (ABORT. Run `prepare_video.py` via shell tool).
- Thinking "I will do both chunks now to be efficient."
- Thinking "I don't remember the prompt format, I'll just guess."
- Running `ls` to check if a file exists.
- Outputting generated timestamps directly into chat instead of calling the write tool.

### Anti-Rationalization Table
| Your Excuse | The Reality |
|---|---|
| "Skill only works with Ollama, not LM Studio" | **FALSE**. LM Studio is the primary default backend at `http://127.0.0.1:1234/v1/chat/completions`. |
| "I'll run python prepare_video.py directly" | **FAIL**. Script is not in CWD. You MUST use absolute path `[SKILL_ROOT]/scripts/prepare_video.py`. |
| "I'll download the video with yt-dlp" | **NEVER**. Only subtitles are needed. Run `prepare_video.py` (passes `--skip-download`). |
| "Workspace already has chunks, I'll re-download" | **SKIP**. If `[WORKSPACE]/chunks/` exists, proceed straight to Step 3. |
| "I'll fetch YouTube via fetch_web_content/curl" | **FAIL**. YouTube blocks raw scrapers. ALWAYS run `prepare_video.py` via terminal tool. |
| "Captions failed, I'll ask for sample transcript" | **NO**. Did you actually run `prepare_video.py` in shell? Run it. yt-dlp gets it. |
| "I'll create workspace in my current directory" | **NO**. Workspace is ALWAYS `C:/Users/<username>/youtube_<id>_workspace` (absolute path). |
| "I'll do chunks 18 and 19 in one turn" | You will crash. **ONE chunk per turn. No exceptions.** |
| "I need to check the folder first" | Curiosity wastes context. Blindly use the paths provided. |
| "I'll narrate my tool call" | No dry-running. If you say "I will read", CALL the tool. |
| "I'll output everything to be safe" | MAX 10 lines per chunk. Summarize. Period. |
| "I successfully generated the markdown" | Did you call the write tool? If not, you failed. NEVER skip the write call. |
| "I must continue reading the next chunk" | NO. Stop after state update. Wait for user prompt. |
| "I'll update state at the end of the batch" | No. Update state after EACH chunk. No batching ever. |
| "I'll remember all previous transcripts in chat" | NO. Treat each chunk like an isolated subagent. Forget past chunk texts. |
| "I'll use 'auto continue' in Cline for all 30 chunks" | **TIMEOUT TRAP**. 30 chunks in one chat = 120k tokens. P100 takes 7 min to prefill $\to$ Cline HTTP client times out. Use Option A script. |

### Core Constraints
1. **Shell execution only for download**: NEVER use web fetch / curl / browser tools on YouTube URLs. Run `prepare_video.py` via shell (`run_commands` / `run_command`).
2. **Subagent-style context isolation (CRITICAL)**: Treat each chunk like an ephemeral subagent worker. Read ONLY current `chunk_XX.txt` and previous stamp tail from `anibon_timestamper_state.json`. NEVER carry over or summarize previous chunks' raw transcripts in conversation context.
3. **Context bloat cap (Max 15k tokens)**: If agent conversation history exceeds 15k tokens (or after every 5 chunks in interactive chat), write state, halt, and ask user to clear/compact context or open a fresh chat.
4. **One tool per turn**: Never batch tool calls across chunks.
5. **Process inline**: Read `.txt`, write timestamps yourself. No subagents.
6. **No `<think>` tags**: Never wrap reasoning in `<think>`.
7. **Handoff trigger**: User says "handoff", "stuck", or context > 15k tokens $\to$ IMMEDIATELY write state file and halt.

### 🚨 The "Operation Timed Out" Death Loop (CRITICAL)

If you see `The operation timed out.` in your chat session:
- **WHY IT HAPPENS**: The chat history accumulated past chunk transcripts and exceeded 30k–120k tokens. On a local GPU (e.g. Tesla P100), prompt evaluation for 100k tokens takes >7 minutes. The IDE's HTTP client (Cline/Roo) aborts after 4 minutes.
- **NEVER CLICK "AUTO CONTINUE"**: Retrying in a bloated chat session sends the same 120k tokens again and will **TIMEOUT 100% OF THE TIME**.
- **MANDATORY RECOVERY**:
  1. Abandon or reset the bloated chat session immediately.
  2. Do NOT run chunk loops inside conversational chat turns.
  3. Run the Option A CLI runner (`process_chunks_local.py`) via terminal command.
     - `process_chunks_local.py` runs outside chat context, sending only ~1,500 tokens per chunk.
     - Prompt prefill takes **<1 second**, zero timeouts, and resumes automatically from existing chunk outputs.

---

## 🗺️ Plugin Directory Map (Do NOT use `ls`)

You already know where everything is. Resolve `[SKILL_ROOT]` in Step 0.

- **Scripts**: `[SKILL_ROOT]/scripts/prepare_video.py`
- **DB + Check Scripts**: `[SKILL_ROOT]/scripts/`
  - `fetch_fgo_db.py`, `fetch_ygo_db.py`, `check_sections.py`, `pack_timestamps.py`
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

**Find `[SKILL_ROOT]`**:
1. If `<skill location="...">` tag exists in prompt: strip `SKILL.md`, replace `\` with `/`.
2. **Canonical fallbacks by environment**:
   - **`.agents` format (Cline / Roo / Claude Code / Cursor / `npx skills`)**:
     - Global: `~/.agents/skills/anibon-timestamper-local` (Windows: `C:/Users/<username>/.agents/skills/anibon-timestamper-local`)
     - Project: `<project_root>/.agents/skills/anibon-timestamper-local`
   - **`.gemini` plugin format (Google Antigravity)**:
     - Global: `~/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local` (Windows: `C:/Users/<username>/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local`)

🚨 **ANTI-TYPO**: Skill folder = `anibon-timestamper-local` (HYPHENS). NEVER use underscores. Copy paths directly; do not retype from memory.

**Verify Python**:

Mac/Linux:
```bash
uname -a && python3 --version
```
Windows (PowerShell):
```powershell
python --version
```

**Set `[WORKSPACE]`**:
- **Default (Standard Global)**:
  - Mac/Linux: `~/youtube_<video_id>_workspace`
  - Windows: Use forward slashes — `C:/Users/<username>/youtube_<video_id>_workspace`
- **When running inside a project in `.agents` format**:
  You can set `[WORKSPACE]` to an absolute path or pass `--workspace "[WORKSPACE]"` to `prepare_video.py`.
- ⚠️ **FORBIDDEN**: NEVER create workspace inside agent's temporary chat session directory (e.g. `.cline/...` is strictly prohibited).

### Step 1: Initialization

1. **Ask output language**: "What language for the timestamps? (e.g. Thai, English)" — do NOT proceed to timestamp generation until confirmed.
2. **Channel ownership check**: Run:
   ```bash
   yt-dlp --print uploader,upload_date "VIDEO_URL"
   ```
   Verify uploader matches one of: `Phuboat`, `ปู่โบ๊ต`, `โบ๊ต`, `Boat`, `ANIBON`. If no match — do NOT call the speaker "Boat".
3. **Royal/political content**: If transcript mentions Thai royalty, royal succession, or sensitive political topics → use metaphor-based masking.
   **REQUIRED SUB-SKILL:** `masking-royal-news`

### Step 2: Download & Chunk (Terminal Shell ONLY)

> ⚡ **CHECK EXISTING WORKSPACE FIRST**:
> If `[WORKSPACE]/chunks/chunk_00.txt` already exists, **SKIP STEP 2 COMPLETELY**. Proceed directly to Step 3. Do not re-download.

> 🚨 **ABSOLUTE RULE — NO WEB SCRAPERS & NO RAW VIDEO DOWNLOADS**:
> - NEVER use `fetch_web_content`, `read_url_content`, `curl`, or browser tools to fetch the YouTube URL. YouTube blocks raw web requests and will return generic HTML without subtitles.
> - NEVER run raw `yt-dlp "URL"` without `--skip-download` (do not download multi-gigabyte video files!).
> - ALWAYS execute `prepare_video.py` using its full absolute path `"[SKILL_ROOT]/scripts/prepare_video.py"` in shell via terminal execution (`run_commands` in Cline / `run_command` in Antigravity).

Mac/Linux:
```bash
python3 "[SKILL_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --workspace "[WORKSPACE]" --format txt --block 300 --overlap 30
```
Windows (PowerShell):
```powershell
python "[SKILL_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --workspace "[WORKSPACE]" --format txt --block 300 --overlap 30
```

**Ready-to-run copy-paste commands (PowerShell)**:
```powershell
# If using .agents format (Cline / Roo / Claude Code):
python "C:/Users/<username>/.agents/skills/anibon-timestamper-local/scripts/prepare_video.py" "VIDEO_URL" --workspace "C:/Users/<username>/youtube_<video_id>_workspace" --format txt --block 300 --overlap 30

# If using .gemini plugin format (Antigravity):
python "C:/Users/<username>/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/prepare_video.py" "VIDEO_URL" --workspace "C:/Users/<username>/youtube_<video_id>_workspace" --format txt --block 300 --overlap 30
```

> **Local LLM Note**: Always use `--format txt`. Do NOT use `--vision` — local models cannot process images.

*(If blocked by YouTube, ask user for cookies file or `raw_transcript.json`. If subtitles/captions are completely missing, transcribe the audio locally using `whisper.cpp` as detailed in [BUILD_WHISPERCPP_GUILD.md](../anibon-timestamper/references/BUILD_WHISPERCPP_GUILD.md).)*

### Step 3: Sequential Chunk Loop

#### Option A: Automated CLI Runner (Recommended via LM Studio / P100)
Run the decoupled runner to process all chunks sequentially, handle continuity, and write `all_timestamps.txt`:

Mac/Linux:
```bash
python3 -X utf8 "[SKILL_ROOT]/scripts/process_chunks_local.py" "[WORKSPACE]" \
    --model "google/gemma-4-12b-qat" --lang th
```
Windows (PowerShell):
```powershell
python -X utf8 "[SKILL_ROOT]/scripts/process_chunks_local.py" "[WORKSPACE]" `
    --model "google/gemma-4-12b-qat" --lang th
```

**Ready-to-run copy-paste commands (PowerShell)**:
```powershell
# If using .agents format (Cline / Roo / Claude Code):
python -X utf8 "C:/Users/<username>/.agents/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "C:/Users/<username>/youtube_<video_id>_workspace" --model "google/gemma-4-12b-qat" --lang th

# If using .gemini plugin format (Antigravity):
python -X utf8 "C:/Users/<username>/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "C:/Users/<username>/youtube_<video_id>_workspace" --model "google/gemma-4-12b-qat" --lang th
```

Flags:
- `--endpoint`: defaults to `http://127.0.0.1:1234/v1/chat/completions`
- `--model`: defaults to `google/gemma-4-12b-qat`
- `--lang`: `th` (Thai, default) or `en` (English)
- `--max-tokens`: per-call budget (default 800; set 1200+ for reasoning models)
- `--temperature`: sampling temperature (default 0.1)
- `--block-size`: seconds per YouTube comment part (default 5400 = 90 min)
- `--no-resume`: force overwrite already processed chunks
- `--dry-run`: check chunk discovery without calling model

> **Output contract (matches front-tier):** 1 timestamp per chunk by default, 2 MAX, 0 (CONTINUATION) allowed. Tags used: `[Greeting]` `[Talk]` `[News]` `[Chat]` `[Donation]` `[Gameplay]` `[Gacha]` `[Boss]` `[Death]` `[Victory]` `[WatchParty]` `[Reaction]`. Descriptions max 12 words in output language.

> **Reasoning model token trap:** If using `gemma-4-12b-qat` or other thinking models, set `--max-tokens 1200`. Script auto-extracts from `reasoning_content` if `content` is empty.

#### Option B: Manual Inline Chunk Processing (Interactive)
Process `chunk_00.txt`, `chunk_01.txt`, ... one at a time.

> **CRITICAL**: Chunk numbers are ALWAYS zero-padded to two digits (`chunk_02.txt`, NOT `chunk_2.txt`).
>
> ⚠️ **AUTO-CONTINUE / CLINE TIMEOUT WARNING**:
> Never let an interactive agent (Cline, Claude Code) loop all 30 chunks inside one long chat thread with "auto continue". Chat history retains every read chunk, bloating to >100k tokens. Local GPUs (Tesla P100) will take >6 minutes to evaluate the prompt, triggering HTTP timeout (`The operation timed out`).
> **Rule**: Treat each chunk like an isolated subagent worker. Do NOT remember or re-quote past transcripts. If context > 15k tokens, halt and clear context or switch to Option A runner.

For each chunk:

1. **Read**: `[WORKSPACE]/chunks/chunk_XX.txt` ONLY. Do NOT re-read or hold previous chunks in memory.
2. **Topic detection** — keyword-scan chunk text for game/royal/tokusatsu signals:
   ```bash
   grep -iE "FGO|Fate|Arknights|ไรเดอร์|Rider|เซนไต|Sentai|royal|imu|112" "[WORKSPACE]/chunks/chunk_XX.txt"
   ```
   Use grep for speed; only install `detect_signals.py` pipeline for bulk analysis.
3. **DB check** — ONLY if topic scan shows game keywords (`FGO`, `Fate`, `YGO`, `遊戯王`):
   - `python3 "[SKILL_ROOT]/scripts/fetch_fgo_db.py" --check`
   - `python3 "[SKILL_ROOT]/scripts/fetch_ygo_db.py" --check`
   - Exit code 1 → re-run without `--check` to build DB. Exit code 0 → skip.
4. **Generate timestamps**: follow the Prompt Template below. **DO NOT output the markdown into chat.**
5. **Write** to `[WORKSPACE]/chunk_outputs/chunk_XX_output.md` using the write tool.
6. **Update State (CRITICAL)**: IMMEDIATELY overwrite `[WORKSPACE]/anibon_timestamper_state.json`. Set `"current_chunk"` to XX+1 and update `"prev_tail"` to the last generated timestamp line. Do this after EVERY chunk.
7. **End Turn (CRITICAL)**: Stop immediately after state update. Output `[CHUNK COMPLETE. READY FOR NEXT.]` and wait for the user to prompt you.
8. **Context Purge**: Discard the chunk text from working memory. Do not carry it to next turn.
9. **Handoff / Clear Context**: If conversation context exceeds 15k tokens (or every 5 chunks in Cline), write state and halt:

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

### 📄 Prompt Template (front-tier quality)

> **Option A handles this automatically.** Use this section only for Option B (manual inline).

**Density contract (CRITICAL — same as front-tier cloud model):**
- 1 timestamp per chunk by default. **2 MAX. 0 allowed (output `CONTINUATION`).**
- New timestamp only when: game switches title, speaker joins/leaves, completely different activity, completely new topic.
- Same topic continuing from previous chunk → `CONTINUATION` (0 stamps).
- Multiple sub-topics within one talk → MERGE into 1 stamp.

**Tags (pick exactly one):**
`[Greeting]` `[Talk]` `[News]` `[Chat]` `[Donation]` `[Gameplay]` `[Gacha]` `[Boss]` `[Death]` `[Victory]` `[WatchParty]` `[Reaction]`

**Output format per chunk file:**
```
<!-- chunk_00 | 00:00:00 – 00:05:00 -->
HH:MM:SS - [Tag] Description in Thai max 12 words
```

Or if continuing:
```
<!-- chunk_00 | 00:00:00 – 00:05:00 | CONTINUATION -->
```

Rules:
- `HH:MM:SS` directly from the transcript. Do NOT recalculate.
- Description: Thai, max 12 words, one phrase, no quotes, no headers.
- No meta-commentary, no apologies, no prose in output file.

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

Then run the packer:
```bash
python3 "[SKILL_ROOT]/scripts/pack_timestamps.py" "[WORKSPACE]/timestamps.txt" --output "[WORKSPACE]/anibon_timestamps.md"
```
Output: `[WORKSPACE]/anibon_timestamps.md` + `[WORKSPACE]/timestamps_parts.json`

If any section exceeds **15 timestamp lines**, adjust `--byte-limit` or split the timestamp list, then re-run.

### Step 5: Verify
```bash
python3 "[SKILL_ROOT]/scripts/check_sections.py" "[WORKSPACE]/anibon_timestamps.md"
```
Any ❌ or ⚠️ → adjust `--byte-limit` or split timestamps → re-run `pack_timestamps.py` → re-verify. Do not proceed until all sections pass.

---

## Iron Rules (Local Edition)

- **ONE chunk per turn**: No batch processing. Ever.
- **Subagent-style isolation**: Never retain raw transcripts from past chunks in chat context. Memory belongs on disk (`chunk_outputs/` and `anibon_timestamper_state.json`), not in conversation tokens.
- **Anti-hoarding / Cline auto-continue guard**: Do NOT run 30 chunks in a single chat session with auto-continue. Context accumulates to >100k tokens $\to$ P100 prompt prefill exceeds 6 minutes $\to$ HTTP timeout error. Clear context every 5 chunks or run Option A CLI runner.
- **Write tool, not chat**: Never paste markdown into the conversation.
- **State after every chunk**: If you crash, state file is your recovery.
- **No `ls`**: You know the paths. Use them.
- **No vision**: Local models use `--format txt`, not `--vision`.
- **Handoff over crash**: If context > 15k tokens, save state and hand off/clear context. Do not power through.
- **Use grep for topic scan**: `detect_topics.py` deprecated/deleted. Use `grep -iE` on chunk text instead.

