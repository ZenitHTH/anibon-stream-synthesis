#!/usr/bin/env python3
"""
fetch_ygo_db.py — YGOPRODeck Yu-Gi-Oh! Card Database Bootstrap
===============================================================
Downloads the full card catalogue from https://db.ygoprodeck.com/api/v7/
and builds a lean SQLite database optimised for LLM querying during
anibon-timestamper skill execution.

Usage:
    python3 fetch_ygo_db.py                  # Download + build DB if missing or stale
    python3 fetch_ygo_db.py --force          # Force re-download even if DB exists
    python3 fetch_ygo_db.py --check          # Check if DB is valid, exit 0=ok / 1=missing
    python3 fetch_ygo_db.py --db /path/db    # Custom DB output path

What gets stored (Lightweight — text-only, no image URLs or price data):
  - cards        : id, name, type, frameType, desc (effect), race, archetype,
                   atk, def, level, rank, linkval, attribute, scale
  - card_sets    : card_id, set_name, set_code, set_rarity  (for set/booster lookup)
  - archetypes   : id, name  (all known archetypes)
  - card_types   : cached list of distinct type strings
  - _meta        : version, built_at, source

Total DB size: ~10–20 MB (vs. raw JSON ~35–50 MB with images)

Exit codes:
    0 — success / DB already valid
    1 — DB missing or invalid (--check)
    2 — download / build error
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any
import concurrent.futures

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL    = "https://db.ygoprodeck.com/api/v7"
VER_URL     = f"{BASE_URL}/checkDBVer.php"
CARDS_URL   = f"{BASE_URL}/cardinfo.php"
ARCH_URL    = f"{BASE_URL}/archetypes.php"

# How many cards to fetch per paginated request (API max is 4000)
PAGE_SIZE   = 2000

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent
    / "skills" / "reference" / "Yu-Gi-Oh DATA" / "ygo_cards.db"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_ygo_db")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, retries: int = 3, timeout: int = 60) -> Any:
    """Download JSON from url with retry + exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            log.info("  GET %s (attempt %d/%d)", url, attempt, retries)
            req = urllib.request.Request(
                url, headers={"User-Agent": "ygo-db-bootstrap/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            log.warning("    ✗ attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to download {url} after {retries} retries")

# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

def _remote_version() -> str:
    """Return the current database_version string from checkDBVer endpoint."""
    try:
        data = _get(VER_URL, retries=2, timeout=10)
        if isinstance(data, list) and data:
            return str(data[0].get("database_version", "unknown"))
        return "unknown"
    except Exception:
        return "unknown"

def _local_version(db_path: Path) -> str:
    """Return stored version from _meta table, or '' if unavailable."""
    if not db_path.exists():
        return ""
    try:
        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT value FROM _meta WHERE key='version'"
        ).fetchone()
        con.close()
        return row[0] if row else ""
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Data fetch — paginated
# ---------------------------------------------------------------------------

def _fetch_all_cards() -> list[dict]:
    """Fetch the complete card list in paginated batches in parallel."""
    # First get total rows to plan chunks
    url = f"{CARDS_URL}?num=1&offset=0&misc=yes"
    data = _get(url, timeout=30)
    total = int(data.get("meta", {}).get("total_rows", 0))
    if not total:
        return []

    all_cards: list[dict] = []
    offsets = list(range(0, total, PAGE_SIZE))

    def fetch_page(offset):
        params = urllib.parse.urlencode({"num": PAGE_SIZE, "offset": offset, "misc": "yes"})
        res = _get(f"{CARDS_URL}?{params}", timeout=90)
        return res.get("data", [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_offset = {executor.submit(fetch_page, off): off for off in offsets}
        for future in concurrent.futures.as_completed(future_to_offset):
            cards = future.result()
            all_cards.extend(cards)
            log.info("  Fetched %d cards (total so far: %d/%d)", len(cards), len(all_cards), total)

    log.info("→ Total cards fetched: %d", len(all_cards))
    return all_cards

def _fetch_archetypes() -> list[dict]:
    """Fetch the list of all known archetypes."""
    try:
        data = _get(ARCH_URL, timeout=30)
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("Could not fetch archetypes: %s", exc)
        return []

# ---------------------------------------------------------------------------
# DB builder
# ---------------------------------------------------------------------------

def _build(db_path: Path, all_cards: list[dict], archetypes: list[dict], version: str) -> None:
    """Write everything to SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA cache_size=-32000")

    # --- _meta ---
    con.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO _meta VALUES (?, ?)", [
        ("version",  version),
        ("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        ("source",   BASE_URL),
        ("card_count", str(len(all_cards))),
    ])

    # --- cards ---
    con.execute("""
        CREATE TABLE cards (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT,
            frameType   TEXT,
            humanType   TEXT,
            desc        TEXT,
            race        TEXT,
            archetype   TEXT,
            atk         INTEGER,
            def         INTEGER,
            level       INTEGER,
            rank        INTEGER,
            linkval     INTEGER,
            attribute   TEXT,
            scale       INTEGER
        )
    """)
    cards_rows = []
    for c in all_cards:
        cards_rows.append((
            c.get("id"),
            c.get("name"),
            c.get("type"),
            c.get("frameType"),
            c.get("humanReadableCardType"),
            c.get("desc"),
            c.get("race"),
            c.get("archetype"),
            c.get("atk"),
            c.get("def"),
            c.get("level"),
            c.get("rank"),
            c.get("linkval"),
            c.get("attribute"),
            c.get("scale"),
        ))
    con.executemany(
        "INSERT OR IGNORE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        cards_rows,
    )
    log.info("  ✓ table [cards]: %d rows", len(cards_rows))

    # --- card_sets (one row per card×set combination) ---
    con.execute("""
        CREATE TABLE card_sets (
            card_id     INTEGER,
            set_name    TEXT,
            set_code    TEXT,
            set_rarity  TEXT,
            FOREIGN KEY(card_id) REFERENCES cards(id)
        )
    """)
    sets_rows = []
    for c in all_cards:
        cid = c.get("id")
        for s in (c.get("card_sets") or []):
            sets_rows.append((
                cid,
                s.get("set_name"),
                s.get("set_code"),
                s.get("set_rarity"),
            ))
    con.executemany(
        "INSERT INTO card_sets VALUES (?,?,?,?)",
        sets_rows,
    )
    log.info("  ✓ table [card_sets]: %d rows", len(sets_rows))

    # --- archetypes ---
    con.execute("""
        CREATE TABLE archetypes (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE
        )
    """)
    arch_rows = [(a.get("archetype_name"),) for a in archetypes if a.get("archetype_name")]
    con.executemany("INSERT OR IGNORE INTO archetypes (name) VALUES (?)", arch_rows)
    log.info("  ✓ table [archetypes]: %d rows", len(arch_rows))

    # --- indexes ---
    indexes = [
        ("idx_cards_name",      "cards",     "name"),
        ("idx_cards_archetype", "cards",     "archetype"),
        ("idx_cards_type",      "cards",     "type"),
        ("idx_cards_race",      "cards",     "race"),
        ("idx_cards_attribute", "cards",     "attribute"),
        ("idx_sets_setname",    "card_sets", "set_name"),
        ("idx_sets_setcode",    "card_sets", "set_code"),
        ("idx_sets_cardid",     "card_sets", "card_id"),
        ("idx_arch_name",       "archetypes","name"),
    ]
    for idx, tbl, col in indexes:
        con.execute(f"CREATE INDEX IF NOT EXISTS [{idx}] ON [{tbl}] ([{col}])")
    log.info("  ✓ indexes created")

    con.commit()
    con.close()

    size_mb = db_path.stat().st_size / 1024 / 1024
    log.info("✓ Done! ygo_cards.db built: %.1f MB", size_mb)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_db(db_path: Path, force: bool = False) -> None:
    """Download and build (or skip if already fresh)."""
    if not force and db_path.exists():
        local_ver  = _local_version(db_path)
        remote_ver = _remote_version()
        if local_ver and local_ver == remote_ver:
            log.info("✓ DB already up-to-date (version %s). Use --force to rebuild.", local_ver)
            return
        log.info("→ Version changed (%s → %s). Rebuilding...", local_ver, remote_ver)
    else:
        remote_ver = _remote_version()

    log.info("Building YGO DB — database version: %s", remote_ver)
    all_cards  = _fetch_all_cards()
    archetypes = _fetch_archetypes()
    _build(db_path, all_cards, archetypes, remote_ver)


def check_db(db_path: Path) -> bool:
    """Return True if DB exists and has required tables."""
    if not db_path.exists():
        log.info("✗ DB not found at %s", db_path)
        return False
    try:
        con    = sqlite3.connect(db_path)
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        con.close()
        required = {"cards", "card_sets", "_meta"}
        missing  = required - tables
        if missing:
            log.info("✗ DB missing tables: %s", missing)
            return False
        ver   = _local_version(db_path)
        count = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        log.info("✓ DB valid — version: %s, cards: %d", ver, count)
        return True
    except Exception as exc:
        log.info("✗ DB check failed: %s", exc)
        return False


def ensure_db(db_path: Path | None = None) -> Path:
    """Called at skill runtime: build DB if missing/stale."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if not check_db(db_path):
        log.info("→ DB missing or stale. Bootstrapping from YGOPRODeck...")
        build_db(db_path)
    return db_path

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download Yu-Gi-Oh! card data from YGOPRODeck and build SQLite DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--db",    type=Path, default=DEFAULT_DB_PATH, help="Output SQLite DB path")
    p.add_argument("--force", action="store_true", help="Re-download even if DB is fresh")
    p.add_argument("--check", action="store_true", help="Only check DB validity (exit 0/1)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.check:
        sys.exit(0 if check_db(args.db) else 1)
    try:
        build_db(args.db, force=args.force)
    except Exception as exc:
        log.error("✗ Build failed: %s", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
