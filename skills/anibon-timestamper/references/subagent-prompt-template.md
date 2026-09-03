---
name: anibon-subagent-prompt-template
description: Use when building the prompt to send to a chunk-processing subagent for the anibon-timestamper workflow. Contains the canonical step-by-step instructions and output contract.
---

# Anibon Subagent Prompt Template

Use this template when delegating a 5-minute chunk to a subagent.
Fill in the `<placeholders>` before sending.

---

```
You are processing Chunk <N>.
CONTEXT: Stream recorded on <Upload Date> (<Time_Ago>).

## Step 0: READ EVERYTHING FIRST (MANDATORY, do this before anything else)

1. Read the ENTIRE transcript chunk — every line, not a skim. If it is a file,
   read the whole file top-to-bottom (prefer `python -X utf8 scripts/dump_chunk_text.py <chunk_xml>` for clean text).
2. Read the ENTIRE LiveChat log for this chunk (LIVE-CHAT LOG block below), if present.
3. Do NOT write a single timestamp until you have read both fully.
4. If you cannot read the full chunk, output NOTHING and say "incomplete read" — never stamp from a skim.
5. Your whole-chunk understanding is the ONLY basis for stamps. `primary_topic`, signals, and knowledge files are HINTS to verify against the text you read, never substitutes for reading.
6. **FULL LIST REVEAL RULE (Read Further across Adjacent Chunks):** When the streamer reveals a list or announcement (e.g. animation updates, new banners, character lists), do NOT stop reading at the first 3-5 items in your current chunk. Read into the NEXT adjacent chunk(s) to verify if the reveal continues before concluding total counts or listing character names. Never truncate a 7-item list to 5 items just because the reveal spans across chunk boundaries.

PREVIOUS CHUNK PRIMARY TOPIC: <Orchestrator: inject topic of previous chunk>
CURRENT CHUNK PRIMARY TOPIC: <Orchestrator: inject topic from detect_signals.py>

LIVE-CHAT LOG (watchers, this chunk):
<Orchestrator: inject livechat/livechat_chunk_NN.txt content, or "no livechat available">

ON-SCREEN ACTIVITY & WEBCAM (Ground Truth from Storyboard):
<Orchestrator: inject activity/activity_chunk_NN.txt content, or "no visual activity data">
(Ground truth for on-screen game/app, webcam presence/AFK, and physical expressions)

MOOD + TONE GUIDANCE (from analyze_555.py mood_555.json, optional):
<Orchestrator: inject this chunk's {verdict, tone, verbs} from mood_555.json, or "no mood_555". 
The tone/verbs hint is a REMINDER of the vibe the chat carried — you still choose your own
first verb from the situation. Do not flatline a chat laugh/hype peak into a calm verb.>

TOPIC CONTINUITY RULE (READ FIRST):
If CURRENT_CHUNK_PRIMARY_TOPIC matches PREVIOUS_CHUNK_PRIMARY_TOPIC,
output 0 timestamps UNLESS there is a clear EVENT change
(Boss/Death/Victory/Cutscene/Donation).

A "slightly different subtopic" is NOT a topic change.
Only when the GAME or MAJOR ACTIVITY changes.
EXCEPTION: Q&A/interview format — each explicit question frame
("เดี๋ยวตอบคำถามนี้", "ปู่ปู่ว่า...", "สุดท้ายคำถาม") counts
as topic switch regardless of same domain.

DETECTION SIGNALS:
<Orchestrator: inject detect_signals.py output block for this chunk (signal: matched_files, weighted_matched_files, best_file, primary_topic, confidence)>

KNOWLEDGE FILES (RANKED):
<Orchestrator: inject reference file paths, best_file first>

The DETECTION SIGNALS + KNOWLEDGE FILES above are machine-computed and RARITY-WEIGHTED
(term frequency × inverse document frequency). Read the ranked list top-to-bottom, then
VERIFY against the transcript text BEFORE using any file.

FREQUENCY PRIORITY RULE (READ FIRST):
- LOW-frequency (rare) terms = the MAIN IDEA of this chunk. That is what the talker is
  actually "about". Analyze those, not the common words.
- HIGH-frequency (daily-use words that appear in every chunk) = filler. Ignore them; they
  are ambient noise, never the topic.
- Do NOT glue a knowledge file to a bare substring hit. Only use `best_file` if it is the
  chunk's dominant topic AND the transcript confirms it. If `confidence` implies no clear
  winner (no strong best_file) or best_file is null, do NOT inject game/anime names —
  describe the event only.
- The knowledge files contain canonical names — use them only to correct Whisper's
  phonetic spelling of a name you ALREADY confirmed from the transcript. Never name a
  game merely because its keyword appears once elsewhere.

## OUTPUT CONTRACT (read before anything else)

One 5-minute chunk → **1 timestamp by default, 2 MAX**.
A new timestamp is only valid when ONE of these occurs:
- Game switches entirely (different title)
- Speaker joins or leaves (Discord guest, etc.)
- Completely different activity begins (e.g., watching video → playing game)
- A completely NEW topic of conversation begins
- Activity CHANGE within same game (e.g., walking overworld → boss fight, browsing menu → gacha summon, exploration → dialogue)

**0-TIMESTAMP RULE:** Output 0 ONLY if chunk is empty or an exact topic continuation (same game, same activity, no event change). In all other cases, output at least 1 timestamp. "Same topic with minor sub-shifts" is NOT a 0 case — merge into 1.

Multiple sub-topics within one continuous talk → MERGE into 1 timestamp with broader description.

## Wrap Same-Topic Timestamps (post-merge, whole-list pass)

Before finalizing, re-read the FULL merged timestamp list. Wrap consecutive
timestamps that describe the SAME single topic (same event/thread/subject)
within ~≤2 minutes into ONE line:
- KEEP the earliest timestamp's time.
- Prefer the most specific tag; merge descriptions into one concise line.
- If the later line is more informative, carry its wording — don't keep the
  first verbatim.

SAME topic → wrap: same gacha-revenue news stamped twice; `[Reaction]`+`[Reaction]`
on the same ad; `[WatchParty]`+`[Reaction]` on the same PV; `[Gameplay]`+`[Talk]`
on the same skill review; `[Chat]`+`[Donation]` answering the same question.

DO NOT wrap (different topics even if same-second/nearby): `[Gameplay]` analysis
vs `[Gacha]` banner analysis at the same second; two different games; a boss
fight vs a donation read; distinct Q&A questions. Same timestamp ≠ same topic.

Q&A FORMAT EXCEPTION: Structured Q&A where each question is
explicitly framed by host/guest is NOT "continuous talk."
Each distinct question frame = topic boundary → emit 1 stamp.
Detect phrases like "เดี๋ยวตอบคำถามนี้", "ปู่ปู่ว่า...",
"คำถามสุดท้าย", explicit question markers.
If unsure → merge. Never split.

## Step 1: Verify Signal Against Transcript
The [DETECTION SIGNAL] block above suggests the primary topic(s). Confirm by reading the transcript text. If signal says FGO but transcript shows WuWa → trust transcript. Match card/game terms against FGO/YGO database records if provided.

> [!TIP]
> **Reading Chunks**: To inspect transcript dialogue without XML truncation or encoding errors on Windows, run:
> `python -X utf8 scripts/dump_chunk_text.py <path_to_chunk_xmls>`

## Step 2: Time Alignment
For every valid timestamp event:
- Use the pre-calculated `timestamp` field from the JSON item directly.
- Do NOT calculate time yourself.

## Step 3: Select the Correct Tag
- `[Greeting]`: Stream intro / saying hi
- `[Talk]`: Chatting, chat interaction, story tangents, general discussion
- `[News]`: Reading news or commenting on real-world events (apply safety metaphors!)
- `[Chat]`: Speaker reads/responds to live chat message directly
- `[Donation]`: Speaker responds to paid superchat/donation (Must load `references/stream/donation-classifier.md` to classify description)
- `[Gameplay]`: Playing a game / fighting stages
- `[Gacha]`: Drawing cards / summoning (NEVER reveal pull results)
- `[Boss]`: Boss fight / challenging enemy
- `[Death]`: Notable/funny death in-game
- `[Victory]`: Boss cleared / quest completed
- `[WatchParty]`: Watch-along reaction / episode review
- `[Reaction]`: General reaction to trailers or videos
- `[Tour]` / `[Vlog]`: Walking through event halls, IRL walkthroughs, location transitions
- `[Booth]`: Visiting specific company/creator booths (Kadokawa, Good Smile, Animate)
- `[Food]`: Ordering food, tasting Japanese delicacies/sweets, drink reviews
- `[Stage]`: Live stage performances, concert, idol show, cover dance
- `[Cosplay]`: Cosplayers, costume craftsmanship, photo sessions
- `[FanMeet]`: Meeting stream viewers IRL, taking photos, signing autographs
- `[Interview]`: Face-to-face interview with booth staff, creator, or guest
- `[Merch]`: Shopping, figure showcases, anime goods browsing
- `[Work]`: Hands-on worksite, workshop, or pipeline tasks

### Tag Classification Examples:

| Transcript text | Correct tag | Wrong tag |
|---|---|---|
| "สู้บอสตัวนี้ยากมาก" (fighting boss) | `[Boss]` | `[Gameplay]` |
| "ตายแล้วไอ้นี่" (died) | `[Death]` | `[Gameplay]` |
| "เคลียร์แล้ว" (cleared boss) | `[Victory]` | `[Gameplay]` |
| Boat reads chat message: "ในแชทบอกว่า..." | `[Chat]` | `[Talk]` |
| Boat responds to donation: "ขอบคุณครับ..." | `[Donation]` | `[Talk]` |
| Boat watches trailer/youtube video | `[Reaction]` | `[Gameplay]` |
| Boat reads in-game story dialogue | `[Story]` | `[Gameplay]` |
| Boat pulls gacha: "จิ้มเลย" | `[Gacha]` | `[Gameplay]` |
| Boat walks around convention hall: "เดินเข้างานนิปปอนฮาคุ" | `[Tour]` / `[Vlog]` | `[Talk]` |
| Boat visits Good Smile booth: "มาดูฟิกเกอร์บูธนี้" | `[Booth]` | `[Gameplay]` |
| Boat tastes food: "ชิมทาโกยากิร้อนๆ" | `[Food]` | `[Talk]` |
| Boat watches live stage dance: "ดูโชว์บนเวทีใหญ่" | `[Stage]` | `[Reaction]` |
| Boat meets fan IRL: "มีคนดูเข้ามาทักทาย" | `[FanMeet]` | `[Chat]` |
| General overworld walking + fighting trash mobs | `[Gameplay]` | `[Boss]` |
| Boat discusses news/current events | `[News]` | `[Talk]` |

**Rule of thumb:** If the player is FIGHTING a named boss → `[Boss]`. If the player dies → `[Death]`. If the player completes a major objective → `[Victory]`. If the player is farming/running stages → `[Gameplay]`. If Boat looks at external video → `[Reaction]`. Event booth → `[Booth]`. Food tasting → `[Food]`. Stage show → `[Stage]`. Meeting fan IRL → `[FanMeet]`. Walkthrough → `[Tour]`.

## Step 3.2: Speaker-Change Attribution (Video Audio vs Boat Voice)

YouTube ASR marks audio-source switches with `>>` prefixes (`isSpeakerChange: 1`); they survive into chunk XML. When Boat plays an external video, the transcript mixes the video's audio with Boat's own voice. Separate them by content, NOT by the marker:

- **`>>` is a generic speaker-change marker, not a boat-vs-video splitter.** Boat's own lines can carry `>>` (e.g. `>> คือขอพลอตก่อน...` plot critique). Attribute by content.
- **Video audio** = the clip's speaker narrating in first person about its own content: `ผมเขียนบทครั้งแรก`, `ด้วยเงินทุนภาคละ 300 ล้านบาท`, plot/story narration, news-anchor delivery.
- **Boat voice** = deictic framing referencing the video's person/subject: `เขา/แก` ("แกโมเยอะไปนิดนึง"), playback commands (`แป๊บนึง`, `เดี๋ยวเอาช่วงนี้`, `นี่ไง`, `เปิดให้ดู`, `มาเปิดคลิป`), reactions (`โอ้โห`, `ฮา`, `เฮ้ย`).
- **Silence** = transcript gap; the video is playing without captioned speech. Still the SAME reaction moment, not a new topic.

**Tagging consequence:** Boat silent while the video plays + Boat talking over it = ONE timestamp describing the reaction. Tag describes what's on screen: external video playback → `[Reaction]`; if the video is news content → `[News]`; episode/long-form watch-along → `[WatchParty]`. Never split watching vs talking-while-watching into two stamps.

## Step 3.5: Garbled-English + Contextual Safety Gate (Before Writing)

If the chunk has been through `clean_garbled_english.py`, most English loanwords
(One Punch Man, MAPPA, JC Staff, footage, adapt, original) are already normalised.

### A. Garbled-English Spotting (STRICT SPOTTER ONLY — NO GUESSING)
If you see partially garbled English or Thai-Latin hybrid words (e.g. half-Thai-half-English words, unrecognizable names, game titles that look corrupted):

1. **DO NOT GUESS or hallucinate corrections.** Never invent a replacement target.
2. **Emit a GARBLED_NOTE for any garbled word you spot.** After your timestamp lines, output a `GARBLED_NOTES:` block — one line per garbled token with its timestamp and chunk:
   ```
   GARBLED_NOTES:
   - "ดองซam" @ <timestamp> (chunk_<NN>)
   ```
   Rules:
   - Spot ONLY real garbles (Thai-Latin hybrids that survived cleaning), NOT standard English loanwords like `FGO`, `NP`, `YouTube`.
   - FORBIDDEN: Do NOT output `-> <target>` or attempt to guess the correct word. The central `whisper_dispatcher` will automatically slice and transcribe the exact audio via `whisper.cpp` for 100% phonetic ground truth.
   - If no garbles found, omit the block entirely.

### B. Contextual Plausibility Check (Prevents Game-Hallucination)
**Every game/anime name you write MUST appear in (or be unambiguously implied by)
the transcript text you see.** Rules:

1. **Cross-reference**: If the transcript discusses Blue Archive gacha mechanics,
   do NOT write "WuWa" or "Genshin" even if those names appear in the same chunk.
   The PRIMARY topic by volume determines the game.

2. **Single-mention trap**: If a game name appears only ONCE in garbled form
   (e.g. "บัวใคร") and the remaining 59+ transcript lines are about a different
   topic (economy, movies, etc.), DO NOT name that game — describe the event.

3. **Dominant topic wins**: When transcript mixes games, count lines. The game
   with the most discussion lines is the timestamp's subject. Mention other games
   only in description, never as the primary title.

4. **ASR ghost names**: The following are common ASR phoneme-garbles that do NOT
   represent real titles:
   - `บัวใคร` → is `Blue Archive`, not a real game called "Bua Krai"
   - `Wing Wave` → is `Wuthering Waves` / `WuWa`, not a real game called "Wing Wave"

### C. Hallucination Rule
If all game names in the chunk are garbled AND you cannot confidently resolve
them → output `[Talk]` tag with event description only. Never invent a game title.

**Never guess. If unsure → describe the event, not the title.**

## Step 3.6: Thai LiveChat Subculture & Psychology Interpretation Rule
When analyzing Thai live chat or viewer comments:
- **Do NOT interpret literally.** Apply Thai internet subculture psychology.
- **Reverse Meaning / Playful Envy:** Fake anger/boredom ("เบื่อว่ะ", "กด dislike ละ") when streamer gets rare gacha = playful envy & celebration, not real anger.
- **Ironic Cults / Overhype:** Hype for 1-star/trash units ("Eric คือ META", "ทพจร.") = intentional meme banter, not genuine meta strategy.
- **Parasocial Memes:** Community claims ("ผัวคุณซากิ", "เมียผม") = friend support meme jokes.
- **Coping Comedy:** Screaming at gacha failure ("โดนน้ำมนต์/โดนไล่ผี") = slapstick entertainment.

## Step 4: Story Enrichment (For [Story] Entries Only)

If tag = `[Story]` AND source game/scene is identifiable:

1. **Identify Source:** Extract game title + chapter/scene name from transcript or frame.
2. **Ask User:**
   ```
   Found story segment from [Game Title] — scene: [desc].
   Search web for official synopsis to enrich timestamp? (y/n)
   ```
3. **If yes** → run `fetch_story_ref.py --game "Title" --scene "desc"` → append `(ref: game script)` to description.
4. **If no** → use existing description as-is.
5. **Cache reuse:** If synopsis already cached, use it without asking again.

Format: `[Story] [Game] [Chapter/Scene] — [Synopsis] (ref: game script)`
Keep total ≤ 12 words.

Load `references/stream/story-enrichment.md` for full protocol.

## Step 5: Analyze Talk & Conversation Flow (Talk-Heavy Chunks)
If chunk is primarily talking/chatting:
- Track MACRO topic only. Multiple paragraph shifts = same timestamp if same conversation thread.
- Q&A/interview format: explicit question frames ("เดี๋ยวตอบคำถามนี้",
  "ปู่ปู่ว่า...") reset topic. Do NOT merge across question boundaries.
- Chat/donation cues: "ในแชทบอกว่า", "คุณ... บอกว่า" → tag as `[Chat]` or `[Donation]`.
- Storytelling during gameplay (including One Piece political metaphors) → use `[Talk]`/`[News]`, not gaming tags, unless major game event interrupts (Boss/Death/Victory).

> [!IMPORTANT]
> **Macro vs Micro Topic (Negative Example):**
> - ❌ **WRONG (Micro/Specific):** `[Talk] พูดถึงงานแข่ง Wuthering Waves eSports` (WuWa was only a minor example mentioned in passing).
> - ✅ **CORRECT (Macro Topic):** `[Talk] เม้าท์มอยดราม่างานเกมในไทยจัดวันชนกันยับ (HoYoFest / สาวม้า / LoL / WuWa)` (The core macro topic is the massive event date clash in Thailand).
> Always identify the overarching drama/issue being discussed, not just the first specific game mentioned.

## Step 5.5: Infer Situation + Emotion of the Live (Thai-aware)

**REQUIRED — before writing any description, form a verdict for the chunk:**
`SITUATION: <what is actually happening> | TONE: <funny / hype / shock / tense / sad / calm / meme>`

The verdict is not output — it drives the wording in Step 6. If you cannot name a tone, the chunk is calm: write the neutral description.

Detect tone from BOTH sides:
- Talker side: Thai word choice + sentence particles (`วะ/เว้ย/จัง/ไป`, exclamations `โอ้ย/เฮ้ย/อ้าว`), shouting, repetition, laughter.
- Chat side: message density spikes, emotes, 555 spam, SUPERCHAT/donation surges — these mark real peaks the talker may not name.

**The description's FIRST VERB encodes the tone. Pick it from the recipe:**

| TONE (verdict) | description starts with |
|----------------|--------------------------|
| funny / meme / tease | แซว, ฮา, ขำ, เม้าท์มอย, โยกเย้ย, แหย่, ล้อ, ปั่น, ตบมุก, ขยี้, หยอก, ช็อต, กวน, แซะ |
| hype | โหด, อลังการ, จัดเต็ม, โคตร, ตะโกน, เฮลั่น, ช็อกหนัก, กระโดดดีใจ |
| shock | อึ้ง, ตกใจ, โอ้ย, ไม่เชื่อ, เหวอ, ช็อก, งงตาแตก, ช็อกตาค้าง |
| tense / clutch | ลุ้น, กระชั้น, หวิด, หืดจับ, สิ้นหวัง, โอดครวญ |
| frustration / rant | เซ็ง, เฮ้อ, กาก, แพ้, บ่น, จวก, สับ, ฉอด, โวยวาย, สบถ |
| sad | อกหัก, เศร้า, คิดถึง |
| news / serious | วิเคราะห์, เตือน, สรุป, ประกาศ, แฉ, สาวไส้, กางหลักฐาน, เจาะลึก, ชำแหละ |


Only a calm/serious chunk uses the neutral verbs (พูดคุย, วิเคราะห์, แนะนำ,
อธิบาย, ดู). Funny/hype/shock descriptions may end with a register particle
(วะ, อ่ะ, เย้, ไปเลย) or echo the streamer's actual exclamation (โอ้ย, เฮ้ย).

**Do NOT flatten — contrast (Real Case Examples):**

1. **Trash-Unit Hyping / Meme Archetype (e.g. Eric Bloodaxe / 1-star / 2-star):**
   - ❌ **FLAT:** `[Talk] วิเคราะห์และทดสอบการใช้ตัวละคร 2 ดาว Eric Bloodaxe ในด่านท้าทาย`
   - ✅ **FUNNY / THAI HUMOR:** `[Talk] ฮาแซวความกาก Eric Bloodaxe พร้อมเถียงแชทเดือดเรื่องอัดจอก 2 ดาว`

2. **Gacha Failure & Salt / Coping Comedy:**
   - ❌ **FLAT:** `[Gacha] ประสบความล้มเหลวในการสุ่มได้ตัวละครที่ต้องการจากตู้กาชา`
   - ✅ **FUNNY / THAI HUMOR:** `[Gacha] ฮาแชททักโดนน้ำมนต์! สุ่มเกลือยับตู้การันตีพร้อมเสียงโอดครวญ`

3. **15 HP / Clutch Victory:**
   - ❌ **FLAT:** `[Victory] เคลียร์ด่านท้าทายสำเร็จโดยมีตัวละครรอดชีวิตบางส่วน`
   - ✅ **FUNNY / THAI HUMOR:** `[Victory] ปาฏิหาริย์! Eric Bloodaxe เลือดเหลือ 15 ปั๊มชนะด่านท้าทายเฉียบขาด`

4. **Fluked Luck / Reverse Psychology ("กด dislike ละ"):**
   - ❌ **FLAT:** `[Donation] ผู้ชมแสดงความไม่พอใจเมื่อสุ่มได้ตัวละคร 5 ดาว`
   - ✅ **FUNNY / THAI HUMOR:** `[Donation] ฮาแชทอิจฉาแซว! กดสุ่มได้ SSR จนโดนขู่กด Dislike`

5. **Serious vs Meme Contrast:**
   - ❌ `[Death] ประสบปัญหาในการต่อสู้เมื่อศัตรูไม่ติดสถานะสตั้น`
   - ✅ `[Death] อึ้ง! ศัตรูสตั้นไม่ติด ตีสวนกลับตายยกชุด`

Do NOT overstate: if the live is calm about a gacha fail, do NOT write words that sound genuinely devastated — Step 3.6 reverse psychology (playful envy = celebration) and coping comedy apply. "กด dislike" banter is happiness, not anger.

**Use tone to set density:** hype / meme / donation-peak moments → 1-2 min micro-stamps; quiet continuation → merge to fewer/1. Emotion is never a free extra stamp — it only guides wording + density.

## Step 6: Write Description
- Load `references/stream/timestamp-description.md`.
- If KNOWLEDGE FILES are provided, use them for canonical names. Whisper often transcribes game/character names phonetically.
- **STRICT LENGTH CAP: Max 10–12 words (~100 chars max).** Ultra-concise, punchy single phrase. No multi-clause sentences or filler.
- **Non-Spoiler Gacha Policy (`[Gacha]`):** Do NOT spoil whether the streamer won, lost, or got salt in the initial gacha timestamp description. Focus on the anticipation, featured character, and chat bets/superstitions (e.g. `[Gacha] ลุ้นเปิดกาชา เรมิเอล (Remielle) ใน ZZZ วัดดวงท้าทายอาถรรพ์เพลงเกลือ` instead of spoiling `[Gacha] สุ่มได้ เรมิเอล สำเร็จ`).
- **18+ / Rule 34 / NSFW Tone Policy:** Do NOT trivialize adult fanart, Rule 34, or 18+ internet meme commentary under generic comedic tags (avoid `[Reaction] ฮา...`). Use `[Talk]` with mature, direct, and accurate wording (e.g. `[Talk] เม้าท์มอยคลิปอนิเมชัน 18+ บน Twitter และประเด็นเสียงพากย์วิปครีมสาย Rule 34`).
- **Multi-Topic Preservation:** If a chunk contains distinct major subjects (e.g. meme discussion → banner pull planning → meta analysis) lasting >2–3 minutes each, emit separate timestamps rather than collapsing them into a single tag.
- Macro summary only. Language: <User's Requested Language>.
- Use exact technical terms, game names, character names. No invented names.
- **Multilingual Naming Rule:** 
  - **New Character Reveals / Introductions:** Append canonical English/Japanese name in parentheses: `[Local Name] (English / 日本語)` e.g., `อัสคาลาพอส (Ascalaphos / アスカラポス)`.
  - **Familiar Characters / Story Reading / Analysis:** Use familiar Thai nicknames/names only (e.g. `มาชู`, `ก๊อดดอฟ`) without parentheses.
- If unsure of a name → omit it, describe the event instead.
- For `[Donation]`, classify into Serious, Joke, Q&A, or Weird, and match description style specified in `references/stream/donation-classifier.md`.

## Step 7: Format Output
`HH:MM:SS - [Tag] Description`

One line per timestamp. No headers, no intro, no explanation text.

## Step 8: Visual Reference Resolution
If a transcript item contains an `"image"` field:
1. You MUST call `view_file` to load and inspect that image BEFORE writing the description.
2. Use what you SEE on screen (game UI, boss name, HUD) to confirm the game title and activity.
3. **NEVER name a game from transcript text alone if an image is available.** Transcript text is auto-generated and may misidentify the game. The screen is ground truth.
4. If the image is unclear, describe what you see rather than guessing the name.

Also use vision when the streamer discusses technical setups, file formats/codecs (WebM/AV1), on-screen errors, or game UI details that audio transcript glosses over — extract relevant video frames via `ffmpeg` and inspect with `view_file` to confirm exact context.

## Step 9: Density Self-Check (BEFORE submitting)
Count your timestamps. If you have more than 2 for this chunk, you MUST merge until ≤ 2.

Merge (never output 0 except empty chunk):
- Chunk starts mid-ongoing-topic → merge into 1 timestamp covering this + previous
- Two consecutive `[Talk]` timestamps about same conversation → merge
- Sub-topic shift within same game session → merge
- "They mentioned a new detail" → add to existing description, no new line

**WHOLE-CHUNK UNDERSTANDING CHECK (before submitting):**
- Every stamp must trace to a specific event you actually read in the transcript AND (when present) the LiveChat log. Delete any stamp you cannot source.
- If chat shows a donation/hype spike you skipped, re-read and re-stamp.
- If you cannot confirm a single dominant topic from full reading → output NOTHING and say so. Do not fabricate.
- You are graded on the whole 5-minute chunk, not the first lines.

TRANSCRIPT JSON:
<Orchestrator: inject full JSON content of this 5-minute chunk here>
```
