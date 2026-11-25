# Raw Code Change Snapshot: code-change-stage5-guards-fgo-np-2026-11-25
- Branch Comparison: `origin/main` (`532fdee`) vs `dev` working tree (`0` committed commits ahead; `44` modified tracked files, `17` untracked files)
- Acquired: 2026-11-25

## 1. Optional FGO Noble Phantasm DB (`--with-np`)
- Plan: `docs/superpowers/plans/2026-11-24-fgo-db-optional-np.md`
- `skills/anibon-world-identity/scripts/fetch_fgo_db.py`:
  - Added `attribute TEXT DEFAULT ''` to `basic_servant`, `startedAt`/`endedAt` to `basic_event`, `INTEGER PRIMARY KEY` + `INSERT OR REPLACE`, and `COLLATE NOCASE` indexes on `name`.
  - Added `--with-np` CLI flag and `build_db(db_path, force=False, with_np=False)` building `servant_np(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)` via `extract_servant_np_rows()`, `_has_table()`, and `_is_up_to_date()`.
- `lib/process/knowledge/domain_db.py`:
  - Added `_has_servant_np(cur)`, `_build_fgo_query(num_names, with_np)` (`LEFT JOIN servant_np`, `COLLATE NOCASE`), `_format_fgo_row(row, with_np)`, and `query_fgo_servants()` `np` output.
- Tests: `skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py`, `skills/anibon-timestamper-local/tests/test_domain_db.py`.

## 2. Stage 5 Pipeline Guards & Inference Telemetry
- `lib/common/timestamps.py`:
  - Added `[Intro]` and `[Tierlist]` to `TAGS`; `_ALLOWED_TAGS` includes `Highlight`; added `_REACTION_TAG_HINTS` and extended `TAG_REMAP` (`บ่นยับ`, `สับแหลก`, `สับเละ`, `จวกยับ`, `โวย`, `โวยวาย`, `ตื่นเต้น`, `ตกใจ`, `หัวร้อน`).
  - Added `normalize_tag()` and updated `deduplicate_consecutive_timestamps()` bracket regex to `\[[^\]]+\]`.
- `lib/process/byte_cap.py`, `lib/process/caveman.py`: updated bracket regex from `\[\w+\]` to `\[[^\]]+\]` so non-ASCII/multi-word tags parse cleanly.
- `lib/process/prompts.py`:
  - Added `_extract_donor_mentions(transcript_block)` and `_build_game_switch_hint(signal, current_topic, rolling_summary)` (`conf >= 0.65`, excludes `Knowledge`), injected into `build_recursive_prompt()` `## CONTEXT METRICS`.
  - Updated `GROUNDING:` rule to keep viewer/donor handles (`ขอบคุณ / donate / ซุป ... คุณ <Name>`) separate from game factions/characters.
- `lib/process/runners/recursive.py`:
  - Added `_is_non_thai_bgm_chunk(chunk, enrichment)` (`< 5` Thai chars across transcript + `recovered_items`), `_short_circuit_bgm_chunk(...)` (emits `[Intro]` on `chunk_00` or `CONTINUATION (0 stamps)` later), and `_estimate_prompt_tokens(prompt, keyframes)`.
- `lib/process/summarizer_prompt.py`: `_normalize_summary_connectors()` strips leaked `HH:MM:SS - [Tag]` prefixes from summary lines.
- `lib/common/lm_think_log.py` & `skills/anibon-timestamper-local/scripts/process_chunks_local.py`: `summarize_lm_trace()` now reports `prompt_tokens` and `total_tok_per_sec` (`prompt=... tok, gen=... tok/s, total=... tok/s`).
- `scripts/check_sections.py`: flags leaked `HH:MM:SS` inside `ส่วนที่ N:` headers and non-ASCII/non-whitelisted `[tag]` on timestamp lines.
- Tests: `tests/test_stage5_pipeline_guards.py`.

## 3. World Identity, Skills & Dictionaries
- World Identity references: added `Annihilated.md`, `Loop_Hero.md`; updated `Arknights_Endfield.md`, `Bleach.md`, `Blue_Archive.md`, `Tokusatsu_Project_RED.md`, `INDEX.md`, `thai_phonetic_bridge.json`.
- Dictionaries & Skills: updated `resources/knowledge.json`, `resources/garbled_replacements.json`, `skills/anibon-timestamper-local/{SKILL.md, references/hardware-and-endpoints.md, references/stage5-audit-checklist.md}`, `skills/anibon-search/SKILL.md`.
