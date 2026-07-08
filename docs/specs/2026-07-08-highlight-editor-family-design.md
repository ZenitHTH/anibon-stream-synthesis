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
- Never use `-c copy`. Always re-encode (see `edit-cut-video-ffmpeg` skill).
- Never use the concat demuxer text file — always use `filter_complex`.
- Always set `-pix_fmt yuv420p` for macOS compatibility.

---

## Skill 3: `highlight-verifier`

### Purpose
Quality-check the finished highlight MP4 before it is considered done.

### Input
- Path to the finished `highlight_<video_id>.mp4`.
- `highlight_plan_<video_id>.json` (for expected duration).

### Checks

| Check | Tool | Pass Condition |
|-------|------|----------------|
| Duration match | `ffprobe -show_format` | Actual duration within ±5s of `total_expected_duration_seconds` |
| Audio track present | `ffprobe -show_streams` | At least one audio stream found |
| Video track present | `ffprobe -show_streams` | At least one video stream found |
| Pixel format | `ffprobe -show_streams` | `pix_fmt = yuv420p` |
| Frame freeze at boundaries | `ffprobe -show_packets` | No duplicate PTS packets at scene-join points |

### Output
A short report:
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

### AI Responsibilities
1. Run `ffprobe` commands and parse JSON output (`-of json`).
2. Compare against the plan's `total_expected_duration_seconds`.
3. Report pass/fail per check.
4. On failure, advise which scene to re-cut and invoke `highlight-cutter` again
   for that scene only if the user requests it.

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
  cut_highlight.py       ← new companion script
  _chunker.py            (existing)
  _transcript.py         (existing)
  _vision.py             (existing)
  prepare_video.py       (existing)
```

---

## Dependency Map

| Skill | Reads | Writes | Calls |
|-------|-------|--------|-------|
| `highlight-planner` | scene-selection markdown | `highlight_plan_*.json` | nothing |
| `highlight-cutter` | `highlight_plan_*.json` + video source | `highlight_*.mp4` | `cut_highlight.py`, `yt-dlp`, `ffmpeg` |
| `highlight-verifier` | `highlight_*.mp4` + `highlight_plan_*.json` | terminal report | `ffprobe` |

---

## Open Questions / Future Work

- Should `highlight-cutter` support local MP4 input (not just URL)? For now: yes,
  the script will accept a file path as `--source` and skip `yt-dlp`.
- Transition cards (fade-to-black, chapter screens) are out of scope for v1 but
  could be added as an optional flag later.
