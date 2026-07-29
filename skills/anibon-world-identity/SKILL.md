---
name: anibon-world-identity
description: Verify game world, character, and location names against local references before writing story timestamps. Loaded by anibon-timestamper when the stream covers post-cutoff games.
disable-model-invocation: true
---

# Anibon World Identity Verification

> LLMs hallucinate game names from post-cutoff patches. Thai Whisper output is phonetic — model wrong on both sources. Must verify against local references.

## Priority Chain

Local references → cached story refs → reference SRT → websearch fallback

### a. Check local game references

`references/games/INDEX.md` lists available game knowledge files. Each covers patch chronologies, character names, faction lists for major gacha games. This is the fastest and most reliable source.

### b. Check cached story refs

`python3 scripts/fetch_story_ref.py --list` or browse `references/stories/` for previously fetched synopses.

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

### f. Websearch fallback

Only if local + cached + SRT all insufficient:

```bash
python3 scripts/fetch_story_ref.py --game "HSR" --scene "Planarcadia 4.0"
```

### g. Reject

Training-data inference, older-version character, unconfirmed phonetic match

## DB Bootstrap

Run these before World Identity lookups for applicable games:

```bash
python3 scripts/fetch_fgo_db.py --check --db "references/FGO and DATA/atlas_fgo.db" || \
  python3 scripts/fetch_fgo_db.py --db "references/FGO and DATA/atlas_fgo.db"
python3 scripts/fetch_ygo_db.py --check --db "references/Yu-Gi-Oh DATA/ygo_cards.db" || \
  python3 scripts/fetch_ygo_db.py --db "references/Yu-Gi-Oh DATA/ygo_cards.db"
```

## When to Skip

- Stream covers well-known characters/games within training data cutoff
- No game/character names detected in the chunk signal
- User explicitly says "no need to verify"
