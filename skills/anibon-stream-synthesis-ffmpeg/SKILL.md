---
name: anibon-stream-synthesis-ffmpeg
description: Advanced video editing skill using FFmpeg, emphasizing perfect audio/video sync, frame-accurate waveform cutting, and narrative flow without jump-cutting.
---

# Advanced FFmpeg Video Editing & Narrative Flow

## Overview
This skill provides a structured approach for advanced video editing using FFmpeg. It focuses on achieving frame-accurate cuts, perfect audio-video synchronization, and maintaining a seamless narrative flow. The goal is to produce edits that feel natural, avoiding jarring jump cuts and ensuring the viewer never feels confused.

## Core Principles

### 1. The "But / Therefore" Narrative
Always edit using the "But / Therefore" storytelling method. 
- Avoid "And Then" jump cuts (e.g., cutting from one random farming/grinding segment to another).
- Ensure each scene naturally leads to the next: "This happened, **therefore** this happened," or "This happened, **but** then this unexpected event occurred."
- This maintains viewer engagement and provides a cohesive narrative arc.

### 2. Audio-Waveform Driven Cutting
Do not cut blindly based on visuals alone. Always pay close attention to the audio waveform.
- **Cut at the End of Sentences**: Ensure cuts occur naturally at the exact end of a spoken sentence or breath. 
- Avoid cutting mid-word or mid-breath, which causes jarring jump cuts.
- Look deep into the exact picture and waveform details to find the exact frame where the audio trails off into silence before the next action begins.

### 3. Deep Close Detail (Frame-Accurate Precision)
Look closely at the detailed picture and exact frames.
- Ensure the cut makes visual sense. The transition should feel smooth, not disorienting.
- The viewer should not feel confused by a sudden, inexplicable change in scene, posture, or context. Every cut must feel intentional.

## FFmpeg Technical Implementation

This skill inherently integrates and extends the technical foundation from **`anibon-stream-synthesis/edit-cut-video-ffmpeg`**. To guarantee perfect synchronization and prevent frame freezes, you must re-encode specific segments using FFmpeg's `filter_complex` at the raw frame level.

### Fixing Audio-Video Sync & Frame Freezes

Never use `-c copy` when cutting streams or merging clips, as this causes keyframe issues (black screens/freezes) and container-level packet alignment problems (AV desync).

Instead, force frame-level alignment in memory:

```bash
ffmpeg \
  -i input1.mp4 \
  -i input2.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac \
  -movflags +faststart \
  output_seamless.mp4
```

### Why this is critical:
- `-c:v libx264`: Forces a keyframe at the start, eliminating black screen freezes.
- `-pix_fmt yuv420p`: Ensures compatibility across all players, including macOS/QuickTime.
- `concat=n=2:v=1:a=1`: The `filter_complex` aligns video and audio packets perfectly at the raw frame level, completely resolving progressive desync issues.

## Workflow Execution (TDD RED-GREEN-REFACTOR)

Apply the TDD philosophy to your video editing workflow:

1. **RED (Identify the Problem):** Watch the raw footage. Identify disjointed "And Then" moments, audio trailing, or sync issues. Find the exact frames where the viewer would get confused.
2. **GREEN (Make the Cut):** Use FFmpeg to make precise cuts based on the audio waveform at the end of sentences. Re-encode using `filter_complex` to ensure perfect AV sync and visual continuity.
3. **REFACTOR (Polish the Narrative):** Review the concatenated output. Does it follow the "But / Therefore" structure? Are the cuts invisible to the viewer's cognitive load? If not, adjust the cut points and re-process.

## Red Flags - STOP and Start Over
- The edit feels like an "And Then" sequence without narrative causality.
- You cut while a speaker was still inhaling or mid-sentence.
- You used `-c copy` to save time, resulting in a black screen for the first few seconds of the clip.
- The audio and video slowly drift out of sync over a 5-minute clip.
