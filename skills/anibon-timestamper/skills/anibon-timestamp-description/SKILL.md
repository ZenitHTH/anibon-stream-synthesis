---
name: anibon-timestamp-description
description: Use when writing timestamp descriptions for any anibon-timestamper stream, to ensure each description captures the streamer's point, analysis, social impact, and live comment in one tight sentence.
---

# Anibon Timestamp Description

## Overview

A cross-stream subskill loaded by any anibon-timestamper subagent whenever writing a timestamp description. The goal is one tight sentence that captures the full picture:

- What is the streamer's point on this topic?
- What is their analysis/hot take?
- What is the social impact?
- What was the live comment/chat vibe at that moment?

Synthesize these four into **one sentence** that viewers can read and immediately understand why this moment was interesting.

## The 4-Pillar Framework

Before writing any description, scan the transcript for these 4 signals:

### Pillar 1: Point (ประเด็น)

The core topic the streamer wants to talk about. Not the headline — the **angle** they chose.

**Ask:** What specific topic did Boat pull from the news/chat/event to discuss? What made him bring it up now?

| Weak (just the topic) | Strong (the angle) |
|---|---|
| น้ำท่วมอยุธยา | น้ำท่วมใหญ่อยุธยาแต่ทุกคนสนแต่ MOU 43/44 |
| มาสคอตซีเกมส์ | มาสคอตซีเกมส์ชาติจ๋าเกินไป |
| เกษียณ 60→65 | คนรุ่นใหม่เสียโอกาสเพราะรุ่นเก่าไม่ยอมปล่อย |

### Pillar 2: Analysis (การวิเคราะห์)

The streamer's unique take — **not** generic facts. This is what makes timestamps valuable: viewers watch Boat for his opinion, not news headlines.

**Ask:** What specific angle/analysis did Boat add? What frame did he put around this topic?

Detect cues:
- "ผมว่ามันคือ..." (I think it's...)
- "ที่จริงมันคือ..." (Actually it's...)
- "ถ้ามองอีกมุม..." (Looking at it another way...)
- "สรุปคือ..." (In summary...)
- "ที่คนไม่เข้าใจคือ..." (What people don't understand is...)

### Pillar 3: Social Impact (ผลกระทบต่อสังคม)

Why does this matter to the audience/viewers/society right now? The "so what" factor.

**Ask:** Why should the viewer care about this topic right now? Who is affected?

Examples:
- กระทบแรงงานไทย 5 หมื่นคนในอิสราเอล
- คนรุ่นใหม่เสียโอกาสเติบโตในองค์กร
- เสี่ยงโดนกัมพูชาฟ้องศาลโลก
- ข้อมูล 8 ปีหายเพราะไฟไหม้ Data Center

### Pillar 4: Live Comment (สีสันห้องสด)

The chat/streamer mood at that moment. What made this moment "live" — the vibe, the reaction, the community energy.

**Ask:** Was the chat hyped? Was Boat frustrated? Was there a joke, a rant, a laugh?

Detect cues:
- Boat reads chat: "ในแชทบอกว่า..." / "มีคนถามว่า..."
- Chat reaction: 555 floods, hype, debate, confusion
- Boat's emotion: โมโห, ขำ, งง, ประชด, เสียใจ, กลัว
- Chat-driven tangents: viewer question triggers 5+ minute discussion

**Do NOT include:** Generic "chat reacts" or "viewers asked" without specifics. Only include when the live interaction shapes the topic.

## The One-Sentence Synthesis

Combine the strongest 2-3 pillars (not all 4 — that's too dense) into **one sentence**.

### Patterns

```
[Point] แต่/แต่กลับ [Analysis] เพราะ/ส่งผล [Impact]
```

```
[Point] [Analysis] [Live Comment]
```

```
[Point] [Impact] ...คนดู [Live Comment]
```

### Before/After Examples

**Before (dry facts):**
```
Boat วิเคราะห์น้ำท่วมอยุธยาพายุถล่มปี 68 หนักเทียบปี 54 บางบาลท่วมสูง 3 เมตร เตือน กทม.
```

**After (4-pillar):**
```
น้ำท่วมใหญ่อยุธยาพายุถล่มซ้ำซาก ชาวบ้านท่วมสูง 3 เมตร สนใจแต่ MOU 43/44 กันหมด
```
- Point: น้ำท่วมอยุธยา
- Analysis: ซ้ำซาก, หนักเทียบปี 54
- Social Impact: คนไม่สนเพราะสนแต่ MOU
- Live Comment: สนใจแต่ MOU 43/44 (implicit: contrast that Boat noticed)

---

**Before (generic):**
```
Boat วิจารณ์ไทยตีมึน-เขมรตีเนียน ปมแผนที่ 1:50k vs 1:200k ที่ไทยแพ้คดีพระวิหาร ICJ ปี 1962
```

**After (4-pillar):**
```
ไทยตีมึน-เขมรตีเนียน แผนที่ 1:50k vs 1:200k ปมที่แพ้คดีพระวิหาร ICJ 1962 เลิก MOU แล้วมีแผนสำรองไหม
```
- Point: ไทย vs เขมร แผนที่สองมาตรฐาน
- Analysis: ไทยตีมึนเขมรตีเนียน มาตลอด 20 ปี
- Social Impact: เลิก MOU แล้วไม่มีแผนสำรอง
- Live Comment: (implied frustration)

---

**Before (dry):**
```
Boat เกริ่น "ตำรวจด้อม" แฟนเวิร์ค-โดจินชิ ยก Koami เจ้าของ Yu-Gi-Oh! ใจกว้าง บอกดราม่าไม่ใช่เรื่องใหญ่
```

**After (4-pillar):**
```
"ตำรวจด้อม" แฟนเวิร์ค-โดจินชิ โดนแบนง่ายไป Koami เจ้าของ Yu-Gi-Oh! ยังใจกว้าง ดราม่าไม่ใช่เรื่องใหญ่
```
- Point: ตำรวจด้อม/แฟนเวิร์คถูกแบน
- Analysis: เทียบ Koami ใจกว้าง, ไทยแบนง่ายเกิน
- Live Comment: Boat ประชด/เห็นต่างจากกระแส

---

**Before (generic):**
```
Boat รับไม่ได้กับคลิปหนุ่มรัสเซียมีเซ็กส์บนกระบะกลางกรุง ขนาดนี้ที่สาธารณะ
```

**After (4-pillar):**
```
คลิปหนุ่มรัสเซียมีเซ็กส์บนกระบะกลางกรุง สังคมเดือดรับไม่ได้ที่สาธารณะ
```
- Point: คลิปรัสเซียบนกระบะ
- Analysis: (implied — มันเกินไป)
- Social Impact: สังคมเดือด
- Live Comment: สังคมรับไม่ได้

## Decision Guide: Which Pillars to Include

| If this chunk has... | Include... | Why |
|---|---|---|
| Strong point + hot take analysis | Point + Analysis | Viewer wants Boat's opinion |
| Clear social consequences | Point + Impact | Viewer wants to know what this means |
| Viral/lively chat reaction | Point + Live Comment | Viewer wants the community moment |
| Boat on a rant | Analysis + Impact | The facts are known; his take matters |
| Chat-driven tangent | Point + Live Comment | The viewers redirected the stream |

Never force all 4. A good timestamp includes **2-3 strong pillars**. The 4th is implicit.

## Iron Rules

- **One sentence only.** If you need commas or dashes to connect, good. If you need a period and a second sentence, you picked too many pillars.
- **Lead with the Point.** The timestamp reader needs to know what this is about in the first 3-4 words.
- **No false specificity.** If Boat didn't analyze it, don't invent an analysis. Use a different pillar instead.
- **Keep proper nouns exact.** Names, titles, numbers must be exact from transcript. No approximations.
- **Caveman OK.** Drop articles, filler, pleasantries. Fragments allowed. Technical terms exact.
- **Not for [Donation].** Use `anibon-donation-classifier` for donation timestamps instead.
