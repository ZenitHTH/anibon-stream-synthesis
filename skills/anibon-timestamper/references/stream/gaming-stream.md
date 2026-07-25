---
name: anibon-gaming-stream
description: Use when processing a chunk where the speaker is actively playing a game — exploring, fighting bosses, grinding, or reacting to gameplay. Do NOT use for talk-over-game chunks where Boat monologues dominate; load anibon-talk-stream alongside this skill.
---

# Anibon Gaming Stream

## Overview
This skill handles timestamping for "dedicated gaming" chunks of a video or live stream, particularly for speaker "Boat" from Anibon Official. It focuses on gameplay-event detection rather than conversation analysis.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk where the speaker is actively playing a game, exploring, fighting bosses, or making game-related discoveries.

## Behaviors & Rules

### 1. Gameplay Event Detection
Instead of topic-flow analysis, detect these specific gameplay milestones:
- **Area transitions** — moving to new zones, maps, levels
- **Boss encounters** — entering boss fights, mini-bosses
- **Deaths/wipes** — only memorable/funny deaths (look for "555", rage quit, chat flooding)
- **Victories** — clearing bosses, completing quests, significant achievements
- **Discoveries** — finding key items, prosthetics, hidden NPCs worth noting
- **Reactions** — strong verbal reactions (screaming, celebrating, tilting hard)

**SKIP these — they are NOT timestamp-worthy:**
- Reading in-game tips or tutorials
- Upgrading skills at the sculptor / idol
- Talking to the same NPC repeatedly
- Routine farming runs
- Every individual death in a long boss attempt arc
- Minor exploration with no discovery

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
- **Handling Gaps**: Silent gameplay stretches of 15–30+ minutes are **expected** when the speaker plays silently. Insert a continuity marker `HH:MM:SS - [Gameplay] ยังเล่น [Game Name] ต่อ` **ONLY** when ALL of the following are true:
  1. The gap is **≥15 minutes** with no milestone event.
  2. The stretch contains **no interesting activity** — if the player is farming, grinding, or doing routine play with nothing notable, output **0 timestamps** (skip the marker entirely).
  3. The gap would otherwise confuse a viewer into thinking the timestamp list is broken.
  For very long gaps (>45 mins), insert at most 2 markers evenly spaced. Never insert a continuity marker just to fill space.

### 4. Boss Fight Lifecycle Grouping

A boss attempt arc (encounter → die → retry → die → win) is **ONE story arc**, not multiple timestamps.

- Timestamp the **first encounter** with `[Boss]` (include correct verified boss name)
- Add `[Death]` ONLY for truly memorable deaths (one-shot, rage quit, chat floods "555", "5555")
- Timestamp the **final result** with `[Victory]` when boss is cleared
- Do NOT timestamp every retry, every death, every HP check, every "almost had it"

**Real failure case — before fix (Part 3 of sdVOysOTjNc had 19 entries in ~1hr):**
```
01:32:21 - [Gaming] ต่อสู้กับบอส Ashigenjiro          ← wrong tag + wrong name
01:34:38 - [Gaming] ได้รับแขนกนินจา                  ← part of same arc, skip
01:43:11 - [Gaming] พบศาลเจ้า                        ← noise, skip
01:43:50 - [Gaming] ต่อสู้กับไก่                      ← noise, skip
01:45:19 - [Gaming] อ่านคำแนะนำการรับมือการโจมตีถึงชีวิต ← reading tip, skip
01:57:01 - [Gaming] พลาดท่าเสียชีวิต                 ← routine death, skip
```

**Correct (lifecycle grouped, density enforced):**
```
01:32:21 - [Boss] เผชิญหน้าบอส Ashina Genichiro ในบทนำ
01:48:13 - [Gameplay] สำรวจพื้นที่รอบนอกปราสาทอาชินะ สะสมลูกประคำ
02:04:11 - [Boss] เผชิญหน้ายักษ์แดง (Chained Ogre)
```

**Note on proper names:** Boss names must be verified. `Ashigenjiro` ≠ `Ashina Genichiro`. `โอนิเกียบุบุ` ≠ `Gyoubu Masataka Oniwa`. Use the in-game English name (check Fandom wiki) when Thai transcription is phonetically garbled.

### 5. Game-Specific Research (MANDATORY)
Before writing any boss or area name, verify it:
- **Fandom wikis** (search `[game name] wiki fandom`) — boss names, area names, item names
- **SteamDB** — game title verification
- **Official game website** — patch notes for recent content

**Self-check before submitting any name:** Is this the exact in-game English name, or a Thai phonetic guess? If you didn't look it up, look it up now.

## Export Template
```
00:00:00 - [Greeting] เปิดไลฟ์ แจ้งว่าจะเล่น Elden Ring
00:05:00 - [Gameplay] เริ่มเล่น เข้าด่านใหม่
00:25:00 - [Boss] เจอบอส Margit the Fell Omen เริ่มสู้
00:27:30 - [Death] ตายครั้งแรก โดนจับคอมโบ 555
00:35:00 - [Victory] ชนะบอส Margit the Fell Omen ได้!
00:50:00 - [Gameplay] ยังเล่น Elden Ring ต่อ — สำรวจ Stormveil Castle
```

## Pre-Submit Self-Check Ritual

Before handing back results, count your timestamps and verify:

1. **Tag check**: Any `[Gaming]`? → Replace every one. Zero allowed.
2. **Density check**: Total timestamps ÷ total hours ≈ 1 per 8–15 min? More than that → merge or delete.
3. **Boss arc check**: Every `[Boss]` has a matching `[Victory]` in the same session? No orphaned arcs?
4. **Noise check**: Any entry for: tip reading, skill upgrade, shrine visit, idle death, routine exploration? → Delete.
5. **Name check**: Every boss and area name verified against Fandom wiki? Thai phonetic spelling alone is not acceptable.

## Rationalization Red Flags — STOP if you think any of these

| Thought | Why it's wrong |
|---|---|
| "This tip-reading moment is important for viewers" | Tip reading = noise. Not a milestone. Skip it. |
| "I'll use `[Gaming]` this once because it fits better" | There is no case where `[Gaming]` fits. Pick `[Gameplay]`, `[Boss]`, `[Death]`, or `[Victory]`. |
| "The death was notable because Boat got frustrated" | Frustration ≠ memorable. Only timestamp if chat exploded or Boat quit and restarted. |
| "There's a gap so I should insert a continuity marker" | Continuity markers are for gaps with NO activity that would confuse the viewer. If the player is just farming, grinding, or doing routine play → output 0 timestamps, no filler. |
| "I need more entries to cover this long section" | Add a continuity marker `[Gameplay] ยังเล่น X ต่อ`, not fake milestone entries. |
| "I don't have time to look up the boss name" | A wrong name is worse than a placeholder. Look it up. |
| "The boss attempt started in chunk A and ended in chunk B" | Orchestrator merges across chunks. Mark `[Boss]` in chunk A, `[Victory]` in chunk B. They will pair correctly. |

## Iron Rules
- **`[Gaming]` tag FORBIDDEN**: Zero exceptions. Replace with `[Gameplay]`, `[Boss]`, `[Death]`, or `[Victory]`.
- **1 timestamp per 8–15 mins**: Do NOT emit one for every skill upgrade, NPC talk, or death attempt.
- **Boss lifecycle = 1 arc**: Only `[Boss]` first encounter + `[Victory]` final result. `[Death]` only if memorable.
- **NEVER spoil gacha results**: Preserve excitement. NEVER include pull results in timestamp headings.
- **Continuity markers only when necessary**: Only insert `[Gameplay] ยังเล่น [Game Name] ต่อ` when gap ≥15 min AND the stretch is not boring farming/grinding. If the activity is uninteresting, output 0 timestamps — no filler entries. Max 2 markers per 45-min gap.
- **Proper names must be verified**: Search Fandom wiki before finalizing. Thai phonetic transcription alone is insufficient.
