---
name: anibon-world-identity
description: Verify game world, character, and location names against local references before writing story timestamps. Loaded by anibon-timestamper when the stream covers post-cutoff games.
disable-model-invocation: true
---

# Anibon World Identity Verification

## Overview & Triggers

> LLMs hallucinate game names from post-cutoff patches. Thai Whisper output is phonetic — model wrong on both sources. Must verify against local references.

## Priority Chain

Local references → cached story refs → reference SRT → websearch fallback

### a. Check local game & event references

`references/INDEX.md` lists available game, Tokusatsu, and cultural event knowledge files (including anime gacha games, Tokusatsu / Project R.E.D. like `Tokusatsu_Project_RED.md`, and Japanese event conventions/cuisines like `Japan_Event_Convention.md`). This is the fastest and most reliable source.

### b. Check cached story refs

`python3 scripts/fetch_story_ref.py --list` or browse `references/stories/` for previously fetched synopses (dir is auto-created on first fetch).

### c. Reference SRT (if reference video URL exists)

```bash
yt-dlp --write-subs --sub-lang en --skip-download <ref_url>
python3 scripts/align_ref_timeline.py <srt> <chunks/> > alignment.json
```

Parse SRT for character/location names. Use `align_ref_timeline.py` to match ref timestamps against stream chunks automatically.

### d. Build name map

Thai transcript phoneme → verified EN name from sources above

### e. Scan chunks at story boundary

For each candidate, match against verified map

### f. Websearch & Live-Service Version Research Fallback (`anibon-live-service-researcher`)

Only if local + cached + SRT all insufficient, OR when the stream covers a fresh live-service patch/game missing from `references/<Game>.md`:

1. **Quick scene synopsis fetch**:
```bash
python3 scripts/fetch_story_ref.py --game "HSR" --scene "Planarcadia 4.0"
```

2. **Full Live-Service Version & Patch Chronology Research (`anibon-live-service-researcher`)**:
When a live-service game in `references/<Game>.md` is outdated or unindexed, dispatch the **`anibon-live-service-researcher`** subagent via `invoke_subagent`:
- **Step 1**: Checks real-time date (`time.is` / UTC clock) to lock current month and year.
- **Step 2**: Finds the **current live version (`V_0`)** and **next upcoming version (`V_+1`)** for that month/year.
- **Step 3**: Recursively traces backward **at least 3 versions** from `V_0` (`V_-3`, `V_-2`, `V_-1`, `V_0`, bridging any gap to the last version in `references/<Game>.md`).
- **Step 4**: Audits every version from **oldest to latest** for: (a) changes/QoL, (b) system updates/events, (c) new gacha characters/banners (EN + Thai names, element, role/path), and (d) new story chapters/arcs.
- **Step 5**: Updates `references/<Game>.md`, `references/INDEX.md`, `references/thai_phonetic_bridge.json`, and `resources/knowledge.json`.

### g. Reject

Training-data inference, older-version character, unconfirmed phonetic match

## Version Chronology Verification

When a stream covers a version update or special program for a live-service game (Genshin, HSR, ZZZ, WuWa, etc.):
1. **Match Version to Nation/Arc**: Consult the version chronology table in `references/<Game>.md`. Verify which nation/arc the patch belongs to before assigning titles to sections, characters, or bosses.
2. **Anti-Callback Conflation**: Streamers regularly mention older regions/patches to compare character balance or meta history (e.g. Boat referencing 6.x Nod-Krai during the 7.2 Snezhnaya stream). Do NOT mistake a historical comparison for the active patch location.
3. **Character Affiliation Integrity**: Verify newly announced characters against the active version table. New characters belong to the active patch nation unless explicitly documented otherwise.
4. **Top-1800-Char Live Patch Snapshot Contract (`_WI_SNIPPET_LIMIT`)**: Local chunk prompts only inject the first `1,800` characters of `references/<Game>.md`. Always place a compact `## 🔥 สถานะแพตช์ล่าสุด (Current Live Patch)` summary (active event/version, newest banner units/terms, and top phonetic ASR mappings) **at the very top before the first `---` separator**, keeping total header length `<= 1,800` characters while full oldest-to-latest tables sit below `---`. Verify character count (`<= 1800`) after every edit.

## DB Bootstrap

Run these from plugin root (`anibon-stream-synthesis`) before World Identity lookups for applicable games:

```bash
python3 skills/anibon-world-identity/scripts/fetch_fgo_db.py --check --db "skills/reference/FGO and DATA/atlas_fgo.db" || \
  python3 skills/anibon-world-identity/scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"
python3 skills/anibon-world-identity/scripts/fetch_ygo_db.py --check --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db" || \
  python3 skills/anibon-world-identity/scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
python3 skills/anibon-world-identity/scripts/fetch_pokemon_db.py --check --db "skills/anibon-world-identity/references/Pokemon DATA/pokemon.db" || \
  python3 skills/anibon-world-identity/scripts/fetch_pokemon_db.py --db "skills/anibon-world-identity/references/Pokemon DATA/pokemon.db"
```

> **SQLite Table Note**: `atlas_fgo.db` stores Servants in `basic_servant(collectionNo, name, originalName, className, rarity, type)`, not `servants`.
> **Freshness Check (Live-Service Streams)**: `--check` only validates local SQLite table integrity and exits `0` even when behind Atlas Academy's live export. For recent FGO JP streams (≤ 7 days old) or when chat mentions a brand-new Servant, run `fetch_fgo_db.py --force --db "skills/reference/FGO and DATA/atlas_fgo.db"` before Pass 1 so new `collectionNo` entries populate `entity_glossary.json`.

## Mandatory Pokémon Naming Rules

Whenever any Pokémon species, entity, or stream topic is detected:
1. **Primary Name MUST be in Thai**: Always output the Thai community/English-sound name (`name_th_english_sound`) or official Thai name (`name_th_official`) first.
   - Example: `แบกซ์แคลิเบอร์ (Baxcalibur)`, `ม้าดำ (Spectrier)`, `การ์โชมป์ (Garchomp)`, `เป็ดต้นหอม (Farfetch'd)`.
2. **Dual-Lookup Verification**: Cross-check candidate strings against `references/Pokemon DATA/pokemon.db` matching `name_en`, `name_th_official`, or `name_th_english_sound`.
3. **No Bare English Names**: Never output bare English Pokémon names alone (e.g. write `แบกซ์แคลิเบอร์ (Baxcalibur)` or `แบกซ์แคลิเบอร์`, not just `Baxcalibur`).

## Post-Stream Knowledge Harvesting Protocol

Execute immediately after `anibon_timestamps.md` passes all parity gates:
1. **Audit Unverified Entities**: Inspect `audit_timestamps_against_glossary` warnings for new proper nouns, game titles, or unindexed lore.
2. **Category Routing**:
   - **New Game/Franchise**: Scaffold `references/<Franchise>.md` (standard table or bold bullets) and link in `references/INDEX.md`.
   - **Existing Franchise**: Append new patch/character/mechanic notes to `references/<Franchise>.md`.
   - **Phonetic Corrections**: Add confirmed Whisper drift patterns to `resources/garbled_replacements.json` via `update_garbled_dictionary.py`.
   - **Short Thai Pattern Guard**: Never add unanchored Thai substrings `<= 4` chars to `garbled_replacements.json` without verifying they cannot match inside Sinner/character names or common Thai words.
3. **Play History Scope Discipline (GAME-ONLY CONTENT INVARIANT - STRICT)**:
   - When recording or updating `Stream Chronology & Play History` in `references/<Game>.md`, include **ONLY topics, mechanics, builds, gear, boss encounters, exploration, questlines, and engine/hardware issues directly regarding that game**.
   - **Strict Ban on Unrelated Talk Topics**: Never include political debates (US, French, Thai politics), personal anecdotes (food, loans, life stories), societal critiques, or reviews of unrelated movies/anime/games in a game's reference file.
   - General stream discussions belong in timestamps (`anibon_timestamps.md`), NEVER in game-specific world identity files.
4. **Integrity Check**: Run `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_knowledge_reader.py` to confirm knowledge files parse cleanly.

## When to Skip

- Stream covers well-known characters/games within training data cutoff
- No game/character names detected in the chunk signal
- User explicitly says "no need to verify"
