---
name: antigravity-vision-proxy
description: Use when the current agent cannot directly view or analyze images, but frame inspection is needed for video analysis or visual context.
---

# Antigravity Vision Proxy

## Overview
Use `agy --print` as a subprocess to analyze images via Gemini vision models. Frame extraction (ffmpeg) + agy invocation + structured output parsing.

## When to Use

- Agent lacks built-in vision but needs to identify game, heroes, or activity from video frames
- Video frame analysis needed for timestamping or scene classification
- Any scenario requiring visual context that the current model cannot see

Do NOT use for: purely audio analysis, already-transcribed text, tasks where transcript alone suffices.

## Frame Extraction

### Option A: Lightweight YouTube Storyboard (`sb0`) — Preferred for YouTube (No full video download, ~15MB total)

```bash
# 1. Download storyboard mhtml (covers entire multi-hour stream in ~15MB)
yt-dlp -f sb0 "https://www.youtube.com/watch?v=VIDEO_ID" -o "frames/storyboard.%(ext)s"

# 2. Unpack MHTML slides and crop timestamp tile
# Each slide is 960x540 (3x3 grid of 320x180 tiles, ~89.93s per slide, ~10s per tile)
python3 -c "
import email, os
from email import policy

mhtml = 'frames/storyboard.mhtml'
os.makedirs('frames/slides', exist_ok=True)
with open(mhtml, 'rb') as f:
    msg = email.message_from_binary_file(f, policy=policy.default)
for idx, p in enumerate(list(msg.iter_parts())[1:], 1):
    with open(f'frames/slides/slide_{idx:03d}.jpg', 'wb') as out:
        out.write(p.get_payload(decode=True))
"

# 3. Crop target timestamp HH:MM:SS
# slide_idx = int(sec / 89.932) + 1, sub = min(8, int((sec % 89.932) / 9.9924))
# x = (sub % 3) * 320, y = (sub // 3) * 180
ffmpeg -y -i frames/slides/slide_007.jpg -vf "crop=320:180:640:180" frames/frame_00_09_57.jpg
```

### Option B: Local Video / MP4 File

```powershell
# Single frame
ffmpeg -ss HH:MM:SS -i full_video.mp4 -frames:v 1 -q:v 2 frames\frame.jpg

# Batch: every N seconds for $duration total
0..([math]::Floor($duration/$interval)) | % {
  $t = $_ * $interval
  $ts = "{0:D2}:{1:D2}:{2:D2}" -f [math]::Floor($t/3600),[math]::Floor(($t%3600)/60),($t%60)
  ffmpeg -ss $ts -i full_video.mp4 -frames:v 1 -q:v 2 "frames\frame_$ts.jpg"
}
```

## Invoke agy

```powershell
agy --model "Gemini 3.6 Flash" --dangerously-skip-permissions `
  --print "Identify per frame: 1) Game 2) Heroes/characters 3) Gameplay/menu/cutscene 4) Notable events" `
  --add-dir frames
```

Required: `--dangerously-skip-permissions` + `--add-dir frames`

For parseable output, request JSON in the prompt:
`"Return JSON array: [{timestamp, game, heroes, activity}]"`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| agy "cannot access file" | Missing `--add-dir` or wrong path |
| Low-confidence hero IDs | Cross-reference with transcript text for character names |
| Frame quality too low | `-q:v 2` for UI text, `-q:v 5` for game ID |
| Extracting too frequently | >1 frame per 30s adds cost with diminishing returns |

## Model Selection

| Model | Cost | Use |
|-------|------|-----|
| Gemini 3.6 Flash | Default | Bulk game scanning |
| Gemini 3.6 Flash (High) | Moderate | Hero/UI text identification |
| Gemini 3.1 Pro (Low) | Moderate | When Flash misidentifies |
