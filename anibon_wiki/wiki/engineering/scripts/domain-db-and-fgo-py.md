---
title: "fetch_fgo_db.py & domain_db.py (FGO DB --with-np & JIT Entity Queries)"
category: "engineering-script"
updated: "2026-11-25"
script_path: "skills/anibon-world-identity/scripts/fetch_fgo_db.py"
tags: ["python", "script", "sqlite", "fgo", "world-identity", "domain-db"]
sources: ["[[code-change-stage5-guards-fgo-np-2026-11-25]]"]
status: "active"
---

# `fetch_fgo_db.py` & `domain_db.py`

- **FGO DB Builder**: [skills/anibon-world-identity/scripts/fetch_fgo_db.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-world-identity/scripts/fetch_fgo_db.py)
- **Domain Query Module**: [lib/process/knowledge/domain_db.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/knowledge/domain_db.py)
- **Design Plan**: [2026-11-24-fgo-db-optional-np.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/plans/2026-11-24-fgo-db-optional-np.md)
- **Unit Tests**: [test_fetch_fgo_db.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py), [test_domain_db.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/tests/test_domain_db.py)
- **Pipeline & Consumers**: [[prep-first-full-context-48k]], [[prompts-py]]

## Purpose & Responsibility
Builds the offline `atlas_fgo.db` SQLite cache from Atlas Academy exports (`fetch_fgo_db.py`) and serves JIT FGO servant/entity lookups into Pass 1 prompts (`domain_db.py`). Adds opt-in Noble Phantasm (`servant_np`) indexing via `--with-np` while keeping legacy schemas without `servant_np` backwards-compatible.

## Key Functions & Public Contracts

### `skills/anibon-world-identity/scripts/fetch_fgo_db.py`
- `build_db(db_path: Path, force: bool = False, with_np: bool = False) -> None` ([fetch_fgo_db.py:429](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-world-identity/scripts/fetch_fgo_db.py#L429)): Downloads Atlas Academy endpoints and populates `basic_servant` (including `attribute TEXT DEFAULT ''`), `basic_event` (including `startedAt`/`endedAt`), `COLLATE NOCASE` indexes on `name`, and optional `servant_np(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)` using `INSERT OR REPLACE`.
- `extract_servant_np_rows(servants: list[dict]) -> list[dict]` ([fetch_fgo_db.py:330](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-world-identity/scripts/fetch_fgo_db.py#L330)): Extracts servant ID, NP name, and card type rows for `servant_np`.
- `_has_table(db_path: Path, table: str) -> bool` ([fetch_fgo_db.py:347](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-world-identity/scripts/fetch_fgo_db.py#L347)) & `_is_up_to_date(db_path: Path, with_np: bool, remote_ver: str) -> bool` ([fetch_fgo_db.py:363](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-world-identity/scripts/fetch_fgo_db.py#L363)): Ensures passing `--with-np` rebuilds an older `atlas_fgo.db` that matches `remote_ver` but lacks `servant_np`.

### `lib/process/knowledge/domain_db.py`
- `_has_servant_np(cur: sqlite3.Cursor) -> bool` ([domain_db.py:42](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/knowledge/domain_db.py#L42)): Detects whether `servant_np` exists in `atlas_fgo.db`.
- `_build_fgo_query(num_names: int, with_np: bool) -> str` ([domain_db.py:48](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/knowledge/domain_db.py#L48)): Conditionally emits `LEFT JOIN servant_np` with `COLLATE NOCASE` matching.
- `_format_fgo_row(row: tuple, with_np: bool) -> Dict[str, Any]` ([domain_db.py:64](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/knowledge/domain_db.py#L64)) & `query_fgo_servants(...)` ([domain_db.py:73](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/knowledge/domain_db.py#L73)): Formats matched servant records including `np` details when `servant_np` is populated.
