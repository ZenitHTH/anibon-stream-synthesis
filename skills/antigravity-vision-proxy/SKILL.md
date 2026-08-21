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
   - User asks to verify with vision (`/btw i want you to use vision`, `--vision`).

**BYPASS (Stay Text-Only):**
- Static podcast/talk segments, opinion sharing, news reading where streamer reads headlines verbatim, or games already 100% confirmed by audio and TF-IDF signals.

## Frame Extraction

### Option A: Lightweight YouTube Storyboard (`sb0`) — Preferred for YouTube (No full video download, ~15MB total)

```bash
# 1. Download storyboard mhtml (covers entire multi-hour stream in ~15MB)
yt-dlp -f sb0 "https://www.youtube.com/watch?v=VIDEO_ID" -o "frames/storyboard.%(ext)s"

# 2. Unpack clean MHTML slides (robust binary JPEG extraction)
python3 -c "
import glob, os
mhtml = glob.glob('frames/storyboard*')[0]
slides_dir = 'frames/slides'
os.makedirs(slides_dir, exist_ok=True)
with open(mhtml, 'rb') as f:
    data = f.read()
parts = data.split(b'--')
valid_count = 0
for p in parts:
    if b'image/jpeg' in p:
        idx = p.find(b'\xff\xd8')
        end_idx = p.rfind(b'\xff\xd9')
        if idx != -1:
            valid_count += 1
            jpg_data = p[idx:end_idx+2] if end_idx != -1 else p[idx:]
            with open(f'{slides_dir}/slide_{valid_count:03d}.jpg', 'wb') as out:
                out.write(jpg_data)
print(f'Extracted {valid_count} clean slides.')
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
