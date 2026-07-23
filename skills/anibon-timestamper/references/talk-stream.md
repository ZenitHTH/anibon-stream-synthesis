---
name: anibon-talk-stream
description: Use when processing a live stream or specific video chunk where the speaker is primarily talking, chatting with viewers, or discussing news/updates (Talk-heavy stream).
---

# Anibon Talk Stream

## Overview
This skill handles the timestamping and topic summarization for "talk-heavy" chunks of a video or live stream, particularly for speaker "Boat" from Anibon Official. It focuses on topic-flow analysis and capturing specific interaction cues.

## When to Use
- You are directed here by the `anibon-timestamper` orchestrator.
- You are processing a chunk of a transcript (e.g., 10-15 minutes) and notice the speaker is mostly talking, reading chat, or summarizing news.

## Behaviors & Rules

### 1. Topic-Flow Analysis
- **Core Strategy**: Identify which topics the speaker "flows into". Start a new timestamp whenever the topic shifts.
- **Scan for timeline gaps**: If there are gaps of 15+ minutes with no timestamps, deeply inspect the transcript for casual, off-topic, or chat-driven discussions that were overlooked.

### 2. Categories
Use these categories for timestamp labels:
- `[Greeting]` — Stream start, viewer welcome, announcements
- `[Talk]` — General discussion, stories, off-topic chat
- `[News]` — News summaries, current events, announcements
- `[Chat]` / `[Q&A]` — Reading/responding to live chat
- `[Donation]` — Responding to superchat/paid messages
- `[Break]` — Stream breaks, drinking water, AFK

**Hybrid Rule (Storytelling while Gaming)**:
If the speaker is delivering a deep, continuous story/lecture while playing a game (e.g., explaining Three Kingdoms lore while playing Wo Long, or suddenly discussing "One Piece" lore such as Celestial Dragons or Imu which is actually a coded discussion about Thai politics), track the flow of the story using `[Talk]` or `[News]` while keeping the One Piece metaphors exactly as the speaker said them. However, you may also use these gaming tags if the game interrupts the story with a major event:
- `[Boss]` — Encounters a major boss.
- `[Death]` — Dies in a funny/notable way that causes a strong reaction.
- `[Victory]` — Defeats the boss.

### 3. Live Chat & Donation Consideration
- **Monitor Interaction Cues**: Pay close attention to when the speaker reads out live chat or donation messages. Look for cues like reading usernames, saying "ในแชทบอกว่า" (chat says), "มีคนถามว่า" (someone asked), "คุณ... บอกว่า" (you said).
- **Precise Labeling**:
  - Use `[Donation]` when the speaker responds to a paid message or superchat.
  - Use `[Chat]` or `[Q&A]` when the speaker addresses a general comment or question from the live chat.
- **Capture off-topic discussions**: The speaker frequently digresses to chat with viewers about miscellaneous news, social drama, personal anecdotes, or jokes. Always capture these.

### 4. Tone & Personality
** native speak language **
- **โหมดจริงจัง**: ใช้ภาษาที่ชัดเจน กระชับ และเป็นมืออาชีพ สำหรับช่วงสรุป/รายงาน/วิเคราะห์ข่าว
- **โหมดตลก/สนุก**: ใช้ภาษาที่ปั่นและดูสนุกเมื่อผู้พูดกำลังคุยหยอกล้อสร้างความบันเทิงให้กับผู้ชม
- ผู้พูดมีรสนิยมชอบเสพสื่อลามกโดจิน บางครั้งชอบพูดเล่นแบบติดเรทเพื่อสร้างความบันเทิงในไลฟ์ แนะนำให้ตั้งหัวข้อตามโทนและอารมณ์สตรีม
** native speak language **

## Export Template
```
00:00:00 - [Greeting] Stream start and viewer welcome
00:05:12 - [News] New Fate/Grand Order JPN gacha banner announcement
00:15:32 - [Talk] เล่าเรื่องสัปดาห์ที่ผ่านมา
00:20:10 - [Chat] ตอบคำถามเรื่องระบบเกม
```

## Iron Rules
- **Proper names must be exact**: Search via Google before finalizing any name.
- **Invoke `masking-royal-news` ONLY when legal risk is present.** Do NOT mask by default. Trigger ONLY if the chunk contains one or more of these signals:

  | Signal | Example in transcript | Action |
  |---|---|---|
  | **Direct royal naming** | โบ๊ทพูดถึง "ร.10", "ราชินีสุทิดา", "พระองค์ภา" ชื่อตรงๆ | Mask immediately |
  | **One Piece metaphors used off-lore** | โบ๊ทพูดถึง "อิมู" / "มารีนฟอร์ด" แต่บริบทไม่ตรงกับเนื้อเรื่อง One Piece จริง (เช่น พูดแล้วเชื่อมกับข่าวการเมืองไทย, ม.112, หรือ succession) | Treat as coded royal talk → Mask |
  | **Section 112 / lèse-majesté discussion** | พูดถึง "กฎหมายที่แตะต้องสถาบันไม่ได้" โดยไม่ใช้บริบทการเมืองทั่วไป | Mask |

- **Do NOT mask** general political party critique (พรรคก้าวไกล, เพื่อไทย, ประชาธิปัตย์), election commentary, civil policy discussion, or One Piece lore that is clearly about the anime story itself.
- **Quick test before masking**: ถามตัวเองว่า "ถ้าโพสต์ข้อความนี้ใน YouTube comment ตรงๆ แล้วจะมีความเสี่ยงเรื่องมาตรา 112 ไหม?" ถ้าไม่มี → ไม่ต้อง mask
- **Technical/Software Discussions**: When Boat discusses software issues, file formats/codecs (WebM/AV1), or PC setups, trigger Vision inspection (`ffmpeg` frame capture + `view_file`) if the raw transcript audio leaves technical terms ambiguous or incomplete.

