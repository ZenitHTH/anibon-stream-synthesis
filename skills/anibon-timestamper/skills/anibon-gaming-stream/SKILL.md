---
name: anibon-gaming-stream
description: Use when processing a live stream or specific video chunk where the speaker is playing a single game with sparse verbal reactions (Dedicated gaming).
---

# Anibon Gaming Stream

## Overview
This skill handles the timestamping for "dedicated gaming" chunks of a video or live stream, particularly for speaker "Boat" from Anibon Official. It focuses on gameplay-event detection rather than conversation analysis.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk of a transcript where the speaker is actively playing a game, exploring, fighting bosses, or making game-related discoveries.

## Behaviors & Rules

### 1. Gameplay Event Detection
Instead of topic-flow analysis, detect these specific gameplay milestones:
- **Area transitions** — moving to new zones, maps, levels
- **Boss encounters** — entering boss fights, mini-bosses
- **Deaths/wipes** — only timestamp memorable/funny deaths, not every single one (look for "555", "lol", or rage)
- **Victories** — clearing bosses, completing quests, achievements
- **Discoveries** — finding hidden areas, NPCs, items worth noting
- **Reactions** — strong verbal reactions (laughing, shouting, celebrating)

### 2. Categories
Use these specific gaming categories instead of generic labels:
- `[Gameplay]` — General gameplay, exploration, missions (Note: Use `[Gameplay] (First Time)` if it's the first time playing a game)
- `[Boss]` — Boss encounters, boss fights, challenging enemies
- `[Death]` — Notable deaths, wipes, funny fails
- `[Victory]` — Clearing a boss, completing a quest, significant achievements
- `[Gacha]` — Gacha pulls, loot boxes (NEVER reveal results; summarize briefly if there are many pulls)

### 3. Timestamp Density & Gaps
- **Target Density**: Target ~1 timestamp per 8-15 minutes during active gameplay (lower density than talk segments).
- **Handling Gaps**: Silent gameplay stretches of 15-30+ minutes are **expected** when the speaker plays silently. Instead of inserting forced entries, add a **single continuity marker** at the midpoint: `HH:MM:SS - [Gameplay] ยังเล่น [Game Name] ต่อ` so viewers know the timestamp list isn't broken. For very long gaps (>45 mins), insert at most 2 continuity markers evenly spaced to avoid clutter.

### 4. Boss Fight Lifecycle Grouping
A boss attempt arc (encounter → die → retry → die → win) should be grouped logically:
- Timestamp the **first encounter** and the **final result** (victory or give-up).
- Only add intermediate deaths if they're **funny or memorable** (e.g., instant one-shot death, rage moment).
- Do NOT timestamp every single retry.

### 5. Game-Specific Research
For non-FGO games, research boss names, area names, and in-game terms via:
- Game-specific wikis (e.g., Fandom wikis, game subreddits)
- [SteamDB Search](https://steamdb.info/search/?a=app&q=&type=1&category=0) for game name verification
- Official game websites or social media

## Export Template
```
00:00:00 - [Greeting] เปิดไลฟ์ แจ้งว่าจะเล่น Elden Ring
00:05:00 - [Gameplay] เริ่มเล่น เข้าด่านใหม่
00:25:00 - [Boss] เจอบอส Margit เริ่มสู้
00:27:30 - [Death] ตายครั้งแรก โดนจับคอมโบ 555
00:35:00 - [Victory] ชนะบอส Margit ได้!
00:50:00 - [Gameplay] ยังเล่น Elden Ring ต่อ — สำรวจ Stormveil Castle
```

## Iron Rules
- **NEVER spoil gacha results**: Preserve the excitement of card pulls. NEVER include pull results in Timestamp headings.
- **Use gameplay continuity markers**: For silent gameplay gaps of 15+ minutes, insert a single `[Gameplay] ยังเล่น [Game Name] ต่อ` continuity marker.
- **Proper names must be exact**: Search via Google/SteamDB before finalizing any boss or area name.
