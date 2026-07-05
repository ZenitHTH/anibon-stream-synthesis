---
name: edit-cut-video-ffmpeg
description: Use when cutting, concatenating, or fixing audio-video synchronization and frame freeze issues in downloaded video streams
---

# Edit Cut Video with FFmpeg

## Overview
Automated pipeline for cutting highlights from live streams and fixing common playback issues (frame freezes, black screens, AV desync). Re-encode specific segments using FFmpeg's `filter_complex` at the raw frame level to ensure perfect synchronization.

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

## Red Flags - STOP and Start Over
- Trying to use `-c copy` to save time when cutting streams.
- Recommending `concat` demuxer (text file) for stream clips.
- "I'll just download the whole video and use a GUI."
- Omitting `-pix_fmt yuv420p` for macOS outputs.

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
