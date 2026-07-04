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

2. **Handoff Message**: Output a message to the user explaining that context is full, pointing to the state file, and instructing them to start a new session.
   
   *Example message:*
   > 🔄 [CONTEXT WARNING] My active memory window is nearly full. I have saved the progress state to `/absolute/path/to/youtube_rP8AHWOIXtI_workspace/anibon_timestamper_state.json`. Please start a new conversation session and load BOTH `anibon-timestamper-handoff` and `anibon-timestamper-local` skills to resume from Chunk 12!

---

## 📂 Loading Progress (In a New Session)

When the user starts a fresh conversation session to resume work:

1. **Load Local Rules First**: You MUST read and load `anibon-timestamper-local/SKILL.md` before doing anything else. You need its rules (no `<think>` tags, chunk JSON schema, output format) to function correctly in the loop.
2. **Find and Read State File**: Locate and read `anibon_timestamper_state.json` in the video workspace. Use the absolute path if provided.
3. **Resolve Plugin Path**: Look at the `<skill location="...">` XML tag at the top of your instructions. Extract the directory path up to the `skills/` folder. Replace all backslashes `\` with forward slashes `/`. Use this as the `[PLUGIN_ROOT]` for the script paths below.
4. **Verify Databases**: Even if `db_checked` says `true`, you MUST verify the database for FGO/YGO by running the exact command:
   - FGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - YGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
5. **Resume Step 3 (Loop)**: Do NOT repeat Step 1 (Environment Check) or Step 2 (Download & Chunk via `prepare_video.py`) in the new session. Directly resume Step 3 (Sequential Chunk Loop) starting at the value of `"current_chunk"` (e.g. `chunk_12.txt`).
6. **Verify Chunk Outputs**: Verify that outputs up to `chunk_11_output.md` exist before starting the next one.
7. **Completion**: Once the loop finishes processing the final chunk, you MUST immediately proceed to **Step 4 (Topic Map & Assembly)** and **Step 5 (Verification Check)** exactly as described in `anibon-timestamper-local/SKILL.md`. Pay special attention to drafting the section summaries step-by-step!
