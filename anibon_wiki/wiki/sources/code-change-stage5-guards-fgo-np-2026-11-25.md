---
title: "Code Change: Stage 5 Guards, FGO --with-np & Wiki Search (dev vs origin/main 532fdee)"
category: "source"
updated: "2026-11-25"
commits: "dev working tree vs origin/main (532fdee)"
tags: ["engineering", "stage5", "fgo", "sqlite", "guards", "telemetry", "dev-branch"]
sources: []
status: "active"
---

# Code Change: Stage 5 Guards, FGO `--with-np` & `dev` Working Tree (`2026-11-25`)

- **Git Comparison**: `origin/main..dev` has **`0` committed commits**; all changes currently reside in the `dev` working tree (`44` modified tracked files, `17` untracked files vs `origin/main` `532fdee`).
- **FGO DB Spec**: [2026-11-24-fgo-db-optional-np.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/plans/2026-11-24-fgo-db-optional-np.md)
- **Raw Snapshot**: [code-change-stage5-guards-fgo-np-2026-11-25.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/raw/code-changes/code-change-stage5-guards-fgo-np-2026-11-25.md)
- **Architecture & Script Docs**: [[prep-first-full-context-48k]], [[domain-db-and-fgo-py]], [[prompts-py]], [[process-chunks-local-py]], [[audit-gaps-and-check-sections]], [[anibon-wiki-tools]]

## Change Workstreams (`dev` Working Tree vs `origin/main`)

1. **ANIBON Stream Archive (`210 -> 215` Streams)**:
   - Acquired and ingested 5 additional streams (`2026-11-24`..`2026-11-25`), newest ingested in this cycle: [[stream-f_p0qclmfzi]], [[stream-soc6jzfd_j8]], [[stream-uql-sexvuve]], [[stream-7tpofoiphog]], [[stream-wzeajupt7xw]].
2. **Optional FGO Noble Phantasm SQLite Support (`--with-np`)**:
   - Added `--with-np` / `servant_np` schema & lookup across [[domain-db-and-fgo-py]] (`fetch_fgo_db.py`, `domain_db.py`), verified by `test_fetch_fgo_db.py` and `test_domain_db.py`.
3. **Stage 5 Pipeline Guards, BGM Short-Circuit & Trace Telemetry**:
   - Updated [[prompts-py]] (`_extract_donor_mentions`, `_build_game_switch_hint`, donor grounding rule), [[process-chunks-local-py]] (`_is_non_thai_bgm_chunk`, `_short_circuit_bgm_chunk`, `_estimate_prompt_tokens`, `summarize_lm_trace` tok/s telemetry), and [[audit-gaps-and-check-sections]] (`_ALLOWED_TAGS` / `TAG_REMAP`, bracket `[tag]` regex normalization, leaked-timestamp header checks, `_normalize_summary_connectors`), verified by [test_stage5_pipeline_guards.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_stage5_pipeline_guards.py).
4. **World Identity, Skills & Wiki Search Upgrade**:
   - Upgraded `wiki_search.py` & `wiki_tool.py search` ([[anibon-wiki-tools]]) and `skills/anibon-search/SKILL.md`; updated `skills/anibon-timestamper-local/{SKILL.md, references/hardware-and-endpoints.md, references/stage5-audit-checklist.md}` and World Identity references (`Annihilated.md`, `Loop_Hero.md`, `Arknights_Endfield.md`, `Bleach.md`, `Blue_Archive.md`, `Tokusatsu_Project_RED.md`, `INDEX.md`, `thai_phonetic_bridge.json`, `resources/knowledge.json`, `resources/garbled_replacements.json`).
