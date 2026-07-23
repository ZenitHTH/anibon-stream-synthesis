---
name: anibon-timestamper-handoff
description: Save or load the progress state of a local timestamper session to prevent token context window exhaustion.
---

> [!WARNING]
> **Load order is critical.** This skill MUST be loaded *after* `anibon-timestamper-local`. Loading this skill first on a local model (Gemma, Qwen) will cause an immediate abort due to prefill budget exhaustion from the combined skill text size. Always load `anibon-timestamper-local` first, then load this skill.

# 🔄 Anibon Timestamper Handoff Protocol

When processing long video transcripts (>2 hours) on local models (Ollama/Gemma/Qwen), the conversation context window can overflow after processing several sequential chunks, causing the model to become slow, unresponsive, or forgetful.

Use this handoff protocol to save the session state, flush the context, and resume processing in a brand-new conversation session.

---

## 🗺️ Plugin Directory Map (Do NOT use `ls`)
You already know where everything is. Resolve `[SKILL_ROOT]` and `[WORKSPACE]` from the state file or from Step 0 of `anibon-timestamper-local`.
- **Main Scripts**: `[SKILL_ROOT]/scripts/prepare_video.py`
- **DB + Check Scripts**: `[SKILL_ROOT]/scripts/` (`fetch_fgo_db.py`, `fetch_ygo_db.py`, `check_sections.py`)
- **Workspace**: `[WORKSPACE]` — stored in state file as `workspace_path`
  - `[WORKSPACE]/chunks/chunk_XX.txt`
  - `[WORKSPACE]/chunk_outputs/chunk_XX_output.md`
  - `[WORKSPACE]/anibon_timestamper_state.json`

## ⚡ Strict Rules
- **No Curiosity / No Exploration**: Do NOT run `ls`, `find`, or explore the filesystem. Just blindly execute the paths. Do not list directory contents to "check progress".

---

## 💾 Saving Progress (When Context is Full)

If the local AI shows signs of context exhaustion (e.g. high latency, repetitive responses, forgetting instructions):

1. **Write State File**: Write `anibon_timestamper_state.json` to `[WORKSPACE]/anibon_timestamper_state.json`. Use the absolute path for `workspace_path` — no tildes or relative segments.
   
   **JSON Schema:**
   ```json
   {
     "video_id": "YOUR_YOUTUBE_VIDEO_ID",
     "video_url": "YOUR_YOUTUBE_VIDEO_URL",
     "workspace_path": "/absolute/path/to/youtube_VIDEO_ID_workspace",
     "total_chunks": 48,
     "current_chunk": 12,
     "db_checked": {
       "fgo": true,
       "ygo": false
     },
     "phase": "chunk_loop",
     "last_updated": "2026-07-17T09:23:00Z"
   }
   ```

   **CRITICAL NOTE ON `current_chunk`**: The value for `"current_chunk"` MUST be the exact integer of the **NEXT** chunk to be processed. If you just finished writing the output for `chunk_11`, you MUST set `"current_chunk": 12` so the next session knows to start at 12. Never set it to the chunk you already finished.

2. **Automated Handoff Action**: Output a message explaining that context is full, pointing to the state file. Then, **clear your context** and **call yourself** to load the state and resume work automatically. Do NOT wait for the user to restart the session!
   
   *Example message:*
   > 🔄 [CONTEXT WARNING] My active memory window is reaching 1/9 capacity. I have saved the progress state to `/absolute/path/to/youtube_rP8AHWOIXtI_workspace/anibon_timestamper_state.json`. Clearing context and calling myself to resume from Chunk 12 automatically...

---

## 📂 Loading Progress (In a New Session)

When the user starts a fresh conversation session to resume work:

> [!IMPORTANT]
> **CRITICAL OVERRIDE**: Even if the user asks you to do a specific custom task immediately (e.g. "redo chunk-14", "skip to chunk 16"), you MUST complete Step 1 and Step 2 below FIRST to get your formatting rules. NEVER try to guess the markdown format or file paths from memory.

1. **Resolve Plugin Path**: Look at the `<skill location="...">` XML tag at the top of your instructions. Strip the filename `SKILL.md` (or with backslashes `\` on Windows). Replace all `\` with `/`. Result is `[SKILL_ROOT]`.
   - 🚨 **ANTI-TYPO**: Plugin repo = `anibon-stream-synthesis` (HYPHENS). Skill folder = `anibon-timestamper` (HYPHENS). Copy paths directly; never retype from memory.
2. **Read Local Rules**: MUST read `[SKILL_ROOT]/../anibon-timestamper-local/SKILL.md` using the read tool. You need its output format and constraints.
3. **Read State File**: The user should tell you the workspace path, or ask them. The state file is at `[WORKSPACE]/anibon_timestamper_state.json` where `[WORKSPACE]` = the `workspace_path` value stored in that file. Read it directly. Do NOT run `ls` or search.
4. **Verify Databases**: Even if `db_checked` says `true`, verify:
   - FGO Check: `python3 "[SKILL_ROOT]/scripts/fetch_fgo_db.py" --check`
   - FGO Build (if exit 1): `python3 "[SKILL_ROOT]/scripts/fetch_fgo_db.py"`
   - YGO Check: `python3 "[SKILL_ROOT]/scripts/fetch_ygo_db.py" --check`
   - YGO Build (if exit 1): `python3 "[SKILL_ROOT]/scripts/fetch_ygo_db.py"`
5. **Resume Step 3 (Loop)**: Go directly to the chunk number in `"current_chunk"`. Zero-pad to two digits (`chunk_02.txt` not `chunk_2.txt`).
6. **Verify Stale State (CRITICAL)**: Before reading the chunk `.txt`, check if its output `.md` already exists.
   - Mac/Linux: `[ -f "[WORKSPACE]/chunk_outputs/chunk_XX_output.md" ] && echo Exists || echo Missing`
   - Windows: `Test-Path "[WORKSPACE]/chunk_outputs/chunk_XX_output.md"`
   - If `Exists` → state is stale. Increment counter and check next chunk. Repeat until `Missing`. That is your real resume point.
7. **Completion**: After final chunk, immediately proceed to Step 4 (Assembly) and Step 5 (Verify) as described in `anibon-timestamper-local/SKILL.md`.
