---
name: edit-cut-video-ffmpeg
description: Use when cutting, concatenating, or fixing audio-video synchronization and frame freeze issues in downloaded video streams, emphasizing frame-accurate waveform cutting and narrative flow.
---

# Edit Cut Video with FFmpeg

## Overview
Automated pipeline for cutting highlights from live streams and fixing common playback issues (frame freezes, black screens, AV desync). Re-encode specific segments using FFmpeg's `filter_complex` at the raw frame level to ensure perfect synchronization, seamless narrative flow, and frame-accurate precision.

## Core Principles

### 1. The "But / Therefore" Narrative
Always edit using the "But / Therefore" storytelling method.
- Avoid "And Then" jump cuts (e.g., cutting from one random farming/grinding segment to another).
- Ensure each scene naturally leads to the next: "This happened, **therefore** this happened," or "This happened, **but** then this unexpected event occurred."
- This maintains viewer engagement and provides a cohesive narrative arc.

### 2. Audio-Waveform Driven Cutting
Do not cut blindly based on visuals alone. Always pay close attention to the audio waveform.
- **Cut at the End of Sentences**: Ensure cuts occur naturally at the exact end of a spoken sentence or breath trail-off.
- Avoid cutting mid-word or mid-breath, which causes jarring jump cuts.
- Find the exact frame where the audio trails off into silence before the next action begins.

### 3. Deep Close Detail (Frame-Accurate Precision)
Look closely at the detailed picture and exact frames.
- Ensure the cut makes visual sense. The transition should feel smooth, not disorienting.
- The viewer should not feel confused by a sudden, inexplicable change in scene, posture, or context. Every cut must feel intentional.

## When to Use
- You need to cut highlight clips from a long-form video or stream.
- You encounter black screens or frame freezes at the beginning of cut clips.
- Audio and video become desynchronized after cutting or concatenating clips.
- You need to ensure the final output is compatible with macOS (QuickTime).

## Core Pattern
Instead of simple stream copying (`-c copy`), which causes keyframe and sync issues, use raw frame-level processing with `-filter_complex` and force re-encoding to standard formats.

```bash
# Fix desync and frame freeze by re-encoding at frame level
ffmpeg -i input1.mp4 -i input2.mp4 -filter_complex \
  "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac \
  output.mp4
```

## Quick Reference
| Operation | Command Pattern | Why |
|-----------|-----------------|-----|
| **Download slice** | `yt-dlp --download-sections "*start-end" URL` | Saves time and storage compared to full download. |
| **Fix frame freeze** | `-c:v libx264 -pix_fmt yuv420p -c:a aac` | Re-encoding creates new keyframes; QuickTime requires yuv420p. |
| **Fix AV desync** | `-filter_complex "[0:v][0:a]concat=n=1:v=1:a=1"` | Forces frame-level alignment in memory instead of container-level. |

## Implementation

### 1. Download specific sections
Use `yt-dlp` to download only the necessary sections. Note: This requires FFmpeg.
```bash
yt-dlp --download-sections "*00:01:00-00:01:40" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" "URL" -o "segment.mp4"
```

### 2. Concatenate and fix sync issues
To avoid black screens (due to missing initial keyframes) and AV desync (due to container-level packet alignment), you must re-encode and use `filter_complex`.

```bash
ffmpeg \
  -i segment1.mp4 \
  -i segment2.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac \
  -movflags +faststart \
  final_highlight.mp4
```

## Workflow Execution (TDD RED-GREEN-REFACTOR)

1. **RED (Identify the Problem):** Watch the raw footage. Identify disjointed "And Then" moments, audio trailing, or sync issues. Find the exact frames where the viewer would get confused.
2. **GREEN (Make the Cut):** Use FFmpeg to make precise cuts based on the audio waveform at the end of sentences. Re-encode using `filter_complex` to ensure perfect AV sync and visual continuity.
3. **REFACTOR (Polish the Narrative):** Review the concatenated output. Does it follow the "But / Therefore" structure? Are the cuts invisible to the viewer's cognitive load? If not, adjust the cut points and re-process.

## Red Flags - STOP and Start Over
- Trying to use `-c copy` to save time when cutting streams.
- Recommending `concat` demuxer (text file) for stream clips.
- "I'll just download the whole video and use a GUI."
- Omitting `-pix_fmt yuv420p` for macOS outputs.
- Cutting while a speaker was still inhaling or mid-sentence.
- The edit feels like an "And Then" sequence without narrative causality.

## Rationalization Table
| Excuse | Reality |
|--------|---------|
| "Re-encoding takes too long, use `-c copy`" | `-c copy` on stream downloads causes black screens because cuts don't land on keyframes. |
| "Concat demuxer is faster than filter_complex" | Demuxer fails to align audio and video packets perfectly, leading to progressive desync. |
| "I don't need `yuv420p` for mp4" | High-profile H.264 formats default to pixel formats QuickTime/macOS cannot play. |

## Common Mistakes
| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Using `-c copy` to trim | Black screens/freezes at start | Re-encode with `-c:v libx264` to force a keyframe at start. |
| Concatenating via demuxer text file | Audio desync across cuts | Use `filter_complex` `concat` filter to align at raw frame level. |
| Forgetting `-pix_fmt yuv420p` | Video won't play in QuickTime | Always explicitly set `yuv420p` when encoding to H.264 for macOS. |
