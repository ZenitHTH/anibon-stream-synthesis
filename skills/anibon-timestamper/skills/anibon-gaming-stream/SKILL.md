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

> **⛔ FORBIDDEN TAG: `[Gaming]` must NEVER be used.** It is a generic label that violates this skill. Any timestamp using `[Gaming]` is wrong — replace with the correct tag below.

Use these specific gaming categories instead of generic labels:
- `[Gameplay]` — General gameplay, exploration, missions (Note: Use `[Gameplay] (First Time)` if it's the first time playing a game)
- `[Boss]` — Boss encounters, boss fights, challenging enemies
- `[Death]` — Notable deaths, wipes, funny fails (only if funny/memorable — NOT every death)
- `[Victory]` — Clearing a boss, completing a quest, significant achievements
- `[Gacha]` — Gacha pulls, loot boxes (NEVER reveal results; summarize briefly if there are many pulls)

**Mapping rule:** When converting existing `[Gaming]` timestamps, ask: what is the *primary event*?
- Starting/exploring a new area → `[Gameplay]`
- Entering boss room → `[Boss]`
- Character died → `[Death]` (only if notable)
- Boss/quest cleared → `[Victory]`
- Skill unlock, item found, NPC talk → `[Gameplay]`

### 3. Timestamp Density & Gaps

**Target Density: 1 timestamp per 8–15 minutes. No exceptions.**

- Do NOT emit timestamps for: reading tips, upgrading skills, talking while farming, minor NPC dialogue, routine exploration, every individual death in a boss attempt arc.
- For a 5-minute chunk: emit 0–1 timestamps. 2 is MAX and only when two truly distinct events occur.
- **Handling Gaps**: Silent gameplay stretches of 15–30+ minutes are **expected** when the speaker plays silently. Instead of inserting forced entries, add a **single continuity marker** at the midpoint: `HH:MM:SS - [Gameplay] ยังเล่น [Game Name] ต่อ` so viewers know the timestamp list isn't broken. For very long gaps (>45 mins), insert at most 2 continuity markers evenly spaced to avoid clutter.

### 4. Boss Fight Lifecycle Grouping

A boss attempt arc (encounter → die → retry → die → win) is **ONE story arc**, not multiple timestamps.

- Timestamp the **first encounter** with `[Boss]`: e.g., `[Boss] เจอบอส Genichiro เริ่มสู้`
- Add `[Death]` ONLY for funny/memorable deaths (one-shot, rage quit, chat reacts "555")
- Timestamp the **final result** with `[Victory]` when boss is cleared: e.g., `[Victory] ชนะบอส Genichiro ได้สำเร็จ`
- Do NOT timestamp every single retry, every death in a long boss session, every HP check.

**Example — bad (too dense):**
```
01:32:21 - [Gaming] ต่อสู้กับบอส
01:34:38 - [Gaming] ตายครั้งแรก
01:37:00 - [Gaming] ลองใหม่
01:40:00 - [Gaming] ตายอีกครั้ง
01:43:00 - [Gaming] ชนะบอส
```

**Example — correct (lifecycle grouped):**
```
01:32:21 - [Boss] เจอบอส Ashigenjiro เริ่มสู้
01:43:00 - [Victory] ชนะบอส Ashigenjiro ได้สำเร็จ
```

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
- **`[Gaming]` tag FORBIDDEN**: Never use. Replace with `[Gameplay]`, `[Boss]`, `[Death]`, or `[Victory]`.
- **1 timestamp per 8–15 mins**: Do NOT emit one for every skill upgrade, NPC talk, or death attempt.
- **Boss lifecycle = 1 arc**: Only `[Boss]` first encounter + `[Victory]` final result. `[Death]` only if memorable.
- **NEVER spoil gacha results**: Preserve excitement of card pulls. NEVER include pull results in timestamp headings.
- **Use gameplay continuity markers**: For silent gameplay gaps of 15+ minutes, insert single `[Gameplay] ยังเล่น [Game Name] ต่อ` continuity marker.
- **Proper names must be exact**: Search via Google/SteamDB before finalizing any boss or area name.
