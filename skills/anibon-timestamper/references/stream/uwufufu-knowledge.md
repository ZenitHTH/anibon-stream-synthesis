---
name: anibon-uwufufu-knowledge
description: Reference guide for timestamping and topic summarization when speaker Boat from Anibon Official plays interactive UWUFUFU (Ideal Type World Cup / Tier List / Ranking tournament) streams.
---

# Anibon UWUFUFU Stream & Ideal Cup Knowledge Base

## Overview

This reference guide handles timestamping and topic summarization for **UWUFUFU (`uwufufu.com`) Ideal Type World Cup** and tier-list voting streams featuring speaker "Boat" (Pu Boat / ปู่โบ๊ต) from **Anibon Official**. 

During UWUFUFU streams, Boat engages in bracket-style 1-on-1 elimination voting (e.g. 64, 32, 16 rounds) on topics ranging from anime waifus/husbandos, VTubers, game characters, anime songs/OSTs, to food, memes, and tokusatsu.

---

## When to Use

- Directed here by `anibon-timestamper` orchestrator or `anibon-talk-stream` / `anibon-gaming-stream`.
- Chunk contains keyword signals: `UWUFUFU`, `uwufufu`, `World Cup`, `Ideal Cup`, `ศึกชิง`, `โหวต`, `รอบ 64`, `รอบ 32`, `รอบ 16`, `รอบ 8`, `รอบรอง`, `รอบชิง`, `แชมป์`, `คู่นี้`, `ตกรอบ`, `เลือก`.
- The speaker is actively comparing 2 choices on screen, discussing bracket progression, or revealing global stats on `uwufufu.com`.

---

## Tournament Structure & Timestamp Grouping Rules

### Macro Density Rule (CRITICAL)
> **DO NOT create a timestamp for every single 1-on-1 choice.** 
> In a 32-round or 64-round World Cup, creating 32+ timestamps creates extreme spam and violates macro density caps. 
> **Group bracket progress into 3–6 key milestone timestamps per tournament.**

### Standard Milestone Flow

| Stage | Tag | Description Pattern |
|---|---|---|
| **Topic Selection & Setup** | `[UWUFUFU]` | `[UWUFUFU] เริ่มเล่น Ideal Cup: [Topic Name] (รอบ [Size] คน)` |
| **Notable / Hot Match** | `[UWUFUFU]` | `[UWUFUFU] ศึกดุเดือด: [Candidate A] vs [Candidate B] - [Boat's Reaction / Hot Take]` |
| **Quarter / Semi-Finals** | `[UWUFUFU]` | `[UWUFUFU] รอบ [4 หรือ 8] คนสุดท้าย - ตัดสินคู่สำคัญ` |
| **Grand Finals** | `[UWUFUFU]` | `[UWUFUFU] รอบชิงชนะเลิศ: [Finalist A] vs [Finalist B]` |
| **Winner & Global Stats** | `[UWUFUFU]` | `[UWUFUFU] [Winner Name] คว้าแชมป์ + ดูผลโหวตสถิติโลก` |

---

## Thai Vocabulary & Keyword Dictionary

| Term / Audio Cue | English / Meaning | Usage in Timestamp |
|---|---|---|
| UWUFUFU / อูวูฟูฟู | `uwufufu.com` voting site | Baseline tag `[UWUFUFU]` |
| Ideal Cup / World Cup | World Cup bracket tournament | `[UWUFUFU] เล่น Ideal Cup...` |
| รอบ 64 / 32 / 16 / 8 | Round size (64, 32, 16, 8 entries) | State in tournament setup |
| รอบรอง / รอบรองชนะเลิศ | Semi-Finals (Top 4) | Milestone marker |
| รอบชิง / รอบชิงชนะเลิศ | Grand Final | Milestone marker |
| แชมป์ / ผู้ชนะ / Winner | Tournament Winner | Must state winner name in description |
| ตกรอบ / โดนคัดออก | Eliminated | Note when major favorite gets unexpectedly knocked out |
| ลังเล / เลือกยาก | Difficult decision / Hot debate | Note for highlighted match |
| ผลโหวต / สถิติ | Global win percentages & stats | End of tournament review |

---

## Timestamp Categories for UWUFUFU

- `[UWUFUFU]` — Primary tag for all bracket matches, selections, and tournament progression.
- `[Tierlist]` — When Boat creates or rates a tier list (S/A/B/C/D) on UWUFUFU.
- `[Reaction]` — Extreme hype, rage, or funny reaction to an unexpected match candidate or outcome.
- `[Talk]` — Digression into off-topic discussion sparked by a candidate on screen.

---

## Export Template Example

```markdown
01:15:00 - [UWUFUFU] เริ่มเล่น Ideal Cup: จัดอันดับตัวละครหญิง FGO (รอบ 32 คน)
01:22:45 - [UWUFUFU] ศึกดุเดือดรอบ 16 คน: Morgan vs Melusine - โบ๊ทเลือกยากจนต้องกุมหัว
01:38:10 - [UWUFUFU] รอบ 4 คนสุดท้าย: ตัดสินผู้เข้ารอบชิง
01:45:30 - [UWUFUFU] รอบชิงชนะเลิศ: Ereshkigal vs Ishtar
01:50:12 - [UWUFUFU] Ereshkigal คว้าแชมป์อันดับ 1 + สรุปผลโหวตสถิติจากผู้เล่นทั่วโลก
```

---

## Iron Rules

1. **Always Name the Winner**: The final timestamp of any UWUFUFU tournament MUST explicitly state the winning character/item (`[Winner Name] คว้าแชมป์`).
2. **Exact Character / Item Names**: Spell candidate names accurately (use Thai transliteration or canonical English/Japanese). Do not misspell character names.
3. **Macro Density Enforcement**: Maximum 6 timestamps per UWUFUFU tournament. Never spam per-match timestamps.
4. **Capture Boat's Hot Takes**: If Boat goes on a passionate rant about why candidate X is superior to candidate Y, summarize the reasoning in one concise sentence (e.g. `[UWUFUFU] โบ๊ทอธิบายเหตุผลที่เลือก X เหนือ Y`).
