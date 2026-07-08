---
name: highlight-planner
description: Parses livestream-scene-selection markdown into a JSON cut plan.
---

# Highlight Planner

## Overview
Automates the extraction of `[HH:MM:SS - HH:MM:SS]` scenes from a markdown document into a machine-readable JSON cut plan.

## When to Use
- When a user provides a `livestream-scene-selection` markdown file and asks to prepare a highlight cut.

## AI Instructions
1. Find `plan_highlight.py` in the plugin scripts directory.
2. Run it against the target markdown file:
   `python3 scripts/plan_highlight.py path/to/selection.md --video-id <ID> --source <URL_IF_KNOWN>`
3. Read the output.
4. **DO NOT read the output JSON file.** The JSON is strictly machine-to-machine.

## Iron Rule: Token Budget Policy
> 🚫 **The AI MUST NEVER read the plan JSON file with `view_file`, `read_file`, or any file-reading tool at any stage.** Pass the path directly to subsequent scripts.
