#!/usr/bin/env python3
"""
fetch_fgo_db.py — Atlas Academy FGO JP Data Bootstrap
======================================================
Downloads lightweight JSON exports from https://api.atlasacademy.io/export/JP/
and builds a lean SQLite database optimised for LLM querying during
anibon-timestamper skill execution.

Usage:
    python fetch_fgo_db.py                  # Download + build DB if missing
    python fetch_fgo_db.py --with-np        # Include lightweight servant_np table (~66 MB extra download)
    python fetch_fgo_db.py --force          # Force re-download even if DB exists
    python fetch_fgo_db.py --check          # Just check if DB is valid, exit 0/1
    python fetch_fgo_db.py --db /path/db    # Custom DB output path

The resulting atlas_fgo.db is ~30–60 MB (vs. the original 293 MB full-dump DB)
because we only ingest the columns needed for timestamp generation:
  - Servant name (JP + EN), collectionNo, class, rarity, attribute
  - Craft Essence name (JP + EN), collectionNo, rarity
  - Item/Material name (JP + EN), id
  - Event name (JP + EN), id
  - Command Code name (JP + EN), collectionNo
  - BGM name, id
  - NPC/War name (JP + EN), id
  - Traits, Enums (full JSON blobs — small files)
  - CV/Illustrator name tables

Exit codes:
    0 — success (or DB already valid when --check)
    1 — DB missing/invalid when --check
    2 — download/build error
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
import concurrent.futures

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.atlasacademy.io/export/JP"
INFO_URL = "https://api.atlasacademy.io/info"

DEFAULT_DB_PATH = Path(__file__).parent.parent / "references" / "FGO and DATA" / "atlas_fgo.db"

# Each entry: (endpoint_suffix, table_name, columns_to_extract)
# columns_to_extract: list of (json_key, sqlite_type)
# Use None to store the entire object as a JSON blob in a 'data' column.
ENDPOINTS: list[tuple[str, str, list[tuple[str, str]] | None]] = [
    # --- Lightweight basic servant index (fast, ~500 KB) ---
    (
        "basic_servant_lang_en.json",
        "basic_servant",
        [
            ("id", "INTEGER"),
            ("collectionNo", "INTEGER"),
            ("name", "TEXT"),           # English name
            ("originalName", "TEXT"),   # JP name
            ("className", "TEXT"),
            ("rarity", "INTEGER"),
            ("type", "TEXT"),
            ("attribute", "TEXT"),
        ],
    ),
    # --- Lightweight basic CE index (~750 KB) ---
    (
        "basic_equip_lang_en.json",
        "basic_equip",
        [
            ("id", "INTEGER"),
            ("collectionNo", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("rarity", "INTEGER"),
            ("type", "TEXT"),
        ],
    ),
    # --- Lightweight basic SVT index (all entity types, ~2.2 MB) ---
    (
        "basic_svt_lang_en.json",
        "basic_svt",
        [
            ("id", "INTEGER"),
            ("collectionNo", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("className", "TEXT"),
            ("rarity", "INTEGER"),
            ("type", "TEXT"),
            ("flag", "TEXT"),
        ],
    ),
    # --- Basic event index (~286 KB) ---
    (
        "basic_event_lang_en.json",
        "basic_event",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("type", "TEXT"),
            ("startedAt", "INTEGER"),
            ("endedAt", "INTEGER"),
        ],
    ),
    # --- Basic war/chapter index (~59 KB) ---
    (
        "basic_war_lang_en.json",
        "basic_war",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("longName", "TEXT"),
        ],
    ),
    # --- Basic Command Code index (~31 KB) ---
    (
        "basic_command_code_lang_en.json",
        "basic_command_code",
        [
            ("id", "INTEGER"),
            ("collectionNo", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("rarity", "INTEGER"),
        ],
    ),
    # --- Basic Mystic Code index (~4.9 KB) ---
    (
        "basic_mystic_code_lang_en.json",
        "basic_mystic_code",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
        ],
    ),
    # --- Items / Materials (~1.2 MB) ---
    (
        "nice_item_lang_en.json",
        "nice_item",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("type", "TEXT"),
            ("background", "TEXT"),
            ("priority", "INTEGER"),
        ],
    ),
    # --- BGM (~930 KB) ---
    (
        "nice_bgm_lang_en.json",
        "nice_bgm",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
            ("fileName", "TEXT"),
        ],
    ),
    # --- CV / Voice actors (~15 KB) ---
    (
        "nice_cv_lang_en.json",
        "nice_cv",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
        ],
    ),
    # --- Illustrators (~28 KB) ---
    (
        "nice_illustrator_lang_en.json",
        "nice_illustrator",
        [
            ("id", "INTEGER"),
            ("name", "TEXT"),
            ("originalName", "TEXT"),
        ],
    ),
    # --- Traits (full blob — tiny, ~9 KB) ---
    (
        "nice_trait.json",
        "nice_trait",
        None,   # stored as single JSON blob in column 'data'
    ),
    # --- Enums (full blob — tiny, ~47 KB) ---
    (
        "nice_enums.json",
        "nice_enums",
        None,   # stored as single JSON blob in column 'data'
    ),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_fgo_db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_json(url: str, retries: int = 3, timeout: int = 60) -> Any:
    """Download JSON from url with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            log.info("  GET %s (attempt %d/%d)", url, attempt, retries)
            req = urllib.request.Request(url, headers={"User-Agent": "fgo-db-bootstrap/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw)
        except Exception as exc:
            log.warning("    ✗ attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to download {url} after {retries} retries")


def _get_remote_version() -> str:
    """Return the current JP game version string from /info."""
    try:
        info = _download_json(INFO_URL, retries=2, timeout=10)
        return info.get("JP", {}).get("hash", "") or info.get("JP", {}).get("gameVersion", "unknown")
    except Exception:
        return "unknown"


def _db_version(db_path: Path) -> str:
    """Return the stored version string from an existing DB, or ''."""
    if not db_path.exists():
        return ""
    try:
        con = sqlite3.connect(db_path)
        row = con.execute("SELECT value FROM _meta WHERE key='version'").fetchone()
        con.close()
        return row[0] if row else ""
    except Exception:
        return ""


def _build_table_from_list(
    con: sqlite3.Connection,
    table: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
) -> None:
    """Create table and INSERT rows, extracting specified columns."""
    col_defs = ", ".join(
        f"[{name}] {dtype} PRIMARY KEY" if (i == 0 and name in ("id", "servant_id") and dtype == "INTEGER") else f"[{name}] {dtype}"
        for i, (name, dtype) in enumerate(columns)
    )
    con.execute(f"DROP TABLE IF EXISTS [{table}]")
    con.execute(f"CREATE TABLE [{table}] ({col_defs})")
    placeholders = ", ".join("?" for _ in columns)
    col_names = [c[0] for c in columns]
    data = [
        tuple(
            json.dumps(row.get(c), ensure_ascii=False) if isinstance(row.get(c), (dict, list)) else row.get(c)
            for c in col_names
        )
        for row in rows
    ]
    con.executemany(f"INSERT OR REPLACE INTO [{table}] VALUES ({placeholders})", data)
    log.info("    ✓ table [%s]: %d rows", table, len(data))


def _build_blob_table(con: sqlite3.Connection, table: str, blob: Any) -> None:
    """Store a JSON blob (dict or list) as a single row for easy retrieval."""
    con.execute(f"DROP TABLE IF EXISTS [{table}]")
    con.execute(f"CREATE TABLE [{table}] ([data] TEXT)")
    con.execute(f"INSERT INTO [{table}] VALUES (?)", (json.dumps(blob, ensure_ascii=False),))
    log.info("    ✓ table [%s]: blob stored", table)


def _create_indexes(con: sqlite3.Connection) -> None:
    """Create B-tree indexes (case-insensitive on name) for fast LLM queries."""
    indexes = [
        ("basic_servant", "name"),
        ("basic_servant", "originalName"),
        ("basic_servant", "collectionNo"),
        ("basic_servant", "className"),
        ("basic_equip", "name"),
        ("basic_equip", "originalName"),
        ("basic_equip", "collectionNo"),
        ("basic_svt", "name"),
        ("basic_svt", "originalName"),
        ("basic_svt", "type"),
        ("basic_event", "name"),
        ("basic_event", "originalName"),
        ("basic_event", "startedAt"),
        ("basic_war", "name"),
        ("basic_war", "originalName"),
        ("nice_item", "name"),
        ("nice_item", "originalName"),
        ("nice_bgm", "name"),
        ("nice_cv", "name"),
        ("nice_illustrator", "name"),
    ]
    for table, col in indexes:
        idx_name = f"idx_{table}_{col}"
        collate = " COLLATE NOCASE" if col == "name" else ""
        con.execute(f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{table}] ([{col}]{collate})")
    log.info("  ✓ indexes created")


SERVANT_NP_ENDPOINT = "nice_servant_lang_en.json"
SERVANT_NP_COLUMNS = [("servant_id", "INTEGER"), ("np_name", "TEXT"), ("np_card", "TEXT")]


def extract_servant_np_rows(servants: list[dict]) -> list[dict]:
    """Project primary Noble Phantasm name and card type for each servant."""
    rows: list[dict] = []
    for servant in servants:
        servant_id = servant.get("id")
        nps = servant.get("noblePhantasms")
        if servant_id is None or not isinstance(nps, list) or not nps:
            continue
        np0 = nps[0] if isinstance(nps[0], dict) else {}
        rows.append({
            "servant_id": servant_id,
            "np_name": str(np0.get("name") or ""),
            "np_card": str(np0.get("card") or ""),
        })
    return rows


def _has_table(db_path: Path, table: str) -> bool:
    """Return True if the SQLite database at db_path contains table."""
    if not db_path.exists():
        return False
    try:
        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        con.close()
        return row is not None
    except Exception:
        return False


def _is_up_to_date(db_path: Path, with_np: bool, remote_ver: str) -> bool:
    """Return True if existing DB matches remote_ver and requested tables."""
    if not db_path.exists():
        return False
    local_ver = _db_version(db_path)
    if not local_ver:
        log.info("→ Existing DB has no version metadata. Rebuilding...")
        return False
    if local_ver != remote_ver:
        log.info("→ Remote version changed (%s → %s). Rebuilding...", local_ver, remote_ver)
        return False
    if with_np and not _has_table(db_path, "servant_np"):
        log.info("→ Existing DB missing [servant_np]. Rebuilding with --with-np...")
        return False
    log.info("✓ DB already up-to-date (version: %s). Use --force to rebuild.", local_ver)
    return True


def _download_endpoints(endpoints: list[str]) -> dict[str, Any]:
    """Download JSON payloads concurrently for the given endpoint suffixes."""
    downloaded: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ep = {executor.submit(_download_json, f"{BASE_URL}/{ep}"): ep for ep in endpoints}
        for future in concurrent.futures.as_completed(future_to_ep):
            downloaded[future_to_ep[future]] = future.result()
    return downloaded


def _init_db(db_path: Path, remote_ver: str) -> sqlite3.Connection:
    """Open a fresh SQLite database with pragmas and _meta rows."""
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA cache_size=-64000")  # 64 MB cache
    con.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO _meta VALUES ('version', ?)", (remote_ver,))
    con.execute("INSERT INTO _meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))
    con.execute("INSERT INTO _meta VALUES ('source', 'https://api.atlasacademy.io/export/JP')")
    return con


def _populate_tables(con: sqlite3.Connection, downloaded: dict[str, Any], with_np: bool) -> None:
    """Populate core Atlas Academy tables and optional servant_np table."""
    for endpoint, table, columns in ENDPOINTS:
        log.info("Processing %s → [%s]", endpoint, table)
        data = downloaded[endpoint]
        if columns is None:
            _build_blob_table(con, table, data)
            continue
        if not isinstance(data, list):
            log.warning("  Unexpected non-list JSON for %s, wrapping in list", endpoint)
            data = [data]
        _build_table_from_list(con, table, columns, data)
    if not with_np:
        return
    raw_servants = downloaded[SERVANT_NP_ENDPOINT]
    servants = raw_servants if isinstance(raw_servants, list) else []
    _build_table_from_list(con, "servant_np", SERVANT_NP_COLUMNS, extract_servant_np_rows(servants))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_db(db_path: Path, force: bool = False, with_np: bool = False) -> None:
    """Download JSON exports and build the SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    remote_ver = _get_remote_version()
    if not force and _is_up_to_date(db_path, with_np, remote_ver):
        return
    log.info("Building DB for JP game version: %s", remote_ver)
    endpoints = [ep for ep, _, _ in ENDPOINTS] + ([SERVANT_NP_ENDPOINT] if with_np else [])
    downloaded = _download_endpoints(endpoints)
    log.info("Writing SQLite DB to: %s", db_path)
    con = _init_db(db_path, remote_ver)
    _populate_tables(con, downloaded, with_np)
    _create_indexes(con)
    con.commit()
    con.close()
    log.info("✓ Done! atlas_fgo.db built: %.1f MB", db_path.stat().st_size / 1024 / 1024)


def check_db(db_path: Path) -> bool:
    """Return True if DB exists and has required tables."""
    if not db_path.exists():
        log.info("✗ DB not found at %s", db_path)
        return False
    try:
        con = sqlite3.connect(db_path)
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        required = {"basic_servant", "nice_item", "_meta"}
        missing = required - tables
        con.close()
        if missing:
            log.info("✗ DB missing tables: %s", missing)
            return False
        ver = _db_version(db_path)
        log.info("✓ DB valid. Version: %s, Tables: %d", ver, len(tables))
        return True
    except Exception as exc:
        log.info("✗ DB check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download FGO JP data from Atlas Academy and build SQLite DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Output SQLite DB path")
    p.add_argument("--force", action="store_true", help="Re-download even if DB exists")
    p.add_argument("--check", action="store_true", help="Only check if DB is valid (exit 0/1)")
    p.add_argument("--with-np", action="store_true", help="Download nice_servant_lang_en.json (~66 MB) to populate servant_np")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    db_path: Path = args.db

    if args.check:
        ok = check_db(db_path)
        sys.exit(0 if ok else 1)

    try:
        build_db(db_path, force=args.force, with_np=args.with_np)
    except Exception as exc:
        log.error("✗ Build failed: %s", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
