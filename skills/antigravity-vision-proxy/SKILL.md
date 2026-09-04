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

### Modality Comparison: Text-Only vs. Text + Vision

| Dimension | Text-Only (ASR + LiveChat) | Text + Vision (Storyboard / Frames) |
| :--- | :--- | :--- |
| **Latency & Cost** | ⚡ Extremely fast, low token cost | ⏱ Moderate (requires `sb0` download ~15MB + frame crops) |
| **Conversational Depth** | 🎯 Captures opinions, jokes, nuances, banter | ❌ Cannot hear reasoning or intent |
| **Proper Noun Accuracy** | ⚠️ Susceptible to ASR phonetic corruption | 🎯 Exact on-screen title cards, logos, and UI text |
| **Deictic Pronouns ("อันนี้/เกมนี้")** | ⚠️ Ambiguous without spoken name | 🎯 Immediately resolves target on screen |
| **Silent / Montage Gameplay** | ❌ Fails when streamer is quiet | 🎯 Accurately tracks game state and action |

### Decision Framework: When to Invoke Vision

Apply the **Gated Trigger Rule** — do not call vision on every chunk:

1. **GATED TRIGGER 1: Ambiguous Deictic Pronouns**
   - Streamer talks about "เกมนี้", "ตัวนี้", "คลิปนี้", "ดูอันนี้" with high engagement, but no explicit title is spoken within ±30s.
2. **GATED TRIGGER 2: Unresolved Proper Nouns / ASR Garbled Candidates**
   - `garbled_notes.json` candidates with `correct: null` (e.g. Whisper phonetic mess like *"ดัซบลาโด"* -> *DUSKBLOODS*, *"fet bate zี"* -> *Phantom Blade Zero*).
3. **GATED TRIGGER 3: Game / Activity Transition Boundaries**
   - Precise second where a game launches or title card appears (e.g., verifying exact NES/SNES game title from menu).
4. **GATED TRIGGER 4: Silent / Low-Speech High-Activity Pulses**
   - `MEME_PULSE` or high LiveChat chat burst where transcript has < 5 spoken lines.
5. **GATED TRIGGER 5: Explicit User Verification Request**
   - User asks to verify with vision (`/btw i want you to use vision`, `--vision`, `ลองใช้ vision ตรวจเช็คดูสิ`).
6. **GATED TRIGGER 6: Numerical, Campaign, or Proper Noun Discrepancies**
   - Streamer stumbles over numbers (e.g. Japanese `万` (10,000) vs "ล้าน", slurring "3,500 ล้าน / 30,000 กว่าล้าน"), or LiveChat shows real-time viewer corrections (e.g. chat teasing *"35 ล้านพอปู่"*).

**BYPASS (Stay Text-Only):**
- Static podcast/talk segments, opinion sharing, news reading where streamer reads headlines verbatim, or games already 100% confirmed by audio and TF-IDF signals.

## Frame Extraction

### Option A: High-Resolution YouTube Storyboard (`sb3`/`sb2`/`sb1`/`sb0`) — Preferred for Whole Streams (No full video download, ~15-40MB total)

```bash
# 1. Download highest available resolution storyboard mhtml
yt-dlp -f "sb3/sb2/sb1/sb0" "https://www.youtube.com/watch?v=VIDEO_ID" -o "frames/storyboard.%(ext)s"

# 2. Unpack clean MHTML slides & crop high-res frame using unpack_storyboard.py
python3 ../anibon-stream-activity/scripts/unpack_storyboard.py \
  --mhtml "frames/storyboard*" \
  --out-dir "frames/slides" \
  --crop-sec 597 \
  --duration <DURATION_SEC> \
  --out-crop "frames/frame_00_09_57.jpg"
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

### Option C: Targeted High-Res Video Section Slicing (`yt-dlp --download-sections`) — Best for Spot Inspections (~2-3s download)

When inspecting a specific time range (1–10 minutes) for banners, kanji, UI text, or chat overlays, download the exact section directly:

```bash
# 1. Download targeted 720p clip (instant ~2-3s download, bypassing 403 via Chrome cookies)
yt-dlp --cookies-from-browser chrome \
  --download-sections "*00:08:30-00:15:30" \
  -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  -o "target_slice.mp4" "https://www.youtube.com/watch?v=VIDEO_ID"

# 2. Extract crystal-clear frame at exact offset
ffmpeg -ss 00:01:15 -i target_slice.mp4.webm -frames:v 1 -q:v 2 target_frame.jpg -y
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
