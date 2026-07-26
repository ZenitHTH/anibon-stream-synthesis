# Project Reference

## Directory Structure

```
scripts/                          Root-level Python utilities
  prepare_video.py                All-in-one download, clean, chunk
  pack_timestamps.py              Flat timestamp packer → parts + markdown
  clean_transcript.py             Space normalization & MapReduce chunking
  check_sections.py               YouTube comment byte-size checker
  anibon-analyzer.py              Gap detection & chunk classifier
  fetch_fgo_db.py / fetch_ygo_db.py  DB bootstrap scripts
  plan_highlight.py / cut_highlight.py / verify_highlight.py  Video highlight tools
skills/                           Agent skills
  anibon-timestamper/             Main orchestrator
    scripts/                      Specialized sub-scripts (DB fetchers, merge, validate, story ref)
      fetch_story_ref.py          Websearch + cache story synopses for [Story] enrichment
    references/                   Cross-stream references
      stream/                     Talk, Gaming, Marathon, Event, Tokusatsu, Donation, Macros
        story-enrichment.md       Protocol: source ID → ask user → enrich timestamp
      stories/                    Cache dir for fetched story synopses (.md files)
    skills/                       Sub-skills (Talk, Gaming, Marathon, Event, Tokusatsu)
      reference/                  Game lore files + SQLite DB schemas
    skills/reference/FGO and DATA/   FGO: atlas_fgo.db (~1.9 MB)
    skills/reference/Yu-Gi-Oh DATA/  Yu-Gi-Oh: ygo_cards.db (~13.4 MB)
  synthesizing-knowledge/
  youtube-minutes-synthesis/
  cleaning-auto-transcripts/
  masking-royal-news/
  building-reusable-cli-tools/
  writing-plugin-readme/
  whisper-corruption-recovery/
  antigravity-vision-proxy/
tests/                            Unit and integration tests
plugin.json / package.json / hooks.json / gemini-extension.json   Plugin configs
```

## Script Reference

> **Ponytail Rule:** One script to rule them all. Never build complex multi-line bash/powershell prompt orchestrations when one Python script handles cross-platform setup flawlessly.

Scripts live in `scripts/` (root-level utilities) and `skills/anibon-timestamper/scripts/` (DB fetchers, merge, validate). At runtime, find them with:
```bash
find $HOME/.gemini $HOME/.config/opencode $HOME/.agents -name <script>.py 2>/dev/null | head -1
```

### `prepare_video.py` — Transcript Download & Chunking

Single-command workspace setup. Creates `youtube_VIDEO_ID_workspace/`, downloads transcript via `yt-dlp`, cleans and chunks.

```bash
python3 scripts/prepare_video.py <VIDEO_URL_OR_ID>
python3 scripts/prepare_video.py <VIDEO_URL_OR_ID> --vision   # Also extract frame images
python3 scripts/prepare_video.py <URL> --format xml --block 300 --overlap 30 --vision
```

With `--vision`, downloads a low-resolution (≤ 480p) reference copy for visual pronoun disambiguation.

### `pack_timestamps.py` — Timestamp Packer & Assembly

Packs flat chronological timestamp list into byte-limited parts using **greedy fill** (minimum part count at byte_limit, preserves tag continuity). Writes both `.md` and `parts.json`.

**v1.1.3+ algorithm:**
1. **merge_consecutive_story()** — collapse adjacent `[Story]` entries (keeps first timestamp + description)
2. **cluster_by_tag()** — group consecutive entries by macro tag (TALK, GAMEPLAY, CUTSCENE)
3. **Greedy fill** — pack to body_limit, start new part on overflow
4. **Title preference** — within same macro-tag group, skip `[Story]` entries for title if `[Talk]`/`[Reaction]` exist

```bash
python3 scripts/pack_timestamps.py /path/to/timestamps.txt
python3 scripts/pack_timestamps.py /path/to/timestamps.txt --byte-limit 3500 --output output.md
```

Input format (one per line): `HH:MM:SS - [Tag] Description`

**TAG_MACRO_MAP:** `Story`→`TALK`, `WatchParty`→`NEWS` for density-aware grouping.

### `clean_transcript.py` — Normalization & Chunking

Regex mapping, UTF-8 normalization (critical for Windows PowerShell), and chunk generation.

```bash
python3 scripts/clean_transcript.py raw_transcript.json > cleaned.json
python3 scripts/clean_transcript.py raw_transcript.json --chunk --chunk-dir chunks --block 300 --overlap 30
```

### `check_sections.py` — YouTube Comment Size Validator

Flags sections exceeding YouTube's Thai character limit. Run after assembly.

```bash
python3 scripts/check_sections.py anibon_timestamps.md
# Output: ✅ OK / ⚠️ WARN (>4,500) / ❌ OVER (>5,000) per section
```

### `fetch_story_ref.py` — Story Synopsis Fetcher & Cache

Websearches for official game story synopsis when subagent detects `[Story]` and identifies source game/scene. Requires user confirmation before searching.

```bash
python3 scripts/fetch_story_ref.py --game "FGO" --scene "Babylonia Tiamat war"
python3 scripts/fetch_story_ref.py --list   # Show cached entries
python3 scripts/fetch_story_ref.py --game "HSR" --scene "Penacony Sunday" --cache /path/to/cache
```

Cache: one `.md` file per unique game+scene slug in `skills/anibon-timestamper/references/stories/`. Cache hits skip websearch. Synopsis ≤ 100 chars, appended to timestamp as `(ref: game script)`.

### `fetch_fgo_db.py` — FGO Database Bootstrap

Downloads FGO JP data from [Atlas Academy API](https://api.atlasacademy.io). Builds `atlas_fgo.db` (~1.9 MB). Version-aware — skips if local DB matches live game version.

```bash
python3 scripts/fetch_fgo_db.py --check --db "skills/reference/FGO and DATA/atlas_fgo.db"
python3 scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"
python3 scripts/fetch_fgo_db.py --force --db "skills/reference/FGO and DATA/atlas_fgo.db"
```

See [`FGO_DB_Reference.md`](../skills/anibon-timestamper/skills/reference/FGO%20and%20DATA/FGO_DB_Reference.md) for SQL query patterns.

### `fetch_ygo_db.py` — Yu-Gi-Oh! Database Bootstrap

Downloads 14,400+ cards from [YGOPRODeck API](https://db.ygoprodeck.com/api-guide/). Builds `ygo_cards.db` (~13.4 MB). Paginated (2,000 cards/batch).

```bash
python3 scripts/fetch_ygo_db.py --check --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
python3 scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
python3 scripts/fetch_ygo_db.py --force --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
```

See [`YGO_DB_Reference.md`](../skills/anibon-timestamper/skills/reference/Yu-Gi-Oh%20DATA/YGO_DB_Reference.md) for card schema and queries.

## On-Demand Databases

| Game | DB File | Bootstrap Script | Size | Entities |
|------|---------|-----------------|------|----------|
| Fate/Grand Order | `FGO and DATA/atlas_fgo.db` | `fetch_fgo_db.py` | ~1.9 MB | 470 servants, 2.6K CEs, 1.9K items |
| Yu-Gi-Oh! | `Yu-Gi-Oh DATA/ygo_cards.db` | `fetch_ygo_db.py` | ~13.4 MB | 14,422 cards, 43,768 set prints, 640 archetypes |

> Always run `--check` before querying. Exit code 1 → run build script first.

### `whisper-corruption-recovery` — Detection & Recovery

For long audio where Whisper enters repetition loops. Detects corruption by comparing last 20 entries against a window 100 lines back. Recovery: split audio at corruption boundary → segment → re-run per segment → dedup-merge.

```bash
# Detection (run before any downstream processing on ≥2h audio)
python3 -c "
import json
with open('raw_transcript.json') as f: j = json.load(f)
last = [e['text'] for e in j[-20:]]
win = [e['text'] for e in j[-100:-81]]
r = sum(1 for a,b in zip(last,win) if a==b and len(a)>5)
print(f'Corruption ratio: {r/len(last)}')
"
```

### `antigravity-vision-proxy` — Vision Proxy via agy

Stream image analysis when agent lacks vision. Requires `agy` in PATH.

```bash
# Extract frames every 60s
for ($t=0; $t -lt $duration; $t+=60) {
  $ts = "{0:D2}:{1:D2}:{2:D2}" -f [math]::Floor($t/3600),[math]::Floor(($t%3600)/60),($t%60)
  ffmpeg -ss $ts -i full_video.mp4 -frames:v 1 -q:v 2 "frames\frame_$ts.jpg"
}
# Analyze via agy
agy --model "Gemini 3.6 Flash" --dangerously-skip-permissions --print "Identify game and activity per frame" --add-dir frames
```

## Platform Compatibility

Skills are tool-agnostic. Invoke by plain name (`anibon-talk-stream`) — no tool prefix needed.

| Concept | Antigravity | Claude Code | OpenCode | Pi |
|---------|-------------|-------------|----------|-----|
| Run command | `run_command` | `Bash` | native bash | `bash` |
| Fetch web | `read_url_content` | `WebFetch` | WebSearch/bash | `bash` + curl |
| Write file | `write_to_file` | `Write` | native write | `write` / `edit` |
| Spawn subagents | `subagent-driven-development` | `Task` | concurrent tool calls | agent delegation |
| Working dir | artifacts dir | `~/.claude/brain/...` | project subdir | project workspace |
| Temp files | `scratch/` session dir | session-scoped temp | session-scoped temp | session-scoped temp |
