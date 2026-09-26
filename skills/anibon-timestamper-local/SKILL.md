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

### Step 3: Launch Local Timestamper Runner
Execute via shell tool (`run_commands` / `run_command`):

```powershell
# PRIMARY METHOD (runs launch_local.ps1 detached; returns in 0.5s so Cline 30s timeout NEVER triggers):
powershell -ExecutionPolicy Bypass -File "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/launch_local.ps1" -Workspace "C:/Users/peter/youtube_<VIDEO_ID>_workspace"

# Interactive terminal execution:
python -X utf8 "C:/Users/peter/.agents/skills/anibon-timestamper-local/scripts/process_chunks_local.py" "[WORKSPACE]" --model auto --lang th
```

*(For English output, pass `-Lang en` or `--lang en`)*

### Step 3b: Check Progress
Check the background runner's progress anytime:
```powershell
Get-Content "C:/Users/peter/youtube_<VIDEO_ID>_workspace/timestamper.log" -Tail 10
```

### Step 4: Completion
When `[WORKSPACE]/anibon_timestamps.md` is generated, provide the path to the user.

---

## 🛑 Strict Rules

1. **Shell Execution Only**: Always execute Python scripts via the shell tool (`run_commands` in Cline / `run_command` in Antigravity).
2. **Never Process Chunks in Chat**: Do NOT manually read chunks or generate timestamps turn-by-turn in chat. Chat context will bloat past 100k tokens and cause HTTP timeouts on local GPUs.
3. **Stay Inside `[WORKSPACE]`**: Never search or scan files in home root (`C:/Users/peter/anibon*`). All files belong strictly inside `[WORKSPACE]`.
4. **NEVER Write or Invent Scripts**:
   If you think a process is slow or pending, **NEVER** write your own `.py` scripts (`process_all_chunks.py`), do NOT write shell scripts (`cat > ...`), and do NOT send raw HTTP calls to LM Studio. All execution is handled by `launch_local.ps1` and `process_chunks_local.py`. Writing custom scripts is strictly forbidden.
5. **Handling 30000ms Command Timeout**:
   In Cline, `run_commands` has a 30-second timeout. Always launch the timestamper using `launch_local.ps1` (Step 3). It launches the process detached in the background in under 1 second, logs output to `[WORKSPACE]/timestamper.log`, and never times out.
6. **Model Architecture on P100 (16GB VRAM) & Zero-Conflict Rule**:
   - On 16GB GPUs (Tesla P100), loading multiple models simultaneously exceeds VRAM during active generation due to KV cache allocations, causing LM Studio to evict models.
   - **Recommended Primary Model**: **`google/gemma-4-12b-qat`** (7.15 GB). It provides vastly superior natural language understanding and semantic nuance (Google DeepMind lineage), accurately capturing subtle topic boundaries and specific entities (e.g. AI, ปลาหมอคางดำ) without hyper-generalizing or over-skipping like surface keyword matchers.
   - **VRAM Headroom**: Loading `google/gemma-4-12b-qat` as the single unified model leaves **~8.85 GB free VRAM** for large context KV cache and parallel slot allocations without any VRAM eviction.
   - **NEVER** run `lms unload all` or `lms unload`! The runner uses `--model auto`, which automatically queries and uses whichever model is active in LM Studio without triggering reload or eviction.

---

## 🎯 Front-Tier Quality Standards (80%+ Benchmark Match)

The built-in prompt and post-processor in `process_chunks_local.py` automatically enforce:
- **First-Verb Streamer Tone**: Uses active Pu Boat signature verbs (`แซว`, `ฮาลั่น!`, `เม้าท์มอย`, `ขำก๊าก`, `ชำแหละ`, `จวกยับ`, `วิเคราะห์`, `เจาะลึก`, `อึ้ง!`) and strictly bans flat verbs like `พูดถึง...`.
- **Automatic Sanitization**: Strips meta-prompts, English commentary, and parenthetical translations `(...)` automatically.
- **Part Summaries & Double Borders**: Formats each part with `═` double borders and an intelligent 2-3 topic executive summary matching the front-tier benchmark in `timestamp-workspace`.


