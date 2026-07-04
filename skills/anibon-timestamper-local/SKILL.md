---
name: anibon-timestamper-local
description: Use when generating timestamps for Anibon streams on a LOCAL model (Ollama, gemma4, qwen). Focuses on step-by-step sequential looping, minimal context, and goldfish brain rules.
---

# 🎬 Anibon Timestamper (Local AI Edition)

Optimized for local LLMs with limited context windows (e.g. Gemma 4, Qwen 2.5).
Processes video transcripts in sequential chunks to preserve memory.

---

## ⚡ Goldfish Brain Rules (CRITICAL)
1. **State your step**: Before any action, state what step you are on.
2. **One tool per turn**: Never run batch actions.
3. **Save and forget**: Write output for each chunk to a file, then forget it.
4. **Process inline**: Read the `.txt` file, write timestamps yourself. No subagents.
5. **No dry-running**: Every `read`, `write`, or `bash` MUST be a real tool call. If you cannot call a tool, output exactly: `[STUCK: cannot call tool, awaiting user input]` and stop.
6. **STOP LOOP rule**: If you say "Wait", "Actually", or restart your reasoning — you are looping. **STOP and call a tool immediately.** decide → act → done.
7. **Handoff when full**: If slow or forgetting, write `anibon_timestamper_state.json` and stop.
8. **Forward Slashes Only**: Always `C:/Users/peter/...`. Backslashes get stripped.

---

## 🧭 Steps

### Step 1: Resolve Plugin Path & Verify
Shell is MINGW64/bash. Run:
```bash
uname -a && python3 --version
```
Resolve `[PLUGIN_ROOT]` from the `<skill location="...">` XML tag: extract path up to (not including) `skills/`, replace `\` → `/`.

### Step 2: Download & Chunk
```bash
python3 "[PLUGIN_ROOT]/scripts/prepare_video.py" "VIDEO_URL" --format txt --block 300 --overlap 30
```
*(If blocked by YouTube, ask user for cookies or raw_transcript.json.)*

### Step 3: Sequential Chunk Loop
For each chunk `chunk_00.txt`, `chunk_01.txt`, ...:
1. **Read**: `read C:/Users/peter/<workspace>/chunks/chunk_XX.txt`
2. **DB check** (only if chunk text contains `FGO`, `Fate`, `YGO`, or `遊戯王`):
   - FGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_fgo_db.py" --check`
   - YGO: `python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/fetch_ygo_db.py" --check`
   - Exit 1 → re-run without `--check` to build. Otherwise skip.
3. **Generate timestamps**: follow the Prompt Template below.
4. **Write**: save to `C:/Users/peter/<workspace>/chunk_outputs/chunk_XX_output.md`
5. **Auto-resume**: immediately read `chunk_XX+1.txt`. Do NOT wait.
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

📌 ส่วนที่ 1: บ๊อตทักทายผู้ชม เปิดสตรีมยามเย็น
(หัวข้อ: ทักทาย | ⏱ เริ่ม: 00:03:52)
00:03:52 บ๊อตทักทายผู้ชม เริ่มสตรีม

📌 ส่วนที่ 2: พูดคุยช่วงที่ไม่ได้อัปเดตข่าวการเมืองนานกว่า 3 สัปดาห์
(หัวข้อ: อัปเดตข่าวสาร | ⏱ เริ่ม: 00:04:01)
00:04:01 พูดถึงช่วงเว้นว่างจากข่าวการเมือง
```

- First line: HTML comment (required for merge).
- `📌 ส่วนที่ N:` — use a running counter N that continues across ALL chunks (not per-chunk).
- Summary line: 1 sentence, what happened in this block.
- `(หัวข้อ: ... | ⏱ เริ่ม: HH:MM:SS)` — short title + first timestamp of the block.
- `HH:MM:SS description` lines below — just time + Thai text, no dashes, no tags.
- No meta-commentary or apologies in this file.

**Edge cases (check only if gap > 10 min or timestamps seem wrong):**
- Trust `item.start` over your intuition — timestamps come from YouTube captions.
- Gap > 10 min with nothing in between → write `HH:MM:SS [GAP: no transcript data]`.

---

### Step 4: Assembly
```bash
cat chunk_outputs/chunk_*_output.md > timestamp_VIDEO_ID.md
```
Then:
1. Remove all `<!-- chunk_XX ... -->` lines.
2. The `📌 ส่วนที่ N` headers from chunks are already in the final format — no reformatting needed.
3. If any consecutive section block exceeds **50 timestamp lines**, split it: duplicate the header as Part 1 / Part 2 and divide the lines between them.

### Step 5: Verify
```bash
python3 "[PLUGIN_ROOT]/skills/anibon-timestamper/scripts/check_sections.py" timestamp_VIDEO_ID.md
```
Split further if any section fails (❌ or ⚠️).
