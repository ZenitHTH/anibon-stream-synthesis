# Priority 1: Keep `anibon_wiki` Synced with New Livestreams & Refresh Live InfraNodus Graphs

## Completed Milestones (`2026-11-21`)
- [x] Acquired all **210 canonical ANIBON streams** from `$HOME` (`~/timestamp_workspace/by_video_id/`, `~/youtube_*_workspace*`, `~/youtube_workspaces/backed_up/`) into `raw/streams/` (excluding 2 unrelated GT7 videos and variant duplicates) via `acquire_streams.py`
- [x] Ingested all 210 streams into `wiki/sources/stream-*.md` via `ingest_streams_batch.py` with `masking-royal-news` compliance
- [x] Synthesized **28 Game pages** (`wiki/games/`), **25 Entity pages** (`wiki/entities/`), and **6 Topic pages** (`wiki/topics/`) chronologically (`2025-01` to `2026-11-21`)
- [x] Appended ontology relations into `infranodus/full-wiki-ontology.md` and verified `0 broken wikilinks / 0 orphans / 0 unindexed` via `wiki_tool.py lint`

## Ongoing Tasks
- [ ] Run `python3.14 anibon_wiki/scripts/acquire_streams.py` + `ingest_streams_batch.py` whenever new `~/youtube_*_workspace` streams complete
- [ ] Upload `infranodus/full-wiki-ontology.md` via InfraNodus (`upload_wiki_ontology.py`) once `INFRANODUS_API_KEY` is configured and save gap analysis to `output/`
- [ ] Expand entity pages for newly recurring secondary topics/figures (e.g., `tokusatsu` Ultraman/Super Sentai entries or political figures in `thai-politics-and-economy`)
