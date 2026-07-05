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
You already know where everything is. Never search for files.
- **Main Scripts**: `[PLUGIN_ROOT]/scripts/prepare_video.py`
- **Sub-scripts**: `[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/` (`fetch_fgo_db.py`, `fetch_ygo_db.py`, `check_sections.py`)
- **Workspace**: `C:/Users/peter/youtube_<video_id>_workspace/`
  - `/chunks/chunk_XX.txt`
  - `/chunk_outputs/chunk_XX_output.md`
  - `/anibon_timestamper_state.json`

## ⚡ Strict Rules
- **No Curiosity / No Exploration**: Do NOT run `ls`, `find`, or explore the filesystem. Just blindly execute the paths. Do not list directory contents to "check progress".

---

## 💾 Saving Progress (When Context is Full)

If the local AI shows signs of context exhaustion (e.g. high latency, repetitive responses, forgetting instructions):

1. **Write State File**: Write a JSON file named `anibon_timestamper_state.json` inside the active video workspace directory (e.g., `youtube_<video_id>_workspace/anibon_timestamper_state.json`).
   
   **JSON Schema:**
   ```json
   {
     "video_id": "YOUR_YOUTUBE_VIDEO_ID",
     "video_url": "YOUR_YOUTUBE_VIDEO_URL",
     "workspace_path": "/absolute/path/to/youtube_<video_id>_workspace",
     "total_chunks": 48,
     "current_chunk": 12,
     "db_checked": {
       "fgo": true,
       "ygo": false
     },
     "phase": "chunk_loop",
     "last_updated": "2026-06-29T09:23:00Z"
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

1. **Resolve Plugin Path**: Look at the `<skill location="...">` XML tag at the top of your instructions. Delete the exact text `skills\anibon-timestamper-handoff\SKILL.md` from the end of it. Replace all backslashes `\` with forward slashes `/`. This remaining path is your `[PLUGIN_ROOT]`.
   - 🚨 **ANTI-TYPO WARNING**: You (the AI) are prone to confusing hyphens (`-`) and underscores (`_`) when typing from memory. The repository is `anibon-stream-synthesis` (HYPHENS). The skill folder is `anibon-timestamper` (HYPHENS). NEVER use underscores for these! Copy the path directly, do not retype it.
2. **Read Local Rules**: You MUST read the core rules by calling the `read` tool on `[PLUGIN_ROOT]/skills/anibon-timestamper-local/SKILL.md`. You need its rules (no `<think>` tags, output format) to function correctly.
3. **Read State File**: Extract the video ID from the user's URL. The state file is ALWAYS located at `C:/Users/peter/youtube_<video_id>_workspace/anibon_timestamper_state.json`. `read` this file directly. Do NOT run `ls -R` or search commands.
4. **Verify Databases**: Even if `db_checked` says `true`, you MUST verify the database for FGO/YGO by running the exact commands below. If a `--check` command fails (exit code 1), do NOT debug paths or use `ls`. Just run the specific download command exactly as provided below!
   - FGO Check: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - FGO Download (if check fails): `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py"`
   - YGO Check: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
   - YGO Download (if check fails): `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py"`
5. **Resume Step 3 (Loop)**: Do not repeat Step 1 or Step 2. Directly resume Step 3 (Sequential Chunk Loop) by immediately reading the chunk specified by `"current_chunk"`. Because this value represents the exact NEXT chunk to process, you should start with it. **CRITICAL**: The chunk files are zero-padded to two digits (e.g. if current_chunk is 2, the file is `chunk_02.txt`; if 12, it is `chunk_12.txt`).
6. **Verify Stale State (CRITICAL)**: Sometimes the state file is stale because a previous session crashed before saving. Before you read the `.txt` file for `"current_chunk"`, you MUST use a bash command (e.g., `[ -f "C:/.../chunk_XX_output.md" ] && echo "Exists" || echo "Missing"`) to check if its output `.md` file *already exists*. If it exists, the state is stale! Increment your chunk counter and check the next one until you find the first chunk that is "Missing". That is where you actually resume!
7. **Completion**: Once the loop finishes processing the final chunk, you MUST immediately proceed to **Step 4 (Topic Map & Assembly)** and **Step 5 (Verification Check)** exactly as described in `anibon-timestamper-local/SKILL.md`. Pay special attention to drafting the section summaries step-by-step!
