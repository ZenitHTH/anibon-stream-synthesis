#!/usr/bin/env python3
"""
fetch_pokemon_db.py — Pokémon Relational Database (Official TPC vs EN Community)
=================================================================================
Downloads complete Pokémon species data (Generations 1–9, 1025 species) and builds
a dual-system SQLite database mapping:
  1. Official TPC Thai Name (Japanese-trademark phonetic: เซเกลฟ, บัดเดร็กซ์, เรสพอส)
  2. Community / English-sound Thai Name (แบกซ์แคลิเบอร์, แคลีเรกซ์, สเปกเทรียร์, ม้าดำ)
  3. Official English Name (Baxcalibur, Calyrex, Spectrier)
  4. Official Japanese Name (セグレイブ, バドレックス, レイスポス)

Usage:
    python3 fetch_pokemon_db.py                  # Build DB if missing/outdated
    python3 fetch_pokemon_db.py --force          # Force rebuild
    python3 fetch_pokemon_db.py --check          # Check DB status (exit 0/1)
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

TH_URL = "https://raw.githubusercontent.com/sindresorhus/pokemon/main/data/th.json"
EN_URL = "https://raw.githubusercontent.com/sindresorhus/pokemon/main/data/en.json"
JA_URL = "https://raw.githubusercontent.com/sindresorhus/pokemon/main/data/ja.json"

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent
    / "references" / "Pokemon DATA" / "pokemon.db"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_pokemon_db")

# Hand-crafted Thai English-sound & Community Alias Overrides
COMMUNITY_THAI_MAP = {
    "Charizard": "ชาลิซาร์ด / ลิซาร์ดอน",
    "Corviknight": "คอร์วิไนท์ / นกโควิด",
    "Calyrex": "แคลีเรกซ์ / คาลิเบอร์",
    "Spectrier": "สเปกเทรียร์ / ม้าดำ",
    "Glastrier": "กลาสเทรียร์ / ม้าขาว",
    "Cottonee": "คอตตอนนี / ปุยนุ่น",
    "Zygarde": "ไซการ์ด / จิการ์เด",
    "Lunala": "ลูนาลา",
    "Scizor": "สไซเซอร์ / ฮัซซัม",
    "Cloyster": "คลอยสเตอร์ / หอยน้ำแข็ง",
    "Tyranitar": "ไทรานิทาร์ / บังกิลาส",
    "Urshifu": "อูร์ชิฟู / อาจารย์ชี่ฟู",
    "Bagon": "เบกอน / บากอน",
    "Salamence": "ซาลาเมนซ์ / โบมันเดอร์",
    "Magnezone": "แมกนีโซน / จิบาโคอิล",
    "Starmie": "สตาร์มี",
    "Stunfisk": "สตันฟิสก์ / ปลาแบน",
    "Ogerpon": "โอเกอร์ปอน",
    "Togekiss": "โทเกคิส",
    "Florges": "ฟลอร์เจส",
    "Keldeo": "เคลดีโอ / ม้ามายา",
    "Audino": "ออดิโน",
    "Gogoat": "โกโกต",
    "Luxray": "ลักซ์เรย์",
    "Palossand": "พาลอสแซนด์ / ปราสาททราย",
    "Tapu Koko": "ทาปู โคโค",
    "Silvally": "ซิลแวลลี / เทพเลียนแบบ",
    "Sandaconda": "แซนดาคอนดา",
    "Baxcalibur": "แบกซ์แคลิเบอร์ / มังกรน้ำแข็ง",
    "Groudon": "กรูดอน / กราดอน",
    "Hoopa": "ฮูปา",
    "Farfetch'd": "ฟาร์เฟตช์ / เป็ดต้นหอม",
    "Sirfetch'd": "เซอร์เฟตช์ / ร่างทองเป็ด",
    "Mabosstiff": "มาบอสสติฟฟ์ / หมามาเฟีย",
    "Aegislash": "เอจิสแลช / ดาบผี",
    "Alcremie": "อัลเครมี / น้องครีม",
    "Noivern": "นอยเวิร์น / ค้างคาว",
    "Miraidon": "มิไรดอน",
    "Iron Thorns": "ไอรอน ธอร์นส์",
}


def _get_json(url: str, retries: int = 3, timeout: int = 30) -> list[str]:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pokemon-db-bootstrap/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            log.warning("  Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def build_db(db_path: Path, force: bool = False) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not force and db_path.exists():
        log.info("✓ DB already exists at %s. Use --force to rebuild.", db_path)
        return

    log.info("Fetching Pokemon species names (TH, EN, JA)...")
    th_names = _get_json(TH_URL)
    en_names = _get_json(EN_URL)
    ja_names = _get_json(JA_URL)

    count = min(len(th_names), len(en_names), len(ja_names))
    log.info("Fetched %d species records.", count)

    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")

    con.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO _meta VALUES (?, ?)", [
        ("version", "1025-gen9-dual-th"),
        ("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        ("source", "sindresorhus/pokemon + community aliases"),
        ("pokemon_count", str(count)),
    ])

    con.execute("""
        CREATE TABLE pokemon (
            id                    INTEGER PRIMARY KEY,
            name_en               TEXT NOT NULL,
            name_ja               TEXT NOT NULL,
            name_th_official      TEXT NOT NULL,
            name_th_english_sound TEXT
        )
    """)

    rows = []
    for i in range(count):
        en_name = en_names[i]
        ja_name = ja_names[i]
        th_off  = th_names[i]
        th_en_sound = COMMUNITY_THAI_MAP.get(en_name, None)
        rows.append((i + 1, en_name, ja_name, th_off, th_en_sound))

    con.executemany("INSERT INTO pokemon VALUES (?,?,?,?,?)", rows)

    indexes = [
        ("idx_pokemon_name_en", "pokemon", "name_en"),
        ("idx_pokemon_name_ja", "pokemon", "name_ja"),
        ("idx_pokemon_name_th_off", "pokemon", "name_th_official"),
        ("idx_pokemon_name_th_en_sound", "pokemon", "name_th_english_sound"),
    ]
    for idx, tbl, col in indexes:
        con.execute(f"CREATE INDEX IF NOT EXISTS [{idx}] ON [{tbl}] ([{col}])")

    con.commit()
    con.close()

    size_kb = db_path.stat().st_size / 1024
    log.info("✓ Done! pokemon.db built: %.1f KB (%d species with dual Thai names)", size_kb, count)


def check_db(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        con = sqlite3.connect(db_path)
        count = con.execute("SELECT COUNT(*) FROM pokemon").fetchone()[0]
        con.close()
        return count >= 1000
    except Exception:
        return False


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download Pokémon TH/EN/JA data and build dual-system SQLite DB.")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Output SQLite DB path")
    p.add_argument("--force", action="store_true", help="Re-download even if DB exists")
    p.add_argument("--check", action="store_true", help="Only check DB validity (exit 0/1)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.check:
        sys.exit(0 if check_db(args.db) else 1)
    try:
        build_db(args.db, force=args.force)
    except Exception as exc:
        log.error("Build failed: %s", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
