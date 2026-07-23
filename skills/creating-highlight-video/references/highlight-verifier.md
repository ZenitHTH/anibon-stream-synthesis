---
name: highlight-verifier
description: Quality-checks a highlight MP4 for duration, tracks, and pixel format against the JSON cut plan.
---

# Highlight Verifier

## Overview
Runs `ffprobe` QA checks over an exported highlight MP4 to ensure it meets requirements.

## When to Use
- After `highlight-cutter` completes its render.

## AI Instructions
- **Find `[SKILL_ROOT]`**: Look at the `<skill location="...">` XML tag at the top of your prompt. Strip the filename `SKILL.md` (or with backslashes `\` on Windows). Replace all `\` with `/`. The result is `[SKILL_ROOT]`.
1. Find `verify_highlight.py` in the skill's scripts directory: `[SKILL_ROOT]/scripts/verify_highlight.py`.
2. Run it against the MP4 and JSON plan:
   `python3 "[SKILL_ROOT]/scripts/verify_highlight.py" path/to/highlight.mp4 path/to/plan.json`
3. Read the stdout report (it will be ~5 lines).
4. Inform the user if it PASSes or FAILs.

## Iron Rule: Token Budget Policy
> 🚫 **The AI MUST NEVER read the plan JSON file or ffprobe JSON output with `view_file`, `read_file`, or any file-reading tool at any stage.** 
