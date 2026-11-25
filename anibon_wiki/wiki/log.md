# Anibon Stream & Engineering Wiki — Operation Log

## [2026-11-21] init | Wiki created
- Initialized Heavy-Tier LLM Wiki at `anibon_wiki/` with dual-domain architecture (Stream/Lore + Python Script/Pipeline Engineering).
- Created `CLAUDE.md`, `AGENTS.md`, `wiki/index.md`, `wiki/overview.md`, `infranodus/manifest.json`, and `scripts/wiki_tool.py`.

## [2026-11-21] acquire | Acquired initial stream and git code-change sources into `raw/`
- Acquired `~/youtube_cQlL7DQ35bw_workspace` (`anibon_timestamps.md` + `all_timestamps.txt`) → `raw/streams/stream-cqll7dq35bw.md`.
- Acquired git revision range `3a5a039~1..2dce04d` + implementation plan → `raw/code-changes/code-change-prep-first-48k.md`.

## [2026-11-21] ingest | Processed `stream-cqll7dq35bw` and `code-change-prep-first-48k` into 24 wiki pages
- Created source pages: [[stream-cqll7dq35bw]], [[code-change-prep-first-48k]].
- Created game pages (8): [[zenless-zone-zero]], [[fate-grand-order]], [[honkai-star-rail]], [[azur-promilia]], [[limbus-company]], [[chaotic-plartima]], [[gta-6]], [[wuthering-waves]], [[arknights]].
- Created entity pages (6): [[aoko-aozaki]], [[sen-no-rikyu]], [[sunbringer]], [[kafka]], [[robin]], [[jing-yuan]].
- Created topic pages (2): [[gacha-business-and-endgame-philosophy]], [[thai-politics-and-economy]].
- Created engineering pages (8): [[prep-first-full-context-48k]], [[process-chunks-local-py]], [[chunk-enrichment-py]], [[chunk-storyboard-prep-py]], [[dynamic-chunk-py]], [[webcam-storyboard-py]], [[prompts-py]], [[post-mortem-scrutinize-cqll7dq35bw]].
- Appended initial relations to `infranodus/full-wiki-ontology.md` and ran automated lint check.

## [2026-11-21] acquire & batch-ingest | Full 210-Stream ANIBON Archive + Engineering Suite
- Deduplicated 226 workspace artifacts in `$HOME` (`~/timestamp_workspace/by_video_id/`, `~/youtube_*_workspace*`, `~/youtube_workspaces/backed_up/`) -> excluded 2 unrelated GT7 videos (`DiI0GEBVIxQ`, `lUpikjLTmro`) and 14 variant files (`*_unmasked*`, `_clean`, etc.), yielding **210 canonical ANIBON streams**.
- Acquired 209 remaining snapshots into `raw/streams/` via `acquire_streams.py`.
- Ingested all 209 remaining streams into `wiki/sources/stream-*.md` via `ingest_streams_batch.py` (enforcing `masking-royal-news` safe metaphors and preserving `[[stream-cqll7dq35bw]]`).
- Synthesized **28 Game pages** (`wiki/games/`), **25 Entity pages** (`wiki/entities/`), **6 Topic pages** (`wiki/topics/`), and **14 Python Script engineering pages** (`wiki/engineering/scripts/`).
- Rebuilt `wiki/index.md` via `build_index.py`, updated `wiki/overview.md`, appended full ontology relations to `infranodus/full-wiki-ontology.md`, and verified 0 broken wikilinks, 0 orphan pages, and 0 unindexed pages.

## [2026-11-22] query & file | Synthesized `wiki/games/roblox.md` from user query ("ROBLOX ?")
- Searched 210 streams and filed dedicated game page [[roblox]] synthesizing 22 livestream discussions/gameplay sessions (including the 5-hour Roblox RP marathon in [[stream-vwu3sjkfx6g]], Tsuburaya Ultraman licensing [[stream-ymfjdsqwk6i]], TGA/copyright critiques, and safety/politics coverage).
- Added `"roblox"` rule to `stream_taxonomy.py`, rebuilt `wiki/index.md`, and appended relations to `infranodus/full-wiki-ontology.md`.

## [2026-11-22] query & file | Synthesized `wiki/games/variety-and-indie-games.md` ("เกมจิปาถะ ที่เล่น")
- Cataloged all non-mainline variety, indie, Soulslike, survival, card, MOBA, and event-demo games played by `ปู่โบ๊ต` across 2025–2026 (*Burning Sword: Death Sun*, *Trees Hate You*, *Valor Mortis*, *Beast of Reincarnation*, *Echoes of Aincrad*, *Dinoblade*, *Lost Soul Aside Demo*, *Palworld 1.0*, *One in 8 Billion*, *The Lands*, *Heartopia*, *The Sims 1*, *Eternal Return*, *RoV*, *Arena Breakout: Infinite*, *Yu-Gi-Oh! Master Duel*, *CookieRun: OvenSmash*, *AniGuesser/AMQ*, *LEGO Fortnite*, and TGS 2026 Thai indie booths).
- Rebuilt `wiki/index.md` and ran `wiki_tool.py lint`.

## [2026-11-22] feat | Upgraded `wiki_tool.py search` & migrated `/anibon-search` to `anibon_wiki`
- Added `anibon_wiki/scripts/wiki_search.py` supporting multi-term OR search, tier ranking (`synthesis` > `stream` > `engineering` > optional `--include-raw`), tag/category/date filtering, YouTube `&t=SECs` URL extraction, and `sanitize_wiki_text()` safety enforcement.
- Upgraded `anibon_wiki/scripts/wiki_tool.py search` with `--terms`, `--tags`, `--category`, `--date-from`, `--date-to`, `--limit`, `--include-raw`, `--json`, and `--query-json` flags.
- Rewrote `skills/anibon-search/SKILL.md` to retrieve directly from `anibon_wiki/` instead of `~/timestamp_workspace`, added unit tests in `tests/test_anibon_wiki_search.py`, and updated [[anibon-wiki-tools]].

## [2026-11-24] ingest | Acquired & ingested 4 new ANIBON streams (210 -> 214)
- Acquired raw snapshots (`raw/streams/`) and created source pages (`wiki/sources/`) for [[stream-f_p0qclmfzi]] (`2026-11-21`), [[stream-soc6jzfd_j8]] (`2026-11-22`), [[stream-uql-sexvuve]] (`2026-11-22`), and [[stream-7tpofoiphog]] (`2026-11-23`), enforcing `masking-royal-news` on [[stream-7tpofoiphog]].
- Updated 13 category/entity/topic pages: [[arknights]], [[gta-6]], [[variety-and-indie-games]], [[wuthering-waves]], [[roblox]], [[minecraft]], [[blue-archive]], [[reverse-1999]], [[talulah]], [[tokusatsu-watch-party]], [[thai-politics-and-economy]], [[gacha-business-and-endgame-philosophy]], and [[anime-manga-cinema]].
- Updated [[overview]], rebuilt `wiki/index.md` via `build_index.py`, appended relations to `infranodus/full-wiki-ontology.md`, and verified `wiki_tool.py lint` (0 broken links, 0 orphans, 0 unindexed pages).

## [2026-11-25] ingest & improve | Ingested `WZeAJUPt7xw` (Bleach TYBW Ep 47) & enriched `Bleach.md` + timestamps (214 -> 215)
- Improved `~/youtube_WZeAJUPt7xw_workspace/anibon_timestamps.md` (`41` curated stamps) and `all_timestamps.txt` (`85` stamps) after Stage 5 transcript/livechat/wiki cross-check (anchored `00:00:00` pre-roll, `00:04:39` mic entry, `00:37:22` Aizen cliffhanger, `00:54:26` multi-app Ep 47 delay, `01:28:56` OST III release, `02:52:31` Facebook scam story, canonical *Bleach* terminology).
- Updated `skills/anibon-world-identity/references/Bleach.md` with *Shinken Hakkyoken*, *Goryutenmetsu*, *Gremmy*, *Visored* Cero 7 colors, 5 War Potentials, *OST III*, and verified phonetic drifts; fixed 3 poisoned `garbled_replacements.json` entries (*Can't Fear Your Own World*, *Segunda Etapa*, removed *Brachet*).
- Acquired `raw/streams/stream-wzeajupt7xw.md`, created `wiki/sources/stream-wzeajupt7xw.md`, and updated [[anime-manga-cinema]], [[vlogs-hardware-and-personal-life]], [[overview]], `wiki/index.md`, and `infranodus/full-wiki-ontology.md`.

## [2026-11-25] audit & ingest | Synced `dev` working-tree engineering changes vs `origin/main` (`532fdee`)
- Verified `origin/main..dev` has `0` commits; all changes sit in the `dev` working tree (`44` modified tracked files, `17` untracked files), with `215` streams already ingested.
- Snapshotted working-tree engineering diff in `raw/code-changes/code-change-stage5-guards-fgo-np-2026-11-25.md` and [[code-change-stage5-guards-fgo-np-2026-11-25]].
- Added [[domain-db-and-fgo-py]] (`fetch_fgo_db.py --with-np`, `domain_db.py`) and updated [[prompts-py]], [[process-chunks-local-py]], [[audit-gaps-and-check-sections]], [[prep-first-full-context-48k]], and [[overview]] (`16 -> 17` engineering docs).
