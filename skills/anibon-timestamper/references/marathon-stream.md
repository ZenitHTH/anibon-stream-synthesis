---
name: anibon-marathon-stream
description: Use when processing a live stream or specific video chunk where the speaker switches between multiple games in one session (Multi-game marathon).
---

# Anibon Marathon Stream

## Overview
This skill handles the timestamping for Multi-Game Marathons, ensuring that transitions between different games are clearly marked with visual section headers.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk of a transcript where the speaker explicitly transitions from playing one game to another.

## Behaviors & Rules

### 1. Game Section Headers
Insert visual dividers between game segments to clearly separate the timeline:
```
═══════════════════════════
  🎬 Opening (For the initial stream greeting and lineup announcement)
═══════════════════════════
00:00:00 - [Greeting] สวัสดีครับ
00:05:00 - [Talk] พูดถึงเกมที่จะเล่นวันนี้

═══════════════════════════
  🎮 Game Name
═══════════════════════════
```
- Place headers at the moment the speaker **starts actually playing** the new game (not when they announce it).
- For non-game intermissions, you can use a similar format (e.g., `☕ Break`).

### 2. Transition Handling
When Boat switches games, the old game may still be on screen while he discusses it. Ensure timestamps reflect the reality of the switch:
- Timestamp the **verbal announcement** of switching: `HH:MM:SS - [Transition] ประกาศเปลี่ยนเกม → [New Game]`
- Timestamp the **actual gameplay start** of the new game: `HH:MM:SS - [Gameplay] เริ่มเล่น [New Game]`
- Discussion about the previous game during the loading screen is `[Talk]`, NOT `[Gameplay]`.

### 3. Consistent Depth Across Games
Aim for proportionally similar timestamp density across all game segments. Don't produce 15 timestamps for the first game and 3 for the last. Adjust depth based on segment length.

### 4. Chronological Layout
Keep timestamps chronological within each game section. The game section headers are visual aids — timestamps still flow top-to-bottom by time.

## Export Template
```
═══════════════════════════
  🎮 Zenless Zone Zero
═══════════════════════════
00:15:00 - [Gameplay] เริ่มเล่น ZZZ ทำเดลี่
00:45:00 - [Event] เข้าอีเวนต์ใหม่
01:28:00 - [Transition] ประกาศเปลี่ยนเกม → Monster Hunter Wilds
═══════════════════════════════════
  🎮 Monster Hunter Wilds
═══════════════════════════════════
01:35:00 - [Gameplay] เริ่มเล่น Monster Hunter Wilds
```

## Iron Rules
- **Consistent depth in multi-game streams**: Maintain proportionally similar density across all game segments.
- **Header Placement**: Game headers go immediately before the exact moment actual gameplay begins, NOT at the transition announcement.
