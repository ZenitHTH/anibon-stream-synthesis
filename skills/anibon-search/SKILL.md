---
name: anibon-search
description: Search the ANIBON livestream archive via anibon_wiki (LLM Wiki synthesis pages, curated stream timelines, and raw snapshots) for topics, games, news, or moments Boat discussed. Use when the user asks "ค้นหา พูดถึงเกี่ยวกับ...", "ปู่โบ๊ตเคยพูดเรื่อง... ในสตรีมไหน", "หาคลิปที่ปู่โบ๊ตวิจารณ์...", or similar archive search queries.
---

# ANIBON Search Skill (`anibon_wiki`-Backed)

## Overview & Principles

### Purpose

Retrieve verified moments, opinions, game sessions, and timestamped clips from the **ANIBON livestream archive** backed by the compiled **`anibon_wiki`** knowledge base (`anibon_wiki/`). Combines fast synthesized overview pages (`games/`, `entities/`, `topics/`) with exact per-stream timestamp lookup (`sources/stream-*.md`) and optional raw `all_timestamps.txt` fallback (`raw/streams/`).

### Source of Truth (`anibon_wiki/`)

All archive data lives inside `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/`:

- **Synthesized Knowledge (`wiki/games/*.md`, `wiki/entities/*.md`, `wiki/topics/*.md`, `wiki/overview.md`)** — **Tier 1 (Preferred)**:
  - Cross-stream thematic syntheses, `ปู่โบ๊ต`'s recurring opinions, milestones, and linked stream references (`[[stream-<vid>]]`).
- **Master Index (`wiki/index.md`)**:
  - Single-file directory of every game, entity, topic, stream source, and engineering page.
- **Curated Stream Sources (`wiki/sources/stream-*.md`)** — **Tier 2**:
  - One markdown page per canonical stream with YAML metadata (`video_id`, `upload_date`, `tags`), `Linked Categories & Entities`, macro-thematic sections, and `- \`HH:MM:SS\` — ...` timestamp bullets.
- **Raw Stream Snapshots (`raw/streams/stream-*.md`)** — **Tier 3 (Optional Fallback)**:
  - Original snapshots including exhaustive `all_timestamps.txt` blocks when granular sub-minute timestamps were condensed out of `wiki/sources/`. Searched **only** when `--include-raw` is explicitly enabled.

No external network calls or external workspace directories (`timestamp_workspace`) are required.

### Deterministic CLI Tool (`wiki_tool.py search`)

Use the stdlib CLI wrapper inside the plugin directory (works from any working directory by passing its full path, or relative path from plugin root):

```bash
python3 /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py search --json --query-json '<query_json>'
```

Equivalent flag-based forms:

```bash
# Multi-term OR search returning structured JSON (synthesis + stream hits + t=SECs URLs)
python3 anibon_wiki/scripts/wiki_tool.py search \
  --terms "ริคิว" "Sen no Rikyu" "Rikyu" \
  --tags fgo \
  --limit 15 \
  --json

# Simple human-readable search
python3 anibon_wiki/scripts/wiki_tool.py search "Roblox"

# Include raw/streams/ (all_timestamps.txt) as fallback
python3 anibon_wiki/scripts/wiki_tool.py search --terms "Trees Hate You" --include-raw --json
```

#### Query JSON Schema (`--query-json`)

```json
{
  "terms": ["term1", "term2"],
  "tags": ["optional-tag"],
  "category": "optional: game | entity | topic | source | synthesis | stream | engineering | raw",
  "date": {
    "from": "YYYY-MM-DD",
    "to": "YYYY-MM-DD"
  },
  "limit": 20,
  "include_raw": false
}
```

#### JSON Output Highlights

- `coverage`: `{ "total_pages": N, "total_streams": M, "date_range": "YYYY-MM-DD..YYYY-MM-DD" }`
- `results[]`: ranked by tier (`synthesis` > `stream` > `engineering` > `raw`), title/tag match, distinct term matches, and recency (`upload_date`):
  - `tier`, `score`, `slug`, `path` (absolute path for `file:///` links), `rel_path`, `title`, `video_id`, `upload_date`, `youtube_url`
  - `matches[]`: `{ "line", "section", "timestamp", "seconds", "youtube_url", "text" }` — `youtube_url` automatically appends `&t=<seconds>` whenever `HH:MM:SS` appears on that line!

---

## Search Workflow

### Step 1: Index Lookup & Query Formulation

1. For known games, characters, or broad themes (e.g. `"Roblox"`, `"FGO"`, `"เกมจิปาถะ"`, `"อาโอโกะ"`), check `anibon_wiki/wiki/index.md` first or read the matching `wiki/games/<slug>.md`, `wiki/entities/<slug>.md`, or `wiki/topics/<slug>.md` page directly!
2. Expand search queries with multilingual **Thai + English + phonetic/slang/alias variants**:
   - **Titles / Games**: Thai + English + abbreviations (e.g., `["รางดาว", "Honkai", "Star Rail", "HSR"]`).
   - **Entities / Characters**: official spelling + Thai phonetic + `ปู่โบ๊ต`'s nicknames (e.g., `["อาโอโกะ", "อาโกะ", "Aoko", "Aozaki"]`, `["ท่านอิมู", "แมรี่จัวส์", "กฎหมายแมรี่จัวส์"]` for sensitive political/royal metaphors).
   - **Filters**: start broad without strict `--date-from` or `--tags` unless the user explicitly constrains dates/topics.

### Step 2: Execute Deterministic Search

Run `wiki_tool.py search` with `--json` (either `--terms ...` or `--query-json '<json>'`). Inspect:
1. Top `tier == "synthesis"` hits (`wiki/games/`, `wiki/entities/`, `wiki/topics/`) for synthesized takeaways and cross-stream narrative.
2. Top `tier == "stream"` hits (`wiki/sources/stream-*.md`) for exact dated streams, `video_id`, and timestamped YouTube URLs (`&t=SECs`).

### Step 3: Verify Context Around Matches

Before quoting or stating what `ปู่โบ๊ต` said:
- Use `read_file` around the matched `line` in `wiki/sources/stream-<vid>.md` (and/or the synthesized page in `wiki/games/` / `wiki/topics/`) to verify full narrative context, exact time span (`start–end`), and whether a remark was serious critique, sarcasm, or a viewer Q&A.
- If a snippet links a `[[stream-<vid>]]`, read that stream's `wiki/sources/stream-<vid>.md` when exact timestamp precision is needed.

### Step 4: Iterative Refinement (Max 3 Rounds)

If initial search returns zero or thin hits:
- **Round 2**: Broaden `terms` with alternative Thai spellings, phonetic approximations, or wider category terms, and remove `--tags` / `--category`.
- **Round 3**: Re-run with `--include-raw` (`"include_raw": true`) to scan uncurated `all_timestamps.txt` lines inside `anibon_wiki/raw/streams/`.
- If still empty after 3 rounds, clearly report the gap and state `coverage` (`total_pages`, `total_streams`, `date_range`). Never invent timestamps.

### Step 5: Answer Formatting & Citations

Present answers concisely in the user's language (default Thai when asked in Thai):
- **Synthesized Summary First**: Lead with the direct answer across streams (`ปู่โบ๊ต` — never `ปู่บอท`/`ลุงบอท`).
- **Timestamped Clips**: For each cited moment, include:
  - Upload date & Stream title / ID
  - Exact timestamp + clickable YouTube jump link: `https://www.youtube.com/watch?v=<video_id>&t=<secs>`
  - Clickable local wiki citation link: `[stream-<vid>.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/wiki/sources/stream-<vid>.md#L...)` (and relevant `[game/topic page](file:///...)`).
- **Coverage Footer**: Mention verified scope (e.g. number of matched streams/pages across the archive's `total_streams` and `date_range`).

### Step 6: Optional Query Compounding (LLM Wiki Maintenance)

Per `anibon_wiki/CLAUDE.md`, if a non-trivial search synthesizes a recurring game/entity/topic across multiple streams that lacks a dedicated `wiki/` page (e.g. a newly surfacing franchise or recurring theme):
- Create/update the synthesized page in `anibon_wiki/wiki/games/`, `entities/`, or `topics/` (using `stream-cqll7dq35bw` / `roblox.md` conventions).
- Rebuild the index & validate integrity:
  ```bash
  python3 anibon_wiki/scripts/build_index.py
  python3 anibon_wiki/scripts/wiki_tool.py lint
  ```
- Append a brief entry to `anibon_wiki/wiki/log.md`.
- Skip this step for simple one-off timestamp lookups.

---

## Mandatory Safety & Integrity Rules (Iron Rules)

- **R1 — Zero Fabricated Citations**: Never invent or extrapolate timestamps, `t=SECs`, video IDs, or upload dates. Compute `t=SECs` strictly from `HH:MM:SS` observed in `anibon_wiki/` (`HH * 3600 + MM * 60 + SS`) or directly from `wiki_tool.py search --json` output.
- **R2 — Mandatory Royal News Masking (`masking-royal-news`)**: Read and strictly enforce [skills/masking-royal-news/SKILL.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/masking-royal-news/SKILL.md) before quoting or paraphrasing any sensitive historical/royal/legal stream moment. Keep all canonical metaphors (`ท่านอิมู รุ่นที่ 8/9/10`, `สถาบันแห่งแมรี่จัวส์`, `กฎหมายแมรี่จัวส์`, `มังกรฟ้า`). Even though `wiki_search.py` runs `sanitize_wiki_text` on matched lines, inspect `--include-raw` snippets carefully and mask any unmasked phrasing in prose.
- **R3 — Streamer Identity Invariant**: Always write **`ปู่โบ๊ต`** — never `ปู่บอท`, `ลุงบอท`, or `ปู่โบต`.
- **R4 — Deterministic Local Retrieval**: Do not scrape YouTube, run ad-hoc regex scripts, or query deprecated `~/timestamp_workspace` paths. Always use `anibon_wiki/` and `wiki_tool.py search`.
- **R5 — Context Fidelity**: Read surrounding lines in `wiki/sources/` or `wiki/{games,entities,topics}/` before attributing a position or quote to `ปู่โบ๊ต`. If the archive has no coverage after 3 search rounds, state what is missing honestly.
