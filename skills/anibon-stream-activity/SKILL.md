---
name: anibon-stream-activity
description: Download high-resolution YouTube storyboards (sb3/sb2), detect on-screen activity, webcam presence/AFK, and facial emotions to provide visual grounding for Anibon livestream timestamping.
---

# Anibon Stream Activity & Visual Grounding

## Overview

Tracks what speaker "Pu Boat" (โบ๊ต / PhuBoat) is doing on screen and in his webcam throughout an Anibon Official live stream. Solves the **Speech vs. Action Divergence** problem where the speaker discusses real-world topics while casually playing a game or browsing the web.

## When to Use

- Live streams featuring Pu Boat where he plays games, browses websites/reviews, reacts to videos, or pulls gacha.
- When `anibon-timestamper` needs visual ground truth to prevent hallucinated in-game lore, resolve deictic pronouns (*"ดูอันนี้ดิ"*, *"เกมนี้"*), and ground AFK breaks.
- In multi-hour streams where speaker leaves the desk (AFK empty chair detection).

---

## Storyboard Resolution & Download

Always download the highest-resolution storyboard tier available to avoid pixelation and blur when inspecting UI text, character names, or facial expressions:

```bash
# Downloads highest resolution storyboard (sb3 -> sb2 -> sb1 -> sb0)
yt-dlp -f "sb3/sb2/sb1/sb0" "https://www.youtube.com/watch?v=VIDEO_ID" -o "<workspace>/frames/storyboard.%(ext)s"
```

---

## Pipeline & Helper Scripts

All helper scripts reside in `skills/anibon-stream-activity/scripts/`:

### 1. Unpack Storyboard Slides (`unpack_storyboard.py`)

Extracts clean native JPEG slide sheets from MHTML and provides frame cropping across arbitrary grid sizes (3x3, 5x5, 10x10):

```bash
python3 scripts/unpack_storyboard.py \
  --mhtml "<workspace>/frames/storyboard*" \
  --out-dir "<workspace>/frames/slides"
```

### 2. Extract Activity & Webcam Timeline (`extract_activity_timeline.py`)

Samples storyboard frames every 60–90 seconds + scene change shifts, runs Gemini Vision / `agy` classification, and merges into continuous time intervals:

```bash
python3 scripts/extract_activity_timeline.py \
  --slides-dir "<workspace>/frames/slides" \
  --duration <DURATION_SECONDS> \
  --step-sec 60 \
  -o "<workspace>/activity_timeline.json"
```

**Output Schema (`activity_timeline.json`):**
```json
[
  {
    "start": "00:15:00",
    "end": "00:45:00",
    "start_sec": 900,
    "end_sec": 2700,
    "app_or_game": "Monster Hunter Wilds",
    "category": "Gameplay",
    "details": "Hunting Dosshaguma in Windward Plains",
    "webcam": {
      "speaker_present": true,
      "expression": "focused",
      "layout": "corner_cam"
    }
  }
]
```

### 3. Align to Transcript Chunks (`align_activity_timeline.py`)

Maps activity intervals across 5-minute transcript chunks:

```bash
python3 scripts/align_activity_timeline.py \
  --timeline "<workspace>/activity_timeline.json" \
  --chunks "<workspace>/chunks/" \
  -o "<workspace>/activity/"
```

Emits `<workspace>/activity/activity_chunk_NN.txt` ready for subagent prompt injection.

---

## Disambiguation & Subagent Reasoning Rules

When injecting `ON_SCREEN_ACTIVITY` into `anibon-chunk-timestamper`, subagents MUST apply these rules:

1. **Divergence Rule (Speech ≠ Screen Action)**:
   - When dialogue covers general topics (life stories, food, news, anime lore) while casually playing or farming:
     - Use speech-primary tag: `[Talk]`, `[News]`, or `[Question]`.
     - Suffix the background game in parentheses: `[Talk] เม้าท์มอยเรื่อง... (ระหว่างเล่น Monster Hunter)`.
     - **NEVER** fabricate or hallucinate real-life stories as in-game lore or quest text.
2. **Convergence Rule (Speech = Screen Action)**:
   - When dialogue actively reacts to in-game combat, boss mechanics, or gacha:
     - Use action tag: `[Gameplay]`, `[Gacha]`, or `[Reaction]`.
3. **Webcam & AFK Grounding**:
   - When `speaker_present: false` (empty chair / away from desk) and audio is silent or ambient:
     - Tag as `[AFK] ปู่โบ๊ตลุกไปพักเบรก / เข้าห้องน้ำ` if > 2 minutes.
     - Explains silent gaps cleanly and prevents false topic switching.
4. **Physical Emotion Grounding**:
   - Cross-reference webcam expression (`laughing`, `shocked_facepalm`) with LiveChat `555` bursts to accurately calibrate tone in descriptions.
5. **Deictic Pronoun Grounding**:
   - Resolve *"ดูนี่ดิ"*, *"เกมนี้"*, *"ตัวนี้"* using the `app_or_game` name and visible UI text in `ON_SCREEN_ACTIVITY`.
