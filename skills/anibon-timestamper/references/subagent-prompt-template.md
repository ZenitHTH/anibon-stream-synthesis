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

PREVIOUS CHUNK PRIMARY TOPIC: <Orchestrator: inject topic of previous chunk>
CURRENT CHUNK PRIMARY TOPIC: <Orchestrator: inject topic from detect_signals.py>

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
- `[Donation]`: Speaker responds to paid superchat/donation (Must load `anibon-donation-classifier` to classify description)
- `[Gameplay]`: Playing a game / fighting stages
- `[Gacha]`: Drawing cards / summoning (NEVER reveal pull results)
- `[Boss]`: Boss fight / challenging enemy
- `[Death]`: Notable/funny death in-game
- `[Victory]`: Boss cleared / quest completed
- `[WatchParty]`: Watch-along reaction / episode review
- `[Reaction]`: General reaction to trailers or videos

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
| General overworld walking + fighting trash mobs | `[Gameplay]` | `[Boss]` |
| Boat discusses news/current events | `[News]` | `[Talk]` |

**Rule of thumb:** If the player is FIGHTING a named boss → `[Boss]`. If the player dies → `[Death]`. If the player completes a major objective → `[Victory]`. If the player is farming/running stages → `[Gameplay]`. If Boat looks at external video → `[Reaction]`.

## Step 3.5: Garbled-English + Contextual Safety Gate (Before Writing)

If the chunk has been through `clean_garbled_english.py`, most English loanwords
(One Punch Man, MAPPA, JC Staff, footage, adapt, original) are already normalised.

### A. Garbled-English Check
If you still see partially garbled English (e.g. half-Thai-half-English words,
unrecognisable studio names, game titles that look wrong):

1. Search web to verify the correct name before writing.
2. Common garbles not yet caught by the cleaner:
   - `Kagurabachi` — may be real (business newspaper leak) or hallucinated
   - Studio names with Thai suffixes
   - Romanised Japanese titles with mixed Thai characters

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

Load `anibon-story-enrichment` for full protocol.

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

## Step 6: Write Description
- Load `anibon-timestamp-description`.
- If KNOWLEDGE FILES are provided, use them for canonical names. Whisper often transcribes game/character names phonetically.
- **STRICT LENGTH CAP: Max 10–12 words (~100 chars max).** Ultra-concise, punchy single phrase. No multi-clause sentences or filler.
- Macro summary only. Language: <User's Requested Language>.
- Use exact technical terms, game names, character names. No invented names.
- **Multilingual Naming Rule:** 
  - **New Character Reveals / Introductions:** Append canonical English/Japanese name in parentheses: `[Local Name] (English / 日本語)` e.g., `อัสคาลาพอส (Ascalaphos / アスカラポス)`.
  - **Familiar Characters / Story Reading / Analysis:** Use familiar Thai nicknames/names only (e.g. `มาชู`, `ก๊อดดอฟ`) without parentheses.
- If unsure of a name → omit it, describe the event instead.
- For `[Donation]`, classify into Serious, Joke, Q&A, or Weird, and match description style specified in `anibon-donation-classifier`.

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

TRANSCRIPT JSON:
<Orchestrator: inject full JSON content of this 5-minute chunk here>
```
