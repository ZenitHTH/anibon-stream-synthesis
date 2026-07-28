---
name: anibon-talk-stream
description: Use when processing a live stream or specific video chunk where the speaker is primarily talking, chatting with viewers, discussing news/updates, or conducting analytical anime rants (Talk-heavy stream).
---

# Anibon Talk Stream

## Overview
This skill handles timestamping and topic summarization for "talk-heavy" chunks of a video or live stream, particularly for speaker "Boat" from Anibon Official. It focuses on topic-flow analysis, anime industry rants, dual-synthesis timestamping, and capturing specific interaction cues.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk of a transcript (e.g., 10-15 minutes) and notice the speaker is mostly talking, reading chat, summarizing news, or analyzing anime/manga industry topics.

## Behaviors & Rules

### 1. Topic-Flow Analysis
- **Core Strategy**: Identify which topics the speaker "flows into". Start a new timestamp whenever the topic shifts.
- **Scan for timeline gaps**: If there are gaps of 15+ minutes with no timestamps, deeply inspect the transcript for casual, off-topic, or chat-driven discussions that were overlooked.
- **Opening Stream Setup**: When the streamer talks for 10+ minutes before starting the main agenda/gameplay, extract 3-5 min milestones: Stream Greeting → Topic Announcement → Rules & Setup → Pre-game Discussion.
- **Anime Monologue Breakdown**: During continuous 20–30 minute anime monologues, break down the timeline into **3–7 minute sub-topic milestones**:
  1. `[Anime] Topic Announcement / Reaction`: Initial reaction to news, trailer, or chat question.
  2. `[Anime] Production & Technical Breakdown`: Studio animators, director style, budget, or manga pacing.
  3. `[Anime/Industry] Thai Licensing & Local Market Impact`: Local distributor analysis (JAM, Muse, Medialink) and Thai theatrical window predictions.
  4. `[Anime/Industry] Economics & Purchasing Power`: Production Committee decisions, "แม่ยก" purchasing power, or fan response.
  5. `[Talk] Conclusion & Viewer Advice`: PhuBoat's final takeaway or advice to live chat.

### 1.1 Vlog / Worksite Content
When Boat streams pipeline/construction/site work as a vlog:

**Core Strategy**: Track both the work activity AND the conversation. Work vlogs have dual narrative — what Boat is doing physically + what he's discussing verbally.

**Vlog Breakdown Pattern** (for 20-30 min continuous worksite segments):
1. `[Work]` Task Start / Tool Setup: Boat begins a specific task, explains tools/materials.
2. `[Work]` Process & Technique: Demonstrates method, shares tips, troubleshoots.
3. `[Talk]` Story / Tangent: While working hands-free, Boat goes into personal story, industry rant, or chat Q&A.
4. `[Chat]` Viewer Interaction: Reads chat, answers questions about the work or off-topic.
5. `[Work]` Milestone / Completion: Finishes a task segment, shows result.

**Visual+Audio Synthesis for Vlogs**: The Dual-Synthesis rule (Section 2) applies strongly — Boat may be welding/cutting/driving while discussing anime or politics. Capture BOTH the physical context AND the spoken topic. Example: `[Work] เชื่อมท่อながら discussing FGO story finale` — include both.

**Environmental Audio Cues**: Note when background noise (machinery, traffic, wind) affects readability or signals context shift (e.g., moving indoors → outdoors).

### 2. Dual-Synthesis Timestamp Analysis (Visual Action + Spoken Audio)
- **The Dual-Synthesis Principle**: PhuBoat frequently navigates desktop browser tabs (MyAnimeList, LiveChart.me, X/Twitter, MANGA Plus, YouTube) while simultaneously answering live chat questions or going off on tangential industry rants.
- **DO NOT** write a timestamp description based solely on what is displayed on screen.
- **DO NOT** write a timestamp description based solely on transcript text without checking visual context.
- **ALWAYS SYNTHESIZE BOTH**: Combine `[On-Screen Visual Context]` + `[Spoken Audio Topic]`.
- **Example**: Screen displays MyAnimeList for Gundam, but speaker is analyzing Granblue Fantasy vs FGO story finale -> Include both visual context & spoken analysis in timestamp description.

### 3. Categories
Use these categories for timestamp labels:
- `[Greeting]` — Stream start, viewer welcome, announcements
- `[Talk]` — General discussion, stories, off-topic chat
- `[Anime]` — Anime/manga reviews, industry analysis, voice actor & studio rants
- `[News]` — News summaries, current events, announcements
- `[Chat]` / `[Q&A]` — Reading/responding to live chat
- `[Donation]` — Responding to superchat/paid messages
- `[Break]` — Stream breaks, drinking water, AFK
- `[Work]` — Pipeline/construction/worksite tasks, tool use, hands-on demonstration
- `[Vlog]` — Daily life vlogging, location transitions, off-stream errands

**Hybrid Rule (Storytelling while Gaming)**:
If the speaker is delivering a deep, continuous story/lecture while playing a game (e.g., explaining Three Kingdoms lore while playing Wo Long, or suddenly discussing "One Piece" lore such as Celestial Dragons or Imu which is actually a coded discussion about Thai politics), track the flow of the story using `[Talk]`, `[Anime]`, or `[News]` while keeping the One Piece metaphors exactly as the speaker said them. However, you may also use these gaming tags if the game interrupts the story with a major event:
- `[Boss]` — Encounters a major boss.
- `[Death]` — Dies in a funny/notable way that causes a strong reaction.
- `[Victory]` — Defeats the boss.

### 4. Live Chat & Donation Consideration
- **Monitor Interaction Cues**: Pay close attention to when the speaker reads out live chat or donation messages. Look for cues like reading usernames, saying "ในแชทบอกว่า" (chat says), "มีคนถามว่า" (someone asked), "คุณ... บอกว่า" (you said).
- **Precise Labeling**:
  - Use `[Donation]` when the speaker responds to a paid message or superchat. Merge with anime topics if applicable (e.g. `[Donation/Anime]`).
  - Use `[Chat]` or `[Q&A]` when the speaker addresses a general comment or question from the live chat.
- **Capture off-topic discussions**: The speaker frequently digresses to chat with viewers about miscellaneous news, social drama, personal anecdotes, or jokes. Always capture these.

### 5. Tone & Personality
** native speak language **
- **โหมดจริงจัง**: ใช้ภาษาที่ชัดเจน กระชับ และเป็นมืออาชีพ สำหรับช่วงสรุป/รายงาน/วิเคราะห์ข่าว/อนิเมะ
- **โหมดตลก/สนุก**: ใช้ภาษาที่ปั่นและดูสนุกเมื่อผู้พูดกำลังคุยหยอกล้อสร้างความบันเทิงให้กับผู้ชม
- ผู้พูดมีรสนิยมชอบเสพสื่อลามกโดจิน บางครั้งชอบพูดเล่นแบบติดเรทเพื่อสร้างความบันเทิงในไลฟ์ แนะนำให้ตั้งหัวข้อตามโทนและอารมณ์สตรีม
** native speak language **

## Export Template
```
00:00:00 - [Greeting] Stream start and viewer welcome
00:05:12 - [News] New Fate/Grand Order JPN gacha banner announcement
00:15:32 - [Anime] วิเคราะห์โครงสร้างโปรดักชันอนิเมะและบทบาทคณะกรรมการนายทุน
00:22:15 - [Anime/Industry] คาดการณ์วันฉายโรงในไทยอนิเมะเดอะมูฟวี่ (JAM / Muse)
00:30:10 - [Chat] ตอบคำถามเรื่องระบบเกม
00:35:00 - [Work] เริ่มเชื่อมท่อเหล็ก อธิบายเทคนิคงานเชื่อมแนวตั้ง
00:42:15 - [Talk] เล่าเรื่องเมมเบอร์แกล้งแมวที่บ้าน ขณะทำงานไปด้วย
00:50:30 - [Work] เช็กระดับน้ำในไลน์ pipeline ก่อนเดินระบบ
00:55:00 - [Chat] ตอบคำถาม tools ที่ใช้ในงาน pipe fitting
```

## Iron Rules
- **Proper names must be exact**: Search via Google before finalizing any name.
- **Invoke `masking-royal-news` ONLY when legal risk is present.** Do NOT mask by default. Trigger ONLY if the chunk contains one or more of these signals:

  | Signal | Example in transcript | Action |
  |---|---|---|
  | **Direct royal naming** | โบ๊ทพูดถึง "ร.10", "ราชินีสุทิดา", "พระองค์ภา" ชื่อตรงๆ | Mask immediately |
  | **One Piece metaphors used off-lore** | โบ๊ทพูดถึง "อิมู" / "มารีนฟอร์ด" แต่บริบทไม่ตรงกับเนื้อเรื่อง One Pieceจริง (เช่น พูดแล้วเชื่อมกับข่าวการเมืองไทย, ม.112, หรือ succession) | Treat as coded royal talk → Mask |
  | **Section 112 / lèse-majesté discussion** | พูดถึง "กฎหมายที่แตะต้องสถาบันไม่ได้" โดยไม่ใช้บริบทการเมืองทั่วไป | Mask |

- **Do NOT mask** general political party critique (พรรคก้าวไกล, เพื่อไทย, ประชาธิปัตย์), election commentary, civil policy discussion, or One Piece lore that is clearly about the anime story itself.
- **Quick test before masking**: ถามตัวเองว่า "ถ้าโพสต์ข้อความนี้ใน YouTube comment ตรงๆ แล้วจะมีความเสี่ยงเรื่องมาตรา 112 ไหม?" ถ้าไม่มี → ไม่ต้อง mask
- **Technical/Software Discussions**: When Boat discusses software issues, file formats/codecs (WebM/AV1), or PC setups, trigger Vision inspection (`ffmpeg` frame capture + `view_file`) if the raw transcript audio leaves technical terms ambiguous or incomplete.

