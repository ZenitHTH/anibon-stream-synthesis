# Skills

## Skill Inventory

| Skill | Purpose | Key Integrations |
| :--- | :--- | :--- |
| [`synthesizing-knowledge`](../skills/synthesizing-knowledge/SKILL.md) | Deep research & report synthesis | Delegates long videos to `youtube-minutes-synthesis` |
| [`youtube-minutes-synthesis`](../skills/youtube-minutes-synthesis/SKILL.md) | Meeting-minutes from YouTube videos | Calls `cleaning-auto-transcripts` first |
| [`anibon-timestamper`](../skills/anibon-timestamper/SKILL.md) | Stream orchestrator — auto-detects type & routes to sub-skills | Orchestrates all `anibon-*` sub-skills via parallel signal detection |
| [`anibon-timestamper-local`](../skills/anibon-timestamper-local/SKILL.md) | Local stream orchestrator — sequential loop & goldfish brain rules | For local AIs (Ollama) with restricted context |
| [`anibon-timestamper-handoff`](../skills/anibon-timestamper-handoff/SKILL.md) | Session state saving & loading for local timestamper | Resolves context exhaustion on long runs |
| [`cleaning-auto-transcripts`](../skills/cleaning-auto-transcripts/SKILL.md) | Transcription noise correction | Powers `anibon-timestamper` and `youtube-minutes-synthesis` |
| [`masking-royal-news`](../skills/masking-royal-news/SKILL.md) | Sensitive political/royal content masking | Single source of truth for public safety compliance |
| [`building-reusable-cli-tools`](../skills/building-reusable-cli-tools/SKILL.md) | CLI tool design guidance | Referenced when writing new processing scripts |
| [`writing-plugin-readme`](../skills/writing-plugin-readme/SKILL.md) | README writing guidelines | Guidance for formatting this plugin's README files |
| [`whisper-corruption-recovery`](../skills/whisper-corruption-recovery/SKILL.md) | Whisper repetition-loop detection & recovery | Load before `anibon-timestamper` for streams ≥4h or with suspiciously short transcripts |
| [`antigravity-vision-proxy`](../skills/antigravity-vision-proxy/SKILL.md) | Proxy image analysis via agy + Gemini | Frame extraction + vision model invocation for game/hero identification |

## anibon-timestamper Sub-Skills

Nested under [`../skills/anibon-timestamper/references/`](../skills/anibon-timestamper/references/). The orchestrator **auto-detects** which sub-skill(s) to load by scanning transcript signals.

| Sub-Skill | Detection Signal | Tags |
| :--- | :--- | :--- |
| [`anibon-talk-stream`](../skills/anibon-timestamper/references/talk-stream.md) | Long monologues, reading chat, news, lore/story tangents, coded political talk | `[Talk]` `[News]` `[Chat]` `[Q&A]` `[Donation]` |
| [`anibon-gaming-stream`](../skills/anibon-timestamper/references/gaming-stream.md) | Game-specific jargon dominates, sparse verbal reactions | `[Boss]` `[Death]` `[Victory]` `[Stage]` |
| [`anibon-marathon-stream`](../skills/anibon-timestamper/references/marathon-stream.md) | Multiple distinct game titles in sequence | `[GameSwitch]` `[Session]` |
| [`anibon-event-stream`](../skills/anibon-timestamper/references/event-stream.md) | Patch note reading, new event content, theorycrafting | `[Event]` `[PatchNote]` `[Theory]` |
| [`anibon-tokusatsu-stream`](../skills/anibon-timestamper/references/tokusatsu-stream.md) | Tokusatsu franchise names, watch party, multi-speaker panel | `[WatchParty]` `[Reaction]` `[Discussion]` `[Lore]` `[Tierlist]` `[Review]` |

## Knowledge Base References

Nested under [`../skills/anibon-timestamper/skills/reference/`](../skills/anibon-timestamper/skills/reference/). Structured lore and chronology for live service games discussed in streams.

- [miHoYo Connected Lore](../skills/anibon-timestamper/skills/reference/miHoYo_Connected_Lore.md) — HI3 / Honkai Star Rail / Genshin connected universe
- [Honkai Impact 3rd](../skills/anibon-timestamper/skills/reference/Honkai_Impact_3.md) — Part 1/1.5 chronology, battlesuits, mechanics
- [Honkai Impact 3rd Part 2](../skills/anibon-timestamper/skills/reference/Honkai_Impact_3_Part2.md) — Mars chronology, characters
- [Honkai: Star Rail](../skills/anibon-timestamper/skills/reference/Honkai_Star_Rail.md) — Patches, banners, meta teams
- [Genshin Impact](../skills/anibon-timestamper/skills/reference/Genshin_Impact.md) — Cities, Archons, Fatui, Descenders
- [Wuthering Waves](../skills/anibon-timestamper/skills/reference/Wuthering_Waves.md) — Character and version roadmap
- [Zenless Zone Zero](../skills/anibon-timestamper/skills/reference/Zenless_Zone_Zero.md) — Versions, agent factions
- [Arknights](../skills/anibon-timestamper/skills/reference/Arknights.md) — Version chronology
- [Arknights: Endfield](../skills/anibon-timestamper/skills/reference/Arknights_Endfield.md) — Setup, dates, gameplay mechanics
- [Limbus Company](../skills/anibon-timestamper/skills/reference/Limbus_Company.md) — Key updates, gameplay styles
- [Pokémon Radical Red](../skills/anibon-timestamper/skills/reference/Pokemon_Radical_Red.md) — Difficulty modes, bosses, Version 4.1
