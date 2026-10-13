---
name: anibon-story-enrichment
description: Use when a subagent detects [Story] and identifies source game/scene. Enriches timestamp with original story context via websearch + user confirmation.
---

# Anibon Story Enrichment

When Boat reads story aloud, raw timestamp only says "Boat reads X scene." Enrichment adds source context so viewers know exactly which game/chapter/event.

## Trigger

Apply enrichment when ALL conditions met:
- Tag = `[Story]`
- Source game identified (transcript context or frame inspection)
- Scene/chapter/mission name identifiable
- Description would otherwise be generic ("อ่านฉาก...", "Boat reads dialogue...")

Do NOT enrich if:
- Story segment < 30 seconds (too brief)
- Game title unknown and not identifiable from frames
- Scene is obvious (main menu, tutorial, stream start)

## Enrichment Protocol

### Step 1: Identify Source

Extract from transcript or frame:
- **Game title** (exact name)
- **Chapter/Scene/Mission** name or number
- **Key characters** involved

If game title visible on screen → frame inspection (`view_file`).
If not → derive from transcript, then verify.

### Step 2: Ask User

```
Found story segment from [Game Title] — scene: [desc].
Search web for official synopsis to enrich timestamp? (y/n)
```

Wait for user response.

### Step 3: Fetch Reference

If user confirms `y`:

```bash
python3 scripts/fetch_story_ref.py \
  --game "Game Title" \
  --scene "Chapter/Scene description" \
  --cache "skills/anibon-timestamper/references/stories"
```

Returns: synopsis text (≤ 100 chars) + cache file path.

If `n` → skip enrichment, use existing description as-is.

### Step 4: Enrich Timestamp

Format:
```
HH:MM:SS - [Story] [Game] [Chapter/Scene] — [Synopsis] (ref: game script)
```

Rules:
- Total description ≤ 12 words (~100 chars)
- Game name + scene first, synopsis last
- `(ref: game script)` only for fresh websearch results (not from cache)
- Cache hits assume verified → omit `(ref: ...)`

### Examples

| Before | After |
|---|---|
| Rin and Trailblazer discuss Sparkle's scheme | HSR x FATE collab Ch.4 — Sparkle's Grail trap, Rin detects |
| Castoria explains domain barrier rules | FGO x HSR collab Ch.6 — Castoria's barrier, 7-death limit (ref: game script) |
| Gilgamesh reveals legend of ancient gods | FGO Babylonia — Gilgamesh recounts Tiamat war (ref: game script) |

## Caching

Cache = flat `.md` files in `references/stories/`. One file per unique game+scene key.

Filename pattern: `{game-slug}_{scene-slug}.md`

Cache hit → skip websearch, return cached synopsis directly.
Cache miss → websearch, write to cache, return synopsis.

## Iron Rules

- **Ask user first.** Never websearch without user confirmation.
- **≤ 100 chars.** Enriched description must not exceed 12 words.
- **Source identification is MANDATORY** before enrichment. No "unknown game" enrichment.
- **Frame beats text.** If screen shows game title, trust frame — not transcript guess.
