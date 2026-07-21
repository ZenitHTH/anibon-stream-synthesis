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

## OUTPUT CONTRACT (read before anything else)

One 5-minute chunk → **1 timestamp by default, 2 MAX. (0 is allowed!)**.
A new timestamp is only valid when ONE of these occurs:
- Game switches entirely (different title)
- Speaker joins or leaves (Discord guest, etc.)
- Completely different activity begins (e.g., watching video → playing game)
- A completely NEW topic of conversation begins

**CRITICAL:** If this chunk is simply CONTINUING the exact same topic, story, or game activity from the previous chunk, you should output **0 timestamps**. Do not emit a timestamp just because your chunk started.

Multiple sub-topics within one continuous talk → MERGE into 1 timestamp with broader description, or emit 0 if it's all one long continuous flow.
If unsure → merge. Never split.

## Step 1: Scan and Detect Signals
Read the transcript. Identify the PRIMARY activity of this chunk.
- Gacha pulls, gameplay, talk/news, tokusatsu, watch parties, greetings.
- Match card/game terms against FGO/YGO database records if provided.

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

## Step 4: Analyze Talk & Conversation Flow (Talk-Heavy Chunks)
If chunk is primarily talking/chatting:
- Track MACRO topic only. Multiple paragraph shifts = same timestamp if same conversation thread.
- Chat/donation cues: "ในแชทบอกว่า", "คุณ... บอกว่า" → tag as `[Chat]` or `[Donation]`.
- Storytelling during gameplay (including One Piece political metaphors) → use `[Talk]`/`[News]`, not gaming tags, unless major game event interrupts (Boss/Death/Victory).

## Step 5: Write Description
- Load `anibon-timestamp-description` and apply the 4-pillar framework: Point → Analysis → Impact → Live Comment → **one sentence**.
- Macro summary only. Language: <User's Requested Language>.
- Use exact technical terms, game names, character names. No invented names.
- If unsure of a name → omit it, describe the event instead.
- For `[Donation]`, classify into Serious, Joke, Q&A, or Weird, and match description style specified in `anibon-donation-classifier`.

## Step 6: Format Output
`HH:MM:SS - [Tag] Description`

One line per timestamp. No headers, no intro, no explanation text.

## Step 7: Visual Reference Resolution
If a transcript item contains an `"image"` field:
1. You MUST call `view_file` to load and inspect that image BEFORE writing the description.
2. Use what you SEE on screen (game UI, boss name, HUD) to confirm the game title and activity.
3. **NEVER name a game from transcript text alone if an image is available.** Transcript text is auto-generated and may misidentify the game. The screen is ground truth.
4. If the image is unclear, describe what you see rather than guessing the name.

## Step 8: Density Self-Check (BEFORE submitting)
Count your timestamps. If you have more than 2 for this chunk, you MUST merge until ≤ 2.

Red flags — merge immediately or output 0 timestamps:
- The chunk starts in the middle of an ongoing story/topic → Output 0 timestamps (let the previous chunk's timestamp cover it)
- Two consecutive `[Talk]` timestamps about same conversation → merge
- Sub-topic shift within same game session → merge
- "They mentioned a new detail" → add to existing description, no new line

CRITICAL RULES: <Orchestrator: inject 3-4 bullet Iron Rules from matching sub-skills here>
TRANSCRIPT JSON:
<Orchestrator: inject full JSON content of this 5-minute chunk here>
```
