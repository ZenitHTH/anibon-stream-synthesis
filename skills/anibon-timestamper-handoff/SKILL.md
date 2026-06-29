---
name: anibon-timestamper-handoff
description: Save or load the progress state of a local timestamper session to prevent token context window exhaustion.
---

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
   > 🔄 [CONTEXT WARNING] My active memory window is nearly full. I have saved the progress state to `youtube_rP8AHWOIXtI_workspace/anibon_timestamper_state.json`. Please start a new conversation session and load the `anibon-timestamper-handoff` skill to resume from Chunk 12!

---

## 📂 Loading Progress (In a New Session)

When the user starts a fresh conversation session to resume work:

1. **Find and Read State File**: Locate and read `anibon_timestamper_state.json` in the video workspace.
2. **Resume Step 3 (Loop)**: Do NOT repeat Step 1 (Environment Check) or Step 2 (Download & Chunk) in the new session. Directly resume Step 3 (Sequential Chunk Loop) starting at the value of `"current_chunk"` (e.g. `chunk_12.json`).
3. **Verify Chunk Outputs**: Verify that outputs up to `chunk_11_output.md` exist before starting the next one.
