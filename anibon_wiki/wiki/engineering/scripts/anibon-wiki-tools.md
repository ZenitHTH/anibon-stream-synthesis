---
title: "Anibon Wiki CLI & Batch Ingestion Tools (anibon_wiki/scripts/)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "anibon_wiki/scripts/wiki_tool.py"
tags: ["python", "script", "wiki", "cli", "ingestion", "lint", "taxonomy"]
sources: []
status: "active"
---

# Anibon Wiki CLI & Batch Ingestion Tools

- **Core Wiki CLI**: [anibon_wiki/scripts/wiki_tool.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py)
- **Bulk Stream Acquirer**: [anibon_wiki/scripts/acquire_streams.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py)
- **Batch Stream Ingestor**: [anibon_wiki/scripts/ingest_streams_batch.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py)
- **Taxonomy & Safety Sanitizer**: [anibon_wiki/scripts/stream_taxonomy.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py)
- **Schema Guide**: [anibon_wiki/CLAUDE.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/CLAUDE.md)
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Pages**: [[index]], [[overview]], [[log]]

## Purpose & Responsibility
Provides the maintenance, search, linting, raw snapshot acquisition, taxonomy classification, and batch ingestion toolchain for `anibon_wiki/` (`raw/` → `wiki/`). Together, these four scripts manage single-stream/git snapshots (`wiki_tool.py`), multi-directory bulk stream collection (`acquire_streams.py`), automatic `wiki/sources/` page generation (`ingest_streams_batch.py`), and canonical game/entity/topic slugging plus safety sanitization (`stream_taxonomy.py`).

## Key Functions & CLI Contracts

### `anibon_wiki/scripts/wiki_tool.py`
- **Subcommands** ([wiki_tool.py:137-159](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L137-L159)):
  - `stats` (`cmd_stats`, [L29-L42](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L29-L42)): Counts `raw/` files, `wiki/` pages (excluding `_templates/` via `_all_wiki_pages()`, [L20-L26](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L20-L26)), total words, and per-subfolder counts.
  - `search QUERY` (`cmd_search`, [L45-L55](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L45-L55)): Case-insensitive line search across all `wiki/` markdown pages.
  - `lint` (`cmd_lint`, [L58-L82](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L58-L82)): Parses Obsidian wikilinks via `_WIKILINK_RE` ([L17](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L17)) and reports: (1) broken wikilinks, (2) orphan pages with 0 inbound links (excluding `{"index", "overview", "log"}`), and (3) unindexed pages absent from `wiki/index.md`. Returns exit code `1` if any issue is found.
  - `acquire-stream WORKSPACE [--video-id VID]` (`cmd_acquire_stream`, [L85-L112](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L85-L112)): Snapshots `anibon_timestamps.md` (and `all_timestamps.txt` if present) into `raw/streams/stream-<vid>.md`.
  - `acquire-git REV_RANGE SLUG [--plan PATH]` (`cmd_acquire_git`, [L115-L134](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/wiki_tool.py#L115-L134)): Runs `git log --stat -p` (diff capped at `60000` chars) and writes `raw/code-changes/<slug>.md` with an optional implementation plan.

### `anibon_wiki/scripts/acquire_streams.py`
- **CLI Arguments** ([acquire_streams.py:159-170](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L159-L170)): `--home` (default `$HOME`) and `--force` (overwrite existing snapshots).
- `_pick_best_source(home)` ([acquire_streams.py:68-127](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L68-L127)): Scans three locations in descending source priority (lower `prio` wins):
  1. `~/youtube_*_workspace*/{anibon_timestamps.md, output.md}` (prio `1..2`)
  2. `~/timestamp_workspace/by_video_id/timestamp_*.md` (prio `3` exact 11-char ID, `4` suffixed)
  3. `~/youtube_workspaces/backed_up/youtube_*_workspace*/{anibon_timestamps_essential.md, anibon_timestamps.md, output.md}` (prio `5..7`)
- **Metadata & Filtering**: `_load_readme_meta()` ([L31-L44](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L31-L44)) and `_read_info_meta()` ([L47-L57](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L47-L57)) normalize upload dates (`YYYY-MM-DD`) and titles; `_canonical_vid()` ([L60-L65](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L60-L65)) skips `_unmasked` variants; `EXCLUDED_IDS = {"DiI0GEBVIxQ", "lUpikjLTmro"}` ([L14](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L14)).
- `write_raw_snapshot(entry, force=False)` ([acquire_streams.py:130-156](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L130-L156)): Writes `raw/streams/stream-<vid>.md`, skipping existing files unless `--force` is passed.

### `anibon_wiki/scripts/ingest_streams_batch.py`
- **CLI Arguments** ([ingest_streams_batch.py:92-96](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py#L92-L96)): `--overwrite` and `--packs-dir` (default `/tmp/anibon_category_packs`).
- **Batch Processing** ([ingest_streams_batch.py:105-143](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py#L105-L143)): Iterates over `raw/streams/stream-*.md`, extracts curated sections before `## Exhaustive Chronological Timestamps`, runs `sanitize_wiki_text()` and `classify_stream()`, parses `ส่วนที่` headers and `HH:MM:SS` bullets (`_parse_sections_and_stamps`, [L34-L51](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py#L34-L51)), renders `wiki/sources/<slug>.md` (`_render_source_page`, [L54-L89](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py#L54-L89)), and exports date-sorted per-category JSON packs plus `_all_streams.json` into `--packs-dir`.

### `anibon_wiki/scripts/stream_taxonomy.py`
- **Rule Tables**: `GAME_RULES` ([L7-L36](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L7-L36)), `ENTITY_RULES` ([L38-L64](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L38-L64)), and `TOPIC_RULES` ([L66-L73](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L66-L73)).
- `sanitize_wiki_text(text)` ([stream_taxonomy.py:93-98](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L93-L98)): Applies `_SAFE_REPLACEMENTS` ([L75-L90](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L75-L90)) to enforce the **`ปู่โบ๊ต`** streamer identity invariant and `masking-royal-news` safe metaphors (e.g., `ท่านอิมู รุ่นที่ 8/9/10`, `กฎหมายแมรี่จัวส์`).
- `classify_stream(low_text)` ([stream_taxonomy.py:101-106](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/stream_taxonomy.py#L101-L106)): Returns `{"games": [...], "entities": [...], "topics": [...]}` of matching canonical slugs.

## Error Handling & Invariants
- **Hand-Curated Source Protection**: `ingest_streams_batch.py` explicitly excludes `stream-cqll7dq35bw` from overwrites even when `--overwrite` is supplied ([ingest_streams_batch.py:114](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/ingest_streams_batch.py#L114)), preserving its deep manual synthesis.
- **Unmasked Source Exclusion**: `acquire_streams.py` filters out `_unmasked` video IDs in `_canonical_vid()` ([L62-L63](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/scripts/acquire_streams.py#L62-L63)) and `stream_taxonomy.py` sanitizes both titles and timestamp text before writing `wiki/sources/`.
- **Wiki Health Gate**: `wiki_tool.py lint` guarantees zero broken wikilinks, zero orphan pages, and 100% `wiki/index.md` parity.
