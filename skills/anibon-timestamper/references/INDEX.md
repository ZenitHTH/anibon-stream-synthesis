# Knowledge Files

Auto-matched by signal terms. See `detect_signals.py --match-knowledge` for the matching mechanism.

## Stream Type Knowledge

| File | Matched By | Always Loaded |
|------|-----------|:---:|
| `stream/talk-stream.md` | talk, discussion, chat | |
| `stream/gaming-stream.md` | game, gameplay, play | |
| `stream/event-stream.md` | event, update, patch | |
| `stream/tokusatsu-stream.md` | kamen, super sentai, ultraman, tokusatsu | |
| `stream/marathon-stream.md` | marathon, subathon, long stream | |

## Domain Knowledge

| File | Matched By | Always Loaded |
|------|-----------|:---:|
| `stream/timestamp-description.md` | — | ✅ defines 4-pillar framework |
| `anibon_emoji_dictionary.md` | livechat, emoji, emote, 555 | ✅ defines emote subculture weights |
| `stream/donation-classifier.md` | donate, superchat | |
| `stream/fgo-knowledge.md` | FGO, fate, grand, order, servant | |
| `stream/uwufufu-knowledge.md` | uwufufu, bracket, world cup | |
| `stream/phuboat-anime-talking-style.md` | anime, manga | |
| `stream/story-enrichment.md` | story, lore, plot | |

## Game References

`../anibon-world-identity/references/INDEX.md` — game-specific files matched by game name (canonical game reference files live in `anibon-world-identity/references/`)

## Cached Story Synopses

`references/stories/` — cached by `fetch_story_ref.py`, matched by scene/game name
