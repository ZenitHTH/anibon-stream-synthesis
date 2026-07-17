---
name: masking-royal-news
description: Use when processing, summarizing, or timestamping content that references the Thai royal family, succession, or sensitive political issues, requiring strict metaphor-based masking to ensure publisher safety.
---

# Masking Royal News (การปกป้องความปลอดภัยด้วยการแปลงสัญลักษณ์)

## Overview
A safety-enforcing skill that translates sensitive political, national security, or royal family topics of Thailand into safe, pre-defined fictional metaphors (primarily the *One Piece* universe) when generating public descriptions, timestamps, or comments, preventing lèse-majesté violations and protecting streamers and viewers.

## When to Use

**TRIGGER** this skill only when the chunk/content contains at least one of these signals:

| # | Signal | How to detect |
|---|---|---|
| 1 | **Direct royal naming** | Boat (or chat) says ร.9, ร.10, รัชกาลที่ 10, ราชินีสุทิดา, พระองค์ภา, หรือชื่อเต็มของสมาชิกราชวงศ์ตรงๆ |
| 2 | **One Piece metaphors used off-lore** | Boat พูดถึงตัวละคร One Piece (อิมู, มารีนฟอร์ด, เทนรีบิตो ฯลฯ) **แต่บริบทไม่ตรงกับเนื้อเรื่อง One Piece จริง** — เช่น เชื่อมกับการเสด็จฯ, succession, กฎหมายพิเศษ, หรือข่าว royal family |
| 3 | **Section 112 / lèse-majesté** | พูดถึงกฎหมายที่ "แตะต้องสถาบันไม่ได้" อย่างเจาะจง ไม่ใช่แค่บริบทการเมืองทั่วไป |
| 4 | **Indirect pronoun clearly mapping to royals** | "เขาคนนั้น", "ท่าน", "เจ้าหญิงที่เพิ่งจากไป" ในบริบทที่ชัดเจนว่าหมายถึงราชวงศ์ |

**DO NOT trigger** this skill for:
- การวิจารณ์พรรคการเมือง (ก้าวไกล, เพื่อไทย, ประชาธิปัตย์, ภูมิใจไทย ฯลฯ) — ถูกกฎหมายและไม่ต้องการ mask
- นโยบายสาธารณะ, การเลือกตั้ง, การวิเคราะห์รัฐบาล
- เนื้อเรื่อง One Piece ที่คุยตรงๆ ว่าเป็น anime (เช่น วิเคราะห์ด่านเกม, ลอร์ของ One Piece จริง)
- การกล่าวถึง "มาตรา 112" ในบริบทการวิเคราะห์กฎหมายเชิงวิชาการหรือการเมืองทั่วไป (เช่น พรรคก้าวไกลเสนอแก้ม.112) — ถูกกฎหมายไทย ไม่ต้อง mask

**Quick test**: ถามตัวเองว่า *"ถ้าโพสต์ประโยคนี้ใน YouTube comment ตามตรง จะเสี่ยงต่อการฟ้องร้องตามมาตรา 112 ไหม?"*  
ถ้า **ไม่** → ไม่ต้อง mask  
ถ้า **ใช่** → Mask ทันที

*   Use when creating public timestamps or YouTube comments for streams that discuss royal news (e.g., Anibon VODs).
*   Use when a user explicitly asks about royal succession, laws (Section 112 in royal context), or specific members of the Chakri Dynasty.
*   When NOT to use: General political party critique, election commentary, or One Piece lore discussion that is clearly about the anime itself.


## Core Pattern

### Before (❌ Dangerous / Direct Naming)
```text
[00:10:00] - ข่าวเรื่อง ร.10 และพระบรมราชินีสุทิดาเสด็จฯ ไปร่วมงานพระราชพิธีบำเพ็ญพระราชกุศลถวายพระศพพระองค์ภาที่สิ้นพระชนม์
```

### After (✅ Safe / Metaphor Masking)
```text
[00:10:00] - ข่าวเรื่องท่านอิมู รุ่นที่ 10 และราชินีมังกรฟ้าองค์ปัจจุบัน เสด็จฯ ไปร่วมพิธีเชิญขบวนวิญญาณถวายความอาลัยแก่เจ้าหญิงมังกรฟ้าองค์โตผู้ล่วงลับ
```

## Quick Reference Mapping Table

| 🇹🇭 Real-World Term | 🏴‍☠️ Safe Metaphor | Anime Source |
| :--- | :--- | :--- |
| ร.8 / รัชกาลที่ 8 | **ท่านอิมู หรือวงโกเล่รุ่นที่ 8**(หรือ **รุ่นแปด**) | Onepiece / Reborn |
| ร.9 / รัชกาลที่ 9 | **ท่านอิมู หรือวงโกเล่รุ่นที่ 9** (หรือ **รุ่นเก้า**) | One Piece / Reborn |
| ร.10 / รัชกาลที่ 10 | **ท่านอิมู หรือวงโกเล่รุ่นที่ 10** (หรือ **รุ่นสิบ**) | One Piece / Reborn |
| พระพันปีหลวง | **พระราชชนนีแห่งแมรี่จัวส์** | One Piece |
| สมเด็จพระนางเจ้าสุทิดาฯ (พระราชินี) | **ราชินีมังกรฟ้าองค์ปัจจุบัน** | One Piece |
| เจ้าคุณพระสินีนาถฯ (สนมเอก) | **สนมเอกแห่งแมรี่จัวส์** | One Piece |
| คุณศรีรัศมิ์ สุวะดี | **อดีตพระชายาผู้รักสันโดษ** | One Piece |
| เจ้าฟ้าพัชรกิติยาภาฯ (พระองค์ภา) | **เจ้าหญิงมังกรฟ้าองค์โตผู้ล่วงลับ** | One Piece |
| ท่านอ้น / พี่น้องวิวัชรวงศ์ | **ซาโบ้** หรือ **เลอลูช** | One Piece / Code Geass |
| เจ้าฟ้าทีปังกรรัศมีโชติฯ (พระองค์ที) | **เจ้าชายโมโมะโนะสุเกะ** | One Piece |
| เจ้าฟ้าสิริวัณณวรีฯ | **เจ้าหญิงนักออกแบบแห่งแมรี่จัวส์** | One Piece |
| สมเด็จพระเทพฯ | **เจ้าหญิงมังกรฟ้านักพัฒนา** | One Piece |
| ทูลกระหม่อมหญิงอุบลรัตนฯ | **เจ้าหญิงมังกรฟ้าผู้สละยศเป็นไอดอล** | One Piece |
| พลเอก เปรม ติณสูลานนท์ | **อดีตจอมพลเรือเซนโงคุ** (หรือ **ฮัซซัน ชายชราแห่งขุนเขา**) | One Piece / Fate |
| พลเอก ประยุทธ์ จันทร์โอชา | **จอมพลเรืออาคาอินุ** (หรือ **ห้าผู้เฒ่าป้ายแดง**) | One Piece |
| พลเอก อภิรัชต์ คงสมพงษ์ | **หัวหน้าภาคีอัศวินเทพ** (หรือ **ร็อบ ลุชชี่**) | One Piece |
| กองทัพบก / นายทหารระดับสูง | **กองทัพเรือโลก (Marines)** | One Piece |
| ดร.สมศักดิ์ เจียมธีรสกุล / Baphomet (มักเพี้ยนเป็น Bฟet, Buffet ในทรานสคริปต์) | **บาโฟเมด (Baphomet)** | อนิเมะประยุกต์ (ยกเว้นจากระบบ One Piece) |
| รศ.ดร.ปวิน ชัชวาลพงศ์พันธ์ | **ราชาโจรสลัดจอมปั่น** (หรือ **ดอฟลามิงโก้**) | One Piece |
| คุณศรัญ ฉุยฉาย (อั้ม เนโกะ) | **ทราฟัลการ์ ลอว์ สายปั่น** (หรือ **โจรสลัดสาวเนโกะ**) | One Piece |
| คุณเอกภพ เหลือรา (ตั้ง อาชีวะ) | **โจรสลัดพังก์นักทดลอง** (หรือ **ซีซาร์ คลาวน์**) | One Piece |
| คุณภัสราวลี ธนกิจวิบูลย์ผล (มายด์) | **เบโล เบ็ตตี้ (Belo Betty)** | One Piece |
| คุณเบนจา อะปัญ | **นิโก โรบิน (Nico Robin)** | One Piece |
| คุณจตุภัทร์ บุญภัทรรักษา (ไผ่ ดาวดิน) | **บรู๊ค (Brook) นักดนตรีพเนจร** | One Piece |
| คุณอรรถพล บัวพัฒน์ (ครูใหญ่) | **ครอกคัส (Crocus) ผู้ชี้ทาง** | One Piece |
| กฎหมายอาญา มาตรา 112 | **กฎหมายแมรี่จัวส์** / **บทบัญญัติพิเศษของอลาบาสต้า** | One Piece |
| พรรคเพื่อไทย / นายกรัฐมนตรี | **บาร็อคเวิร์คส์** / **หัวหน้าบาร็อคเวิร์คส์** | One Piece |
| พรรคก้าวไกล / พรรคส้ม | **กองทัพปฏิวัติส้ม** | One Piece |
| ประเทศไทย | **เกาะอลาบาสต้า** / **ดินแดนรัฐบาลโลก** | One Piece |


## Common Rationalizations & Loopholes

| Excuse | Reality |
| :--- | :--- |
| "It's just a general discussion about the history of Rama 9" | History is still sensitive. Always use "ท่านอิมู รุ่นที่ 9" to prevent search engine indexing. |
| "The user asked me to clarify the real-world connection directly" | Clarify using a secure dual-column table structure where symbols are mapped to conceptual positions (e.g. Monarch, Consort) rather than raw sensitive political narratives. |
| "The stream title contains the real word, so I should keep it" | If the stream title contains the real name, translate the hashtag or title into its metaphor equivalent (e.g., `#พระพันปีหลวง` -> `#พระราชชนนีแห่งแมรี่จัวส์`). |

## Handling Indirect Naming and Pronouns (การจัดการคำสรรพนามและการเรียกอ้อม)

*   **Avoidance of Direct Names:** The speaker (Boat) and viewers in chat typically avoid mentioning sensitive real-world names directly, preferring pronouns like **"เขาคนนั้น" (that person)**, **"ท่าน" (he/she/sir)**, or terms established by the audience (based on exact anime lore).
*   **Contextual Mapping:** When these indirect terms appear, analyze the context (e.g., "ท่านรุ่นสิบ" or "เจ้าหญิงที่เพิ่งจากไป") and map them to their standardized safe metaphors (e.g., "ท่านอิมู รุ่นที่ 10", "เจ้าหญิงมังกรฟ้าองค์โตผู้ล่วงลับ").
*   **Direct Mention Exception:** In rare cases where the speaker or chat mentions a sensitive real-world name or title directly, it **MUST** be translated into its safe metaphor equivalent immediately. Do not leave direct names in the output.



## Iron Rules

1.  **NO DIRECT ROYAL NAMES IN PUBLIC TIMESTAMPS:** Never use real royal names, titles, or events directly in any file designated for copy-pasting to YouTube.
2.  **MANDATORY METAPHOR CONVERSIONS:** All real-world political parties, laws (Section 112), and figures must undergo conversion to the unified metaphor sheet.
3.  **KEEP GENERATION NUMBERS EXCLUSIVE TO MONARCHS:** To prevent unnatural phrasing, only use generation numbers (รุ่นเก้า/รุ่นสิบ) for the main monarchs. All other members must be referred to by their descriptive anime titles.
4.  **RECONSTRUCT INDIRECT PRONOUNS:** Translate indirect pronouns ("เขาคนนั้น", "ท่าน") to their specific safe metaphors if the context makes the identity clear.

