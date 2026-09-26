---
name: anibon-timestamper-local
description: Generate timestamps for Anibon Official streams via local LLM (LM Studio / llama.cpp / Ollama).
---

# Anibon Timestamper (Local LLM Edition)

Generates front-tier quality timestamps for long livestreams using a local LLM (LM Studio default on port 1234). Runs fully automated via CLI runner.

## 🚀 Execution Workflow (3 Steps Only)

When invoked with a YouTube video URL or ID:

### Step 1: Set Paths
1. Extract `VIDEO_ID` from URL (e.g., `https://www.youtube.com/watch?v=nF7pCwCZCaE` → `nF7pCwCZCaE`).
2. Set `[WORKSPACE]`:
   - Windows: `C:/Users/<username>/youtube_<VIDEO_ID>_workspace` (e.g. `C:/Users/peter/youtube_nF7pCwCZCaE_workspace`)
   - Mac/Linux: `~/youtube_<VIDEO_ID>_workspace`
3. Resolve `[SKILL_ROOT]`:
   - **`.agents` format (Cline / Roo / Claude Code / Cursor)**: `C:/Users/<username>/.agents/skills/anibon-timestamper-local` (or `~/.agents/skills/anibon-timestamper-local`)
   - **`.gemini` format (Antigravity)**: `C:/Users/<username>/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local`

### Step 2: Download & Chunk (Skip If Already Done)
Test if `[WORKSPACE]/chunks/chunk_00.txt` exists.
- If it **already exists**: **SKIP THIS STEP COMPLETELY**.
- If it **does not exist**, run via shell tool (`run_commands` / `run_command`):

```powershell
# Direct Windows execution (works in any directory):
python "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/prepare_video.py" "VIDEO_URL" --workspace "[WORKSPACE]" --format txt --block 300 --overlap 30

# Cross-platform fallback:
python "[SKILL_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --workspace "[WORKSPACE]" --format txt --block 300 --overlap 30
```

> ⚠️ **NO WEB SCRAPERS**: Never use `fetch_web_content`, browser, or `curl` on YouTube. Always run `prepare_video.py` in shell. Never download raw video files.

### Step 3: Run Local Timestamper Runner
Execute the automated local timestamper via shell tool (`run_commands` / `run_command`):

```powershell
# In Cline (runs detached in background so Cline's 30s tool timeout does not kill it):
Start-Process python -ArgumentList '-X utf8 "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "C:/Users/peter/youtube_<VIDEO_ID>_workspace" --model "google/gemma-4-12b-qat" --lang th'

# Or in standard interactive terminal:
python -X utf8 "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "[WORKSPACE]" --model "google/gemma-4-12b-qat" --lang th
```

*(For English output, use `--lang en`)*

### Step 4: Completion
The runner processes all chunks, tracks topic continuity, validates timestamp ranges, and writes the assembled markdown to:
`[WORKSPACE]/anibon_timestamps.md`

Output the path to the user when finished.

---

## 🛑 Strict Rules

1. **Shell Execution Only**: Always execute Python scripts via the shell tool (`run_commands` in Cline / `run_command` in Antigravity).
2. **Never Process Chunks in Chat**: Do NOT manually read chunks or generate timestamps turn-by-turn in chat. Chat context will bloat past 100k tokens and cause HTTP timeouts on local GPUs.
3. **Stay Inside `[WORKSPACE]`**: Never search or scan files in home root (`C:/Users/peter/anibon*`). All files belong strictly inside `[WORKSPACE]`.
4. **NEVER Write or Invent Scripts**:
   If a command times out (`Command timed out after 30000ms`) or exits with an error, **NEVER** write your own `.py` scripts, do NOT write startup scripts, and do NOT write custom transcript parsers. All required scripts exist. Writing custom scripts is strictly forbidden.
5. **Handling 30000ms Command Timeout**:
   In Cline, `run_commands` has a 30-second timeout. Processing 30 chunks takes ~2–4 minutes. Always launch via `Start-Process` (Step 3) or instruct the user to run the command in their own PowerShell terminal outside Cline.

