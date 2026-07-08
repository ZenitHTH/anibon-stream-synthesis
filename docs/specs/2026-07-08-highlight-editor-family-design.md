# Highlight Editor Skill Family — Design Spec

**Date:** 2026-07-08  
**Plugin:** `anibon-stream-synthesis`  
**Status:** Approved

---

## Overview

A family of three skills that automate the end-to-end workflow of turning a
`livestream-scene-selection` markdown output into a finished, merged highlight
MP4. Each skill has one clear purpose and passes a well-defined artifact to the
next.

---

## Token Budget Policy (Iron Rule — applies to ALL three skills)

> 🚫 **The AI MUST NEVER read the plan JSON file with `view_file`, `read_file`,
> or any file-reading tool at any stage.**
>
> The JSON file is **machine-to-machine**. It is written once by `highlight-planner`
> and read exclusively by Python scripts. The AI only ever holds the **file path**
> (a ~50-character string) — never the file contents.
>
> Violating this rule on a flash/lite model will silently burn token credits for
> zero benefit. Any skill instruction that causes the AI to read the JSON is a bug.

---

## Goals

- Accept the output of `livestream-scene-selection` as the single source of
  truth for which scenes to keep.
- Produce a single merged highlight MP4 with hard cuts and no transitions.
- Ensure the final output is free of frame-freeze, AV desync, and
  QuickTime-incompatible pixel formats.
- Keep each skill independently useful — a user can start from any stage.

## Non-Goals

- No on-screen text overlays, lower-thirds, or title cards.
- No crossfade or fade-to-black transitions.
- No multi-file output (only one final MP4).
- No GUI or web interface.

---

## Skill Family Map

```
livestream-scene-selection  →  highlight-planner  →  highlight-cutter  →  highlight-verifier
(mark scenes / rationale)      (JSON cut plan)        (run ffmpeg)          (QA check)
```

The existing `edit-cut-video-ffmpeg` skill is the **technical reference**
(FFmpeg command patterns) that `highlight-cutter` reads. No duplication.

---

## Skill 1: `highlight-planner`

### Purpose
Parse the `livestream-scene-selection` markdown output and produce a
machine-readable JSON cut plan.

### Input
- A `livestream-scene-selection` markdown file (or pasted text) containing
  timestamp ranges in the format `[HH:MM:SS - HH:MM:SS]`.

### Output
- `highlight_plan_<video_id>.json` in the working session directory.

### JSON Schema
```json
{
  "video_id": "string",
  "source_url": "string or null",
  "total_expected_duration_seconds": 0,
  "scenes": [
    {
      "scene": 1,
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "duration_seconds": 0,
      "label": "Short scene description"
    }
  ]
}
```

### AI Responsibilities
1. Extract all `[HH:MM:SS - HH:MM:SS]` ranges from the markdown.
2. Calculate `duration_seconds` for each scene and `total_expected_duration_seconds`.
3. Validate: no overlapping ranges; `start < end` for every scene.
4. Ask the user for `video_id` and `source_url` if not inferable from context.
5. Write the JSON file and report the total estimated highlight duration.

### Rules
- Do NOT modify or filter scenes — that is the job of `livestream-scene-selection`.
- If a range is malformed, flag it and ask the user to fix it before writing the plan.
- **After writing the JSON, do NOT read it back. Trust the write succeeded.**

---

## Skill 2: `highlight-cutter`

### Purpose
Execute the cut plan — download each scene section and merge all clips into
a single highlight MP4.

### Input
- `highlight_plan_<video_id>.json` (output of `highlight-planner`).
- Video source: YouTube URL (preferred) or local MP4 file path.

### Output
- `highlight_<video_id>.mp4` in the working session directory.

### Companion Script: `scripts/cut_highlight.py`

The skill delegates all heavy lifting to this script. AI's job is to locate
and invoke it correctly.

**CLI Interface:**
```bash
python3 scripts/cut_highlight.py \
  highlight_plan_<video_id>.json \
  --source "https://youtube.com/watch?v=..." \
  --output highlight_<video_id>.mp4
```

**Script Internals:**
1. For each scene in the plan, run:
   ```bash
   yt-dlp --download-sections "*HH:MM:SS-HH:MM:SS" \
     -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
     SOURCE_URL -o "tmp_scene_NNN.mp4"
   ```
2. Build the `ffmpeg -filter_complex concat` command over all `tmp_scene_*.mp4`
   files.
3. Re-encode with `-c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart`.
4. Delete temp scene files on success.
5. Print progress to `stderr`; print only the output path to `stdout`.

**Exit codes:** `0` = success, `1` = runtime error, `64` = bad arguments.

### AI Responsibilities
1. Find `cut_highlight.py` using the standard plugin path search (same pattern
   as `prepare_video.py` in `anibon-timestamper`).
2. Run the script and stream `stderr` to the user.
3. On error, diagnose and retry or report.
4. On success, hand the output path to `highlight-verifier`.

### Rules
- **🚫 NEVER read the plan JSON with `view_file` or any file-reading tool. Pass the file PATH only.**
- Never use `-c copy`. Always re-encode (see `edit-cut-video-ffmpeg` skill).
- Never use the concat demuxer text file — always use `filter_complex`.
- Always set `-pix_fmt yuv420p` for macOS compatibility.

---

## Skill 3: `highlight-verifier`

### Purpose
Quality-check the finished highlight MP4 before it is considered done.

### Input
- Path to the finished `highlight_<video_id>.mp4`.
- Path to `highlight_plan_<video_id>.json` (passed directly to the script — AI does NOT read it).

### Companion Script: `scripts/verify_highlight.py`

All ffprobe calls and JSON reading happen inside this script. The AI only reads
the final short stdout report.

**CLI Interface:**
```bash
python3 scripts/verify_highlight.py \
  highlight_abc123.mp4 \
  highlight_plan_abc123.json
```

**Script Internals — Checks:**

| Check | Tool | Pass Condition |
|-------|------|----------------|
| Duration match | `ffprobe -show_format -of json` | Actual within ±5s of `total_expected_duration_seconds` in plan |
| Audio track present | `ffprobe -show_streams -of json` | At least one audio stream found |
| Video track present | `ffprobe -show_streams -of json` | At least one video stream found |
| Pixel format | `ffprobe -show_streams -of json` | `pix_fmt = yuv420p` |
| Frame freeze at boundaries | `ffprobe -show_packets -of json` | No duplicate PTS at scene-join points |

**Script stdout — short human-readable report only:**
```
✅ PASS  highlight_abc123.mp4
  Duration: 01:23:45 (expected 01:23:42) ✅
  Audio: aac ✅
  Video: h264/yuv420p ✅
  Frame boundaries: 7/7 clean ✅
```
or:
```
❌ FAIL  highlight_abc123.mp4
  Duration: 00:58:10 (expected 01:23:42) ❌ — 25 min short, possible missed scenes
  Frame boundary scene 3: duplicate PTS detected ❌ — re-cut scene 3
```

**Exit codes:** `0` = PASS, `1` = FAIL, `64` = bad arguments.

### AI Responsibilities
1. Find `verify_highlight.py` using the standard plugin path search.
2. Run the script and read **only the short stdout report** (~5 lines).
3. On FAIL, advise which scene to re-cut and invoke `highlight-cutter` again for
   that scene only if the user requests it.

### Rules
- **🚫 NEVER read the plan JSON or ffprobe output directly. The script does all of that.**
- AI context load for this entire skill = ~5 lines of stdout. Nothing else.

---

## File Layout (after implementation)

```
skills/
  highlight-planner/
    SKILL.md
  highlight-cutter/
    SKILL.md
  highlight-verifier/
    SKILL.md

scripts/
  cut_highlight.py       ← new (highlight-cutter companion)
  verify_highlight.py    ← new (highlight-verifier companion)
  _chunker.py            (existing)
  _transcript.py         (existing)
  _vision.py             (existing)
  prepare_video.py       (existing)
```

---

## Dependency Map

| Skill | AI reads | AI writes | Script reads | Script calls |
|-------|----------|-----------|--------------|------|
| `highlight-planner` | scene-selection markdown (small) | `highlight_plan_*.json` | — | — |
| `highlight-cutter` | file path only + stdout (~1 line) | — | `highlight_plan_*.json` | `yt-dlp`, `ffmpeg` |
| `highlight-verifier` | stdout report (~5 lines) | — | `highlight_plan_*.json` + MP4 metadata | `ffprobe` |

**AI token cost per skill invocation (worst case):**
- `highlight-planner`: scene-selection markdown (proportional to stream length)
- `highlight-cutter`: ~1 line
- `highlight-verifier`: ~5 lines

---

## Resolved Design Decisions

- **Local MP4 support**: `cut_highlight.py` accepts either a YouTube URL or a
  local file path as `--source`. If it's a local path, `yt-dlp` is skipped and
  ffmpeg cuts directly from the file.
- **No transitions**: Hard cuts only. Fade-to-black / crossfade deferred to a
  future optional `--fade` flag.
- **AI never reads JSON**: Locked in as an Iron Rule across all three skills.
  Flash/lite models are safe to use for `highlight-cutter` and `highlight-verifier`
  because their AI context load is < 10 lines of text.
