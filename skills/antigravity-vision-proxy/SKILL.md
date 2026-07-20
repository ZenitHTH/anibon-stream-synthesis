---
name: antigravity-vision-proxy
description: Use agy CLI as a vision proxy when the current agent cannot directly view or analyze images. Extracts frames from video, passes them to agy (Gemini), and returns structured visual analysis.
---

# Antigravity Vision Proxy

When the current agent lacks built-in vision, use `agy` as a subprocess to analyze images. `agy` supports Gemini models with vision capability.

## Frame Extraction

Extract frames from video at specific timestamps using ffmpeg:

```powershell
ffmpeg -ss HH:MM:SS -i workspace\full_video.mp4 -frames:v 1 -q:v 2 workspace\frames\frame_TIMESTAMP.jpg
```

Batch extraction at regular intervals:

```powershell
# Every 60s from start to end
$interval = 60; $duration = 18720 # total seconds
0..([math]::Floor($duration/$interval)) | % {
  $t = $_ * $interval
  $h = [math]::Floor($t/3600); $m = [math]::Floor(($t%3600)/60); $s = $t%60
  $ts = "{0:D2}:{1:D2}:{2:D2}" -f $h,$m,$s
  ffmpeg -ss $ts -i workspace\full_video.mp4 -frames:v 1 -q:v 2 "workspace\frames\frame_$ts.jpg"
}
```

## Invoke agy for Visual Analysis

Use `--print` (non-interactive) mode with `--dangerously-skip-permissions`:

```powershell
# Single frame
agy --model "Gemini 3.5 Flash (Low)" --dangerously-skip-permissions --print "What game is being played in this frame? Identify the game, heroes/characters visible, and any notable on-screen activity." --add-dir workspace\frames

# With context
agy --model "Gemini 3.5 Flash (Low)" --dangerously-skip-permissions --print "These frames are from timestamps $START to $END. Identify: 1) What game is on screen? 2) What heroes/characters? 3) Is it gameplay, menu, or cutscene? 4) Notable events (fights, deaths, wins)." --add-dir workspace\frames
```

Key flags:
- `--model "Gemini 3.5 Flash (Low)"` — cheapest vision-capable model
- `--dangerously-skip-permissions` — required for non-interactive automation
- `--add-dir workspace\frames` — makes frames available to the agent
- `--print "prompt"` — single-shot query, returns text on stdout

## Parse Output

`agy` returns markdown text. If using structured output, request JSON format in the prompt:

```powershell
agy --model "Gemini 3.5 Flash (Low)" --dangerously-skip-permissions --print "For each frame, return JSON array: [{\"timestamp\": \"...\", \"game\": \"...\", \"heroes\": [\"...\"], \"activity\": \"...\", \"confidence\": 0-1}]" --add-dir workspace\frames
```

## Pipeline: Batch Frame Analysis

For covering a full video in chunks:

```powershell
# 1. Extract frames every 5 min
# 2. Group into batches of 6 frames (covering 30 min each)
# 3. Run agy on each batch
$batches = @()
# ... group logic ...
foreach ($batch in $batches) {
  $result = agy --model "Gemini 3.5 Flash (Low)" --dangerously-skip-permissions `
    --print "Analyze these $($batch.Count) frames spanning $($batch[0].ts) to $($batch[-1].ts): list game, activity, heroes for each." `
    --add-dir workspace\frames
  $result | Out-File -Append -Encoding UTF8 workspace\frame_analysis.txt
}
```

## Model Selection Guide

| Model | Quality | Cost | Use Case |
|-------|---------|------|----------|
| Gemini 3.5 Flash (Low) | Medium | Cheapest | Bulk frame scanning, game identification |
| Gemini 3.5 Flash (Medium) | Good | Moderate | Hero/character identification |
| Gemini 3.5 Flash (High) | Best | Expensive | Detail analysis, UI text reading |
| Gemini 3.1 Pro (Low) | High | Moderate | When Flash insufficient |

## Iron Rules

- Always use `--dangerously-skip-permissions` for automated batch processing
- Never trust frame-based identification blindly — cross-reference with transcript for hero/character names
- Extract frames at minimum 30s intervals — closer gaps don't improve analysis much
- If agy returns "cannot access file", the `--add-dir` flag is missing or path is wrong
- Frame quality matters: extract at `-q:v 2` (high) for readable UI text, `-q:v 5` is fine for game identification
