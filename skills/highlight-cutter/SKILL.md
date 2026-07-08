---
name: highlight-cutter
description: Executes a cut plan via yt-dlp + ffmpeg to produce a merged highlight MP4.
---

# Highlight Cutter

## Overview
Orchestrates downloading chunks and merging them using `filter_complex` concat, avoiding frame-freezes and AV desync.

## When to Use
- When a `highlight_plan_<id>.json` is ready and the user wants to generate the video.

## AI Instructions
1. Find `cut_highlight.py` in the plugin scripts directory.
2. Run it, providing the JSON plan and the source URL/file:
   `python3 scripts/cut_highlight.py path/to/highlight_plan_abc123.json --source <URL>`
3. Monitor `stderr` for progress. The final output path will be printed on `stdout`.
4. Proceed to `highlight-verifier` when finished.

## Iron Rule: Token Budget Policy
> 🚫 **The AI MUST NEVER read the plan JSON file with `view_file`, `read_file`, or any file-reading tool at any stage.**
