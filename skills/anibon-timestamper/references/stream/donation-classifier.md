---
name: anibon-donation-classifier
description: Use when writing descriptions for [Donation] timestamps in an anibon-timestamper stream, to select the correct donation sub-type and tone (Serious, Joke, Q&A, Weird) before writing the description.
---

# Anibon Donation Classifier

## Overview

A cross-stream subskill loaded by any anibon-timestamper subagent whenever a [Donation] timestamp is emitted. The tag `[Donation]` alone is ambiguous — a superchat can be heartfelt support, a setup for a joke, a question, or outright absurdist chaos. This skill teaches you to detect the sub-type and write the description in matching tone.

## When to Use

Load this skill alongside the primary stream skill (`anibon-talk-stream`, `anibon-gaming-stream`, etc.) whenever the transcript shows the speaker reading or reacting to a paid message (superchat / โดเนท).

Detection cues in transcript:
- `ขอบคุณ... โดเนท` / `ขอบคุณ... ซุปเปอร์แชท`
- Speaker reads out a username and a paid message content
- Sudden emotional shift: burst of laughter, long pause, "เดี๋ยวๆ", loud reaction

## Donation Sub-Types

### 1. `[Donation]` Serious — ซีเรียส / ให้กำลังใจ
**What it is:** Viewer sends genuine support, birthday wishes, get-well messages, graduation congratulations, or heartfelt thank-you messages. No punchline.

**How to detect:**
- Polite, formal Thai: ขอให้สุขภาพแข็งแรง, ขอบคุณมาก, ขอเป็นกำลังใจ
- Speaker reacts with sincere tone: "ขอบคุณมากนะครับ", "อบอุ่นมากเลย"
- No laughter, no confusion, no "เดี๋ยวๆ"

**Description style:** Sincere, straightforward. Mention the occasion if present.

**Example:**
```
07:45:00 - [Donation] ขอบคุณโดเนทให้กำลังใจและอวยพรสุขภาพแข็งแรง
```

---

### 2. `[Donation]` Joke — ขำขัน / ล้อเล่น
**What it is:** Viewer sends a punchline, meme, self-referential joke, or wordplay to entertain. The humor is deliberate — content was crafted to be funny.

**How to detect:**
- Speaker bursts into laughter immediately after reading
- Puns, memes, in-community references (เฟสไทยไลน์, Okita-san, etc.)
- Speaker breaks character, says "555" or "แม่งฮาเลย"
- Chat floods with 555 or laughter emotes

**Description style:** Playful. Describe the joke briefly without explaining it — capture the spirit, not the anatomy.

**Examples:**
```
04:34:29 - [Donation] ขอบคุณโดเนทที่ส่งมุกตลกล้อเลียนเรื่อง 'เฟสไทยไลน์มีเกย์' (Fate/type Redline)
01:21:23 - [Donation] ขอบคุณโดเนทแสดงความยินดีและยิงมุขสอบผ่าน ก.พ. ทำไลฟ์คึกคัก
```

---

### 3. `[Donation]` Q&A — ถาม-ตอบ / ขอคำแนะนำ
**What it is:** Viewer uses a paid message to ask a direct question, request advice, or invite a topic discussion. Speaker answers verbally.

**How to detect:**
- Question words: ถามว่า, อยากรู้ว่า, แนะนำได้ไหม, คิดว่า...ยังไง
- Speaker shifts to answer mode: explains, gives opinion, or opens a mini-discussion
- Sometimes triggers a 5–10 minute tangent

**Description style:** Describe the question topic, not the full answer. Use "ตอบคำถาม" + topic.

**Example:**
```
05:12:00 - [Donation] ตอบคำถามจากผู้ชมเรื่องแผนการสตรีมและชีวิตการทำงาน
```

---

### 4. `[Donation]` Weird — แปลก / ไม่สมเหตุสมผล / absurdist
**What it is:** Viewer sends something surreal, non-sequitur, disturbing, or nonsensical. Speaker visibly confused or stunned. Not a normal joke with a punchline — just chaos.

**How to detect:**
- Speaker says: "เดี๋ยวๆ", "นี่มันคืออะไร", "ทำไมนะ", long confused silence
- Content is unhinged or deeply random (e.g., dream about eating poop, crab fighting crab over soy sauce)
- Chat reacts with 🤡, ❓, or floods in confused emotes
- No clear "funny" intent — just wrong

**Description style:** Capture the weirdness briefly. Let the absurdity speak. Use neutral, slightly bewildered tone.

**Example:**
```
09:03:00 - [Donation] ขอบคุณโดเนทแปลกๆ ที่ทำให้ปู่โบ๊ตงงงวย ก่อนอธิบายเนื้อหาต่อ
02:17:00 - [Donation] ขอบคุณโดเนทส่งข้อความสุดแปลกเรื่องฝันเห็นปู่โบ๊ตสู้กับปูตัวใหญ่เพื่อซีอิ๊ว
```

---

## Decision Flowchart

```
Is the speaker laughing / chat flooding 555?
  YES → Did the viewer intend a punchline?
          YES → Joke
          NO  → Weird
  NO  → Does the message contain a question or request for advice?
          YES → Q&A
          NO  → Is the message emotionally supportive or congratulatory?
                  YES → Serious
                  NO  → Weird (catch-all for uncategorized absurdity)
```

## Iron Rules

- **One tag only**: A donation is ONE type. Pick the dominant signal. If the viewer leads with a joke but ends with a question, the joke is the payload — use `Joke`.
- **Never say "ขอบคุณโดเนทเรื่อง..."** as the entire description for a Joke or Weird entry. The reader needs to know the tone, not just the acknowledgment.
- **Never reveal offensive content verbatim** in the description for Weird donations. Describe what happened without quoting disturbing text.
- **Single sentence only**: Descriptions must fit one line. No multi-sentence timestamps.

## Rationalization Red Flags — STOP if you think any of these

| Thought | Why it's wrong |
|---|---|
| "I'll just use `[Donation]` with a generic thanks — it doesn't matter which type" | The whole point of this skill is that type matters. Viewers use timestamps to find funny moments, not just "a donation happened". |
| "This is kind of a joke AND a Q&A, I'll call it Q&A since it ends with a question" | Lead intent wins. If the viewer's first act was a joke, it's a Joke donation. |
| "The donation is weird but not that weird, I'll call it Serious" | If it made the speaker pause in confusion, it's Weird. Serious = no confusion. |
| "I don't have enough context to pick a type — I'll default to Serious" | Default is Weird if you're unsure. Serious is a deliberate, warm message. Uncertainty = something strange happened. |
