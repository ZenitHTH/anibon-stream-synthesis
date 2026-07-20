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
agy --model "Gemini 3.5 Flash (Low)" --dangerously-skip-permissions `
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
| Gemini 3.5 Flash (Low) | Cheapest | Bulk game scanning |
| Gemini 3.5 Flash (High) | Moderate | Hero/UI text identification |
| Gemini 3.1 Pro (Low) | Moderate | When Flash misidentifies |
