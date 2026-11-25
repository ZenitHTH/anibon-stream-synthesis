# FGO DB Optional Noble Phantasm (`--with-np`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--with-np` flag to `fetch_fgo_db.py` that extracts only `np_name` and `np_card` from `nice_servant_lang_en.json` into a lightweight `servant_np` table, and surface those fields in `query_fgo_servants` when present.

**Architecture:** Default `fetch_fgo_db.py` stays fast and ~2.2 MB by skipping the 66.6 MB `nice_servant_lang_en.json` export. When `--with-np` is passed, `fetch_fgo_db.py` downloads `nice_servant_lang_en.json`, projects each servant's primary Noble Phantasm (`noblePhantasms[0]`) into `servant_np(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)`, and discards the raw JSON. `domain_db.query_fgo_servants()` checks whether `servant_np` exists and `LEFT JOIN`s it when available, keeping full backward compatibility with DBs built without `--with-np`.

**Tech Stack:** Python 3, `sqlite3`, `argparse`, `unittest`

**Spec:** Conversation recommendation (2026-11-24) — opt-in `--with-np` extraction without storing full `nice_servant` schema.

## Global Constraints

- Default `fetch_fgo_db.py` (without `--with-np`) must NOT download `nice_servant_lang_en.json`.
- `servant_np` stores only `(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)` — no raw JSON blobs or full skill arrays.
- Existing callers of `query_fgo_servants(names)` must continue to work identically on DBs without `servant_np`.
- Clean Code rule: functions <= 20 lines, guard clauses first, no dead code.
- Commit to `dev` branch only; never push to `main`.

## Review Focus

- Servant in `nice_servant_lang_en.json` with empty `noblePhantasms: []` or missing key → must be skipped cleanly without raising `IndexError`/`KeyError`.
- `query_fgo_servants()` called against an older `atlas_fgo.db` that has no `servant_np` table → must still return `[{"name", "className", "rarity"}]` without error.
- `fetch_fgo_db.py --with-np` on an up-to-date DB built *without* `--with-np` → must rebuild (or detect missing `servant_np`) instead of returning early as "already up-to-date".
- Case-insensitive lookup (`query_fgo_servants(["oberon"])`) with `servant_np` present → must still match via `COLLATE NOCASE` and include `np_name`, `np_card`.
- `nice_servant` entry where `noblePhantasms[0]` has `name` or `card` missing/`None` → store `""` rather than failing or inserting malformed types.

---

### Task 1: Add `--with-np` extraction and `servant_np` table to `fetch_fgo_db.py`

**Files:**
- Modify: `skills/anibon-world-identity/scripts/fetch_fgo_db.py`
- Create: `skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py`

**Interfaces:**
- Consumes: `_download_json(url: str)`, `_build_table_from_list(con, table, columns, rows)` in `fetch_fgo_db.py`
- Produces:
  - `extract_servant_np_rows(servants: list[dict]) -> list[dict]` returning `[{"servant_id": int, "np_name": str, "np_card": str}, ...]`
  - `build_db(db_path: Path, force: bool = False, with_np: bool = False) -> None`
  - CLI flag `--with-np` on `fetch_fgo_db.py`
  - SQLite table `servant_np (servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)`

- [ ] **Step 1: Write failing unit tests in `skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py`**

```python
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "anibon-world-identity" / "scripts" / "fetch_fgo_db.py"
spec = importlib.util.spec_from_file_location("fetch_fgo_db", SCRIPT_PATH)
fetch_fgo_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_fgo_db)


class TestFetchFgoDbNp(unittest.TestCase):
    def test_extract_servant_np_rows_valid_and_edge_cases(self):
        sample = [
            {"id": 100100, "noblePhantasms": [{"name": "Excalibur", "card": "buster"}]},
            {"id": 100200, "noblePhantasms": []},
            {"id": 100300},
            {"id": 100400, "noblePhantasms": [{"name": None, "card": "arts"}]},
        ]
        rows = fetch_fgo_db.extract_servant_np_rows(sample)
        self.assertEqual(
            rows,
            [
                {"servant_id": 100100, "np_name": "Excalibur", "np_card": "buster"},
                {"servant_id": 100400, "np_name": "", "np_card": "arts"},
            ],
        )

    def test_parse_args_with_np_flag(self):
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["fetch_fgo_db.py", "--with-np"]
            args = fetch_fgo_db._parse_args()
            self.assertTrue(args.with_np)
        finally:
            sys.argv = old_argv

    def test_has_table_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE basic_servant (id INTEGER PRIMARY KEY)")
            con.close()
            self.assertTrue(fetch_fgo_db._has_table(db, "basic_servant"))
            self.assertFalse(fetch_fgo_db._has_table(db, "servant_np"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py -v`
Expected: FAIL (`AttributeError: module 'fetch_fgo_db' has no attribute 'extract_servant_np_rows'`).

- [ ] **Step 3: Implement `extract_servant_np_rows`, `_has_table`, and `--with-np` in `skills/anibon-world-identity/scripts/fetch_fgo_db.py`**

1. Add `extract_servant_np_rows(servants: list[dict]) -> list[dict]`: iterate `servants`, skip entries without a non-empty `noblePhantasms` list or missing `id`, and emit `{"servant_id": s["id"], "np_name": str(np0.get("name") or ""), "np_card": str(np0.get("card") or "")}`.
2. Add `_has_table(db_path: Path, table: str) -> bool`: check `sqlite_master` for `table`.
3. Update `build_db(db_path: Path, force: bool = False, with_np: bool = False) -> None`:
   - In the up-to-date check, only skip rebuild if `not with_np or _has_table(db_path, "servant_np")`.
   - When `with_np` is `True`, download `nice_servant_lang_en.json` and build `servant_np` with columns `[("servant_id", "INTEGER"), ("np_name", "TEXT"), ("np_card", "TEXT")]` (making `servant_id` `INTEGER PRIMARY KEY` in `_build_table_from_list` when `i == 0 and name in ("id", "servant_id")`).
4. Add `--with-np` (`action="store_true"`) to `_parse_args()` and pass `with_np=args.with_np` in `main()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py -v`
Expected: PASS (3 tests OK).

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-world-identity/scripts/fetch_fgo_db.py skills/anibon-timestamper-local/tests/test_fetch_fgo_db.py
git commit -m "feat(fgo-db): add opt-in --with-np flag for lightweight servant_np table"
```

---

### Task 2: Surface `np_name` and `np_card` in `domain_db.query_fgo_servants`

**Files:**
- Modify: `lib/process/knowledge/domain_db.py:42-62`
- Modify: `skills/anibon-timestamper-local/tests/test_domain_db.py`

**Interfaces:**
- Consumes: `servant_np(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)` from Task 1 (optional table)
- Produces: `query_fgo_servants(names: List[str], db_path: Optional[Path] = None) -> List[Dict[str, Any]]` returning `{"name", "className", "rarity"}` plus `"np_name"` and `"np_card"` when `servant_np` exists in the DB.

- [ ] **Step 1: Write failing tests in `skills/anibon-timestamper-local/tests/test_domain_db.py`**

Add two temp-DB unit tests to `TestDomainDB`:
- `test_query_fgo_servants_with_np_table`: creates temp SQLite DB with `basic_servant` (`id=1, name='Oberon', className='pretender', rarity=5`) and `servant_np` (`servant_id=1, np_name='Lie Like Vortigern', np_card='buster'`), calls `query_fgo_servants(["oberon"], db_path=db)`, asserts `result == [{"name": "Oberon", "className": "pretender", "rarity": 5, "np_name": "Lie Like Vortigern", "np_card": "buster"}]`.
- `test_query_fgo_servants_without_np_table`: creates temp SQLite DB with only `basic_servant`, calls `query_fgo_servants(["oberon"], db_path=db)`, asserts `result == [{"name": "Oberon", "className": "pretender", "rarity": 5}]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_domain_db.py -v`
Expected: FAIL on `test_query_fgo_servants_with_np_table` (`np_name` / `np_card` missing).

- [ ] **Step 3: Update `query_fgo_servants` in `lib/process/knowledge/domain_db.py`**

Check `SELECT 1 FROM sqlite_master WHERE type='table' AND name='servant_np'`.
- If present: `SELECT s.name, s.className, s.rarity, COALESCE(n.np_name, ''), COALESCE(n.np_card, '') FROM basic_servant s LEFT JOIN servant_np n ON s.id = n.servant_id WHERE s.name COLLATE NOCASE IN (...)` and include `"np_name"`, `"np_card"` in each returned dict.
- If absent: run the existing `basic_servant` query unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="lib" python3 -m unittest skills/anibon-timestamper-local/tests/test_domain_db.py -v`
Expected: PASS (all tests OK).

- [ ] **Step 5: Commit**

```bash
git add lib/process/knowledge/domain_db.py skills/anibon-timestamper-local/tests/test_domain_db.py
git commit -m "feat(domain-db): join optional servant_np in query_fgo_servants"
```
