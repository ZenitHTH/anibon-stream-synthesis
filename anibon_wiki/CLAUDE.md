# Anibon Stream & Engineering LLM Wiki — Schema & Maintainer Guide

## 1. Project Overview
This is a **Heavy-Tier LLM-Maintained Wiki** (`anibon_wiki/`) inside `anibon-stream-synthesis`. It serves two interconnected purposes:
1. **Anibon Stream & Lore Knowledge Base**: A persistent, compounding encyclopedia of every livestream by **`ปู่โบ๊ต`** (Pu Boat / ANIBON), categorized into stream summaries (`wiki/sources/`), game & patch evolutions (`wiki/games/`), characters/studios/people (`wiki/entities/`), and socio-economic/gacha business/philosophical analyses (`wiki/topics/`).
2. **Python Scripts & Pipeline Engineering Ledger**: A structured technical record of how every Python script, CLI tool, VLM pipeline (`anibon-timestamper-local`, `prepare_video.py`, `chunk_enrichment.py`, `process_chunks_local.py`, `webcam_storyboard.py`), and post-mortem fix in `anibon-stream-synthesis` works and evolves over time (`wiki/engineering/`).

The human curates sources and directs work; the LLM owns and maintains all pages in `wiki/`.

---

## 2. Directory Structure

```text
anibon_wiki/
  raw/                          # Immutable source documents (organized by SOURCE TYPE)
    streams/                    # Imported livestream bundles (<video_id>-stream.md: metadata + timestamps + highlights)
    code-changes/               # Git commit diffs, implementation plans, scrutinize reports (<date>-<slug>.md)
    references/                 # Snapshots of game reference docs / glossaries
    notes/                      # User notes, ad-hoc observations
    assets/                     # Storyboard tiles, webcam grid sheets, diagrams
  wiki/                         # LLM-owned interconnected markdown pages
    index.md                    # Master catalog of all pages by category
    overview.md                 # High-level synthesis of both Stream Lore & Engineering Architecture
    log.md                      # Append-only chronological operation log
    sources/                    # One summary page per ingested raw source (stream or engineering change)
    games/                      # Game franchises, version chronologies, gacha banners, Boat's verdict
    entities/                   # Characters, game studios, public figures, hardware/models
    topics/                     # Thematic synthesis (gacha business models, politics, economy, philosophy)
    engineering/
      scripts/                  # Per-script documentation & changelog (purpose, CLI args, functions, fixes)
      pipelines/                # End-to-end architecture pages (Prep-First 48K, Audio/Shazam, Webcam Grid)
      post-mortems/             # Root-cause analyses, bug fixes, scrutinize audits
    _templates/                 # Markdown templates for each page type
  infranodus/                   # Flat knowledge-graph ontologies & manifest.json
    manifest.json               # Scope registry mapping ontology files to saved InfraNodus graphs
    full-wiki-ontology.md       # Append-only curated [[wikilinks]] ontology (wikilinksMode: wikilinksOnly)
  output/                       # Synthesized answers, reports, and graph gap analyses
  todos/                        # Prioritized research & engineering workstreams (- [ ] checkboxes)
  scripts/                      # Helper CLI tools (wiki_tool.py: search, stats, lint, ingest-stream, ingest-git)
  CLAUDE.md                     # Schema & instructions (Claude / Antigravity)
  AGENTS.md                     # Schema & instructions (Codex / Universal Agent)
```

### Knowledge Graphs (`infranodus/`) Policy
- `infranodus/` holds flat ontology files; `infranodus/manifest.json` maps each file to its saved InfraNodus graph (`graphName` + `url`).
- **Curated ontologies (`curated: true`, `wikilinksMode: wikilinksOnly`) are APPEND-ONLY — NEVER regenerate them from scratch.** Read the existing file first, then append only genuinely new `[[Entity A]] [relation] [[Entity B]]` lines at the end.
- Files with `generated: true` frontmatter are machine-generated and must never be hand-edited or appended to.

---

## 3. Page Conventions & Templates

### Naming & Formatting Rules
- **File names**: `kebab-case.md` (e.g., `zenless-zone-zero.md`, `chunk-enrichment-py.md`, `stream-cqll7dq35bw.md`).
- **Streamer Identity Invariant**: Exclusively **`ปู่โบ๊ต`** (never `ปู่บอท`, `ลุงบอท`, or `ปู่โบต`).
- **Dual Citations (Mandatory)**:
  1. Internal Obsidian wikilinks: `[[page-slug]]` or `[[page-slug|Display Name]]`
  2. Clickable file links to ground-truth files: `[label](file:///absolute/path#L10-L20)` plus timestamp `HH:MM:SS` (for streams) or commit hash / line numbers (for Python scripts).
- **YAML Frontmatter (Required on every `wiki/` page)**:
  ```yaml
  ---
  title: "<Clear Title>"
  category: "source | game | entity | topic | engineering-script | engineering-pipeline | post-mortem"
  updated: "YYYY-MM-DD"
  tags: ["tag1", "tag2"]
  sources: ["[[source-slug]]"]
  status: "active"
  ---
  ```

---

## 4. Ingest Workflow (Fully Autonomous Batch Mode)

When new files arrive in `raw/` (or when the user runs an ingest on a stream workspace or git commit range), execute all 8 steps autonomously without pausing for per-entity confirmation:

1. **Read the raw source(s)** in `raw/streams/` or `raw/code-changes/`.
2. **Create/Update the Source Summary Page** in `wiki/sources/<slug>.md` with key takeaways, timeline table, and outbound wikilinks.
3. **Update or Create Category Pages Automatically**:
   - For streams: create/update touched `wiki/games/<game>.md`, `wiki/entities/<entity>.md`, and `wiki/topics/<topic>.md`. Append chronological entries noting what `ปู่โบ๊ต` said, the stream date/ID, and exact `HH:MM:SS` timestamps.
   - For Python script / pipeline changes: create/update `wiki/engineering/scripts/<script-slug>.md`, `wiki/engineering/pipelines/<pipeline-slug>.md`, and `wiki/engineering/post-mortems/<fix-slug>.md` with root cause, code path trace, commit hash, and file/line links.
4. **Update `wiki/index.md`** so every page is cataloged under its category with a 1-line summary.
5. **Update `wiki/overview.md`** if the new source introduces a major architectural shift or new stream milestone.
6. **Append to `wiki/log.md`** in format: `## [YYYY-MM-DD] ingest | <summary of pages created/updated>`.
7. **Append new relations to `infranodus/full-wiki-ontology.md`** (read first, append-only).
8. **Run Automated Lint Pass**: Verify zero broken `[[wikilinks]]`, zero orphan pages, and flag any factual contradictions across streams or script docs.

---

## 5. Query Workflow (Dual Citation + Auto-Filing)

When the user asks a question against the wiki:
1. Read `wiki/index.md` and `wiki/overview.md` (or run `python3 anibon_wiki/scripts/wiki_tool.py search "<query>"`) to locate relevant pages.
2. Read the target pages in `wiki/` and verify details against ground-truth files if needed.
3. Answer concisely with **Dual Citations**:
   - Wiki cross-references (`[[page-slug]]`)
   - Ground-truth clickable file links (`[file.py](file:///path/to/file.py#L10-L20)` or `[anibon_timestamps.md](file:///path#L20)` with `HH:MM:SS`).
4. **Auto-File Valuable Answers**: When a query produces a new cross-stream comparison, deep synthesis, or architectural walkthrough, save it automatically to `output/<date>-<query-slug>.md` (and link it in `wiki/index.md` / `wiki/log.md`).

---

## 6. Lint Workflow (Autonomous Post-Ingest Health Check)

Run `python3 anibon_wiki/scripts/wiki_tool.py lint` automatically after every batch ingest (and whenever requested):
1. **Broken Wikilinks**: Auto-create missing target pages or fix slug typos so every `[[wikilink]]` resolves.
2. **Orphan Pages**: Ensure every page in `wiki/` is linked from `wiki/index.md` and at least one content page.
3. **Index Parity**: Ensure `wiki/index.md` lists 100% of markdown files under `wiki/`.
4. **Contradiction & Staleness Check**: Flag when a newer stream opinion or newer Python script commit supersedes an older claim (mark older claim as `[Superseded by commit/stream X]` with date rather than silently deleting history).
