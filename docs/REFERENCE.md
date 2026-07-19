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
    scripts/                      Specialized sub-scripts (DB fetchers, merge, validate)
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

Packs flat chronological timestamp list into byte-limited parts with separator blocks matching the canonical spec. Writes both `.md` and `parts.json`.

```bash
python3 scripts/pack_timestamps.py /path/to/timestamps.txt
python3 scripts/pack_timestamps.py /path/to/timestamps.txt --byte-limit 3500 --output output.md
```

Input format (one per line): `HH:MM:SS - [Tag] Description`

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
