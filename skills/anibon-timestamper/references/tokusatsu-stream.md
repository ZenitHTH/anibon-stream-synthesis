---
name: anibon-tokusatsu-stream
description: Use when processing a live stream or specific video chunk where the speaker is discussing tokusatsu (Kamen Rider, Super Sentai, Ultraman, etc.) with guests/co-hosts, or hosting a watch party for a tokusatsu episode.
---

# Anibon Tokusatsu Stream

## Overview
This skill handles timestamping for tokusatsu discussion streams and watch-party sessions featuring speaker "Boat" from Anibon Official, often joined by guests or co-hosts. These streams mix episode reactions, franchise lore debates, news discussions, and live fan Q&A.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- The chunk contains tokusatsu franchise names, character names, series titles, or actor names.
- The stream format is a **panel discussion** (2+ speakers) or a **watch party** (speakers react to a playing episode in real time).

---

## Situation Awareness

### Watch Party vs. Discussion — How to Tell
| Signal | Situation |
|---|---|
| Speakers fall silent, reactions like "โห!", "ว้าว", "อ้าว" in bursts | **Watch party** — episode is playing |
| Long continuous turns of speech, debate, explanation | **Discussion / panel** |
| Both patterns alternate | **Hybrid** — mark each clearly |

### Guest/Co-host Handling
- When a guest speaks, note them if their name is mentioned on stream (e.g., `[Talk] Boat + [GuestName] คุยเรื่อง...`).
- If the guest name is unclear, use `[Talk] Boat + Guest`.
- Do NOT invent guest names. Leave blank if truly unidentifiable.

---

## Tokusatsu Knowledge Base

### Major Franchises & Their Thai Fandom Names
| Franchise | Common Thai fan shorthand | Notes |
|---|---|---|
| Kamen Rider | มาสค์ไรเดอร์ / ไรเดอร์ | Long-running Toei franchise since 1971 |
| Super Sentai | เซนไต / ซุปเปอร์เซนไต | Source of Power Rangers adaptations |
| Ultraman | อุลตร้าแมน | Tsuburaya Productions franchise |
| Metal Heroes | เมทัลฮีโร่ | Older Toei franchise (Space Sheriff series, B-Fighter) |
| Garo | กาโร่ | Dark/adult tokusatsu by Keita Amemiya |
| Avataro Sentai Donbrothers | ดอนบราเธอร์ส | Known for experimental non-linear storytelling |

### Franchise Knowledge Base References
For detailed lists of series, terms, and context, see the following references:
- **[Kamen Rider Series & Lore](references/Kamen_Rider.md)**
- **[Super Sentai & Project R Terms](references/Super_Sentai.md)**
- **[Ultraman Key Terms](references/Ultraman.md)**
- **[Gridman Universe Lore](references/Gridman.md)**

### Common Tokusatsu Discussion Topics (Boat streams)
- Henshin (変身) transformation sequence quality debates
- Suit design ranking / tier lists
- "Kamen Rider BLACK is the best Showa Rider" — recurring hot take
- Crossover movies (Super Hero Taisen, etc.)
- Casting controversies or actor news (e.g. Toei labor issues or Tsuburaya layoffs)
- Thai dub vs. Japanese original debate
- "Gaim is the GOAT" — another recurring opinion
- Watch-party episodes from ongoing seasonal series
- DX Toys (ของเล่น DX) vs. Shokugan/Gashapon collector debates

### Thai Tokusatsu Vocabulary
| Thai term | Meaning |
|---|---|
| เฮนชิน | Henshin — transform |
| ไรเดอร์เข็มขัด | Rider Belt (henshin device) |
| คาอิจู / มอนสเตอร์ | Kaiju / monster |
| ฟอร์ม | Rider/Sentai form change (e.g.,ร่างพัฒนา, ร่างสุดยอด) |
| ฟินเนลฟอร์ม / ไคเมอร์ฟอร์ม | Final Form |
| ไซด์บาสเตอร์ / สปีเชียลอแทค | Finishing move / special attack |
| ซีซั่น / ไรด้าใหม่ | New seasonal Rider or Sentai |
| ดูพร้อมกัน / ดูด้วยกัน | Watch party |
| ตอนนี้ / EP นี้ | This episode |
| การ์ตูนคลับ / Flixer / Dex | Cartoon Club, Flixer, Dex Club (major Thai tokusatsu distributors) |
| ของเล่น DX | Deluxe toys (e.g., เข็มขัดแปลงร่าง DX, หุ่นยนต์ DX) |
| สุ่มกล่อง / โชกัง / กาชา | Shokugan (Candy toys) / Gashapon |

---

## Timestamp Categories

Use these labels for watch-party and discussion streams:

| Tag | When to use |
|---|---|
| `[WatchParty]` | Speakers are reacting to a live/recorded episode playback |
| `[Reaction]` | Strong emotional reaction moment (shock, hype, laugh) during watch party |
| `[Discussion]` | Panel debate, franchise comparison, lore analysis |
| `[Review]` | Post-episode evaluation or rating |
| `[News]` | Tokusatsu casting news, new series announcement, toy/merch releases |
| `[Lore]` | Deep-dive into franchise history, timeline, or canon debate |
| `[Tierlist]` | Ranking Riders, forms, suits, series, etc. |
| `[Q&A]` | Answering viewer questions about tokusatsu |
| `[Talk]` | Off-topic digression from tokusatsu into general chat |
| `[Greeting]` | Stream open / intro |
| `[Break]` | Stream break |

---

## Watch Party Rules

- **Episode boundary**: When a new episode starts playing, mark it with `[WatchParty] ดู [SeriesName] EP[N]`.
- **Reaction timestamps**: Only create a `[Reaction]` timestamp if the speakers stop/pause the episode to react for 30+ seconds. Brief gasps don't need their own timestamp.
- **Spoiler awareness**: If speakers warn viewers about spoilers, note it: `[Discussion] ⚠️ สปอยล์ [SeriesName]`.
- **Pause & discuss**: When they pause the episode to explain lore or debate, switch from `[WatchParty]` to `[Discussion]` or `[Lore]`.

---

## Export Template

```
00:00:00 - [Greeting] Boat + Guest เปิดสตรีมคุยเรื่องโทคุซัทสึ
00:04:30 - [Discussion] ถกเรื่องไรเดอร์ยุค Heisei vs Showa — ยุคไหนดีกว่า
00:18:00 - [WatchParty] ดู Kamen Rider Gaim EP 47
00:35:10 - [Reaction] ช็อคกับ ending ของ Gaim — หยุดดูเพื่อวิจารณ์
00:40:00 - [Review] สรุปความเห็นหลังดู Gaim EP 47 — ให้คะแนน
00:50:00 - [News] ข่าวนักแสดงใหม่ Kamen Rider ซีซั่นหน้า
00:58:00 - [Tierlist] จัดอันดับ Final Form ที่เท่ที่สุดในซีรีส์ OOO
```

---

## Iron Rules

- **Proper names must be exact**: Franchise names, series titles, character names, and actor names must be spelled correctly. Verify with a web search if uncertain — do NOT guess.
- **Never mix up Sentai and Rider**: Super Sentai and Kamen Rider are different franchises. Never label a Sentai character as a Rider or vice versa.
- **Watch party pacing**: Do not create a timestamp for every scene. Only mark major episode moments the speakers explicitly react to or pause for.
- **Multi-speaker attribution**: If a guest is identified by name on stream, include their name in the timestamp description.
- **Invoke `masking-royal-news` ONLY when legal risk is present** (rare in tokusatsu streams): Trigger only if Boat directly names real royal/sensitive figures, or uses One Piece metaphors in a way that clearly maps to royal/succession context rather than actual tokusatsu or anime discussion. General political commentary is fine unmasked.

