---
name: creating-highlight-video
description: Master orchestrator skill that triggers automatically when a user wants to make a highlight video from a link. Coordinates the planner, cutter, and verifier skills automatically.
---

# Creating a Highlight Video

## Overview
This is the master orchestration skill for the Highlight Editor Family. When the user pastes a video URL and asks for a highlight, you MUST immediately activate this skill. It acts as an automated pipeline director, ensuring the AI seamlessly hands off tasks to the correct sub-skills and scripts without requiring the user to manually invoke them.

## When to Use
- Whenever the user asks to "make a highlight", "cut this video", or pastes a YouTube URL with the intent of extracting scenes.

## The Automated Pipeline

When this skill is activated, you must guide the operation through these 4 strict phases:

### Phase 1: Scene Selection 
To cut a video, we need to know *what* to cut.
1. Ask the user if they already have the timestamps or a Markdown selection list.
2. If they do NOT have one, offer to read the transcript or use the `livestream-scene-selection` skill to help them identify the best timestamps (following the "But / Therefore" rule).
3. **REQUIRED SUB-SKILL:** Before finalizing any scene selection, you MUST apply `highlight-no-jumpcut-rules`. This skill enforces Walter Murch's Rule of Six, the 5-min buffer rule, the merge-contiguous rule, and the pacing rollercoaster — all of which prevent jump cuts in the final output.
4. Once you have the timeline validated against `highlight-no-jumpcut-rules`, write it out to a `.md` file (e.g., `highlight_selection.md`). 
> **Workspace Rule:** If there is an existing `youtube_<VIDEO_ID>_workspace` directory (created by `anibon-timestamper` or similar skills), you MUST save this `.md` file inside that directory!

### Phase 2: Highlight Planner
Once the `.md` file is ready, you must invoke the planner.
1. See `highlight-planner/SKILL.md`.
2. Run: `python3 scripts/plan_highlight.py <your_markdown_file.md> --video-id <ID> --source <URL>`
3. Wait for the `highlight_plan_<id>.json` file to be generated.
4. **CRITICAL DURATION CHECK:** Read the stdout from the planner script. If the total highlight duration exceeds **30 minutes**, STOP and warn the user. Tell them downloading will take a long time, and offer to list available resolutions/framerates using `yt-dlp -F <URL>`. If they choose a lower quality to save time, append `--format "<their_choice>"` during Phase 3.
> **Iron Rule:** Never read the JSON file. It is for the machine only.

### Phase 3: Highlight Cutter (Subagent Delegation)
Because video downloading and FFmpeg rendering can take time, this phase should ideally be handled cleanly.
1. See `highlight-cutter/SKILL.md`.
2. Run: `python3 scripts/cut_highlight.py <your_plan.json> --source <URL> [--format "chosen_format"]`
3. Monitor the background task or subagent. It will download the chunks (or use a local `--source`) and stitch them via FFmpeg `filter_complex`. 
> **Tip:** If the user already downloaded the full video to avoid YouTube rate limits, pass the local file path to `--source` instead of the URL!

### Phase 4: Highlight Verifier
Once the `.mp4` is rendered, we must QA check it.
1. See `highlight-verifier/SKILL.md`.
2. Run: `python3 scripts/verify_highlight.py <your_highlight.mp4> <your_plan.json>`
3. Read the output. If it PASSES, present the final MP4 file link to the user!

## Zero-Friction Execution
The goal of this orchestrator is **Zero-Friction**. Do not stop and ask the user for permission between Phase 2, 3, and 4. Once Phase 1 is complete and the timestamps are approved, you should execute the Planner, Cutter, and Verifier in one continuous flow, only reporting back to the user when the final QA-checked MP4 is ready!
