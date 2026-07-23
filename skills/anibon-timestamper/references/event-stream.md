---
name: anibon-event-stream
description: Use when processing a live stream or specific video chunk covering a newly released game event or update (Game Event Launch).
---

# Anibon Event Stream

## Overview
This skill handles the timestamping for Game Event Launches. These streams are characterized by dense terminology, reading of patch notes, team theorycrafting, and rapid activity switching.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk of a transcript where the speaker is exploring brand-new content, reading official update details, or analyzing new characters/mechanics.

## Behaviors & Rules

### 1. Activity-Mode Detection
Distinguish and label these interleaved activities separately:
- **Reading patch notes** → `[Patch Notes]` — speaker is displaying/reading official update info
- **Playing the event** → `[Event]` or `[Gameplay]` — speaker is actively doing event quests
- **Theorycrafting** → `[Theorycrafting]` — speaker is analyzing, comparing, building teams
- **Community reaction** → `[Talk]` — discussing what other players/community think

### 2. Rapid Context Switching
When activities alternate every 2-3 minutes (e.g., read → play → discuss → read), timestamp each switch. High density is acceptable and expected for launch-day content. The standard "limit stamp density" guideline used for normal gaming streams is relaxed here.

### 3. Verification Fallback Chain
Launch day content often doesn't exist in wikis or databases yet. If a term or name is unknown:
1. Try official API (Atlas Academy for FGO, etc.).
2. Try social media / game news sites (Twitter/X, Facebook, official announcements).
3. **Use the speaker's own words from on-screen text** (this IS verified — the game is showing it, even if no external database has the data yet. This is NOT guessing).
4. Only mark as `[unfamiliar/unresearchable]` if the term is unclear even in context.

## Export Template
```
00:03:00 - [Patch Notes] เปิดอ่าน patch notes อีเวนท์ใหม่
00:10:00 - [Theorycrafting] วิเคราะห์สกิลเซ็ตของเซอร์แวนท์ใหม่
00:15:00 - [Event] เริ่มเล่นอีเวนท์ Main Quest
00:22:00 - [Theorycrafting] หยุดเล่น วิเคราะห์ทีมใหม่
```

## Iron Rules
- **Proper names must be exact**: For launch-day content, follow the verification fallback chain closely. The speaker's reading of on-screen text acts as a primary verified source when wikis are empty.
- **Do not guess**: If a term is unresearchable and not visible on screen, mark it explicitly rather than hallucinating a spelling.
