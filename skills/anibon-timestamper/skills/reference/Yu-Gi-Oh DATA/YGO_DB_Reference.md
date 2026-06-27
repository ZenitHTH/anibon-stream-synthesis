# Yu-Gi-Oh! Card Database — Reference Guide

> **Purpose**: On-demand SQLite database downloaded from YGOPRODeck API.
> Replaces any need to ship fat JSON files. The DB is rebuilt automatically
> the first time this reference is needed, and refreshed whenever
> YGOPRODeck releases a new `database_version`.
>
> **Last checked DB version**: 145.88 (2026-06-23)

---

## ⚡ Bootstrap Protocol (CRITICAL — Read First)

When Yu-Gi-Oh content is detected in a transcript, **run this check before any card lookup**:

```
python3 scripts/fetch_ygo_db.py --check --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
```

If exit code is **1** (missing or stale), build the DB:

```
python3 scripts/fetch_ygo_db.py --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
```

**The script is idempotent** — if `ygo_cards.db` exists and the version matches
`checkDBVer.php`, it returns instantly without downloading anything.

Typical build time: **60–180 seconds** (13,000+ cards in ~7 paginated batches).
Resulting DB size: **~10–20 MB**.

---

## 📦 Database Schema

### Table: `cards`
Core card info — one row per unique card.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Konami card ID (also the passcode) |
| `name` | TEXT | English card name |
| `type` | TEXT | Full type string (e.g., `"Effect Monster"`, `"Quick-Play Spell"`) |
| `frameType` | TEXT | Frame category: `normal`, `effect`, `ritual`, `fusion`, `synchro`, `xyz`, `link`, `spell`, `trap`, `token` |
| `humanType` | TEXT | Human-readable card type (e.g., `"Flip Effect Monster"`) |
| `desc` | TEXT | Card effect / flavour text |
| `race` | TEXT | Monster sub-type (e.g., `Dragon`, `Warrior`) or Spell/Trap sub-type (e.g., `Quick-Play`, `Counter`) |
| `archetype` | TEXT | Primary archetype the card belongs to (e.g., `"Blue-Eyes"`, `"HERO"`) |
| `atk` | INTEGER | ATK value (`NULL` for non-monsters) |
| `def` | INTEGER | DEF value (`NULL` for Link/non-monsters) |
| `level` | INTEGER | Level (for Normal/Effect/Ritual monsters) |
| `rank` | INTEGER | Rank (for Xyz monsters) |
| `linkval` | INTEGER | Link Rating (for Link monsters) |
| `attribute` | TEXT | `DARK`, `LIGHT`, `FIRE`, `WATER`, `EARTH`, `WIND`, `DIVINE` |
| `scale` | INTEGER | Pendulum scale (`NULL` for non-Pendulum) |

### Table: `card_sets`
Card printing history — one row per card × set combination.

| Column | Type | Description |
|---|---|---|
| `card_id` | INTEGER | FK → `cards.id` |
| `set_name` | TEXT | Full set name (e.g., `"Battles of Legend: Glorious Gallery"`) |
| `set_code` | TEXT | Set code (e.g., `"BLGG-EN001"`) |
| `set_rarity` | TEXT | Rarity string (e.g., `"Secret Rare"`, `"Ultra Rare"`) |

### Table: `archetypes`
All known archetypes in the game.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Archetype name (e.g., `"Salamangreat"`, `"Branded"`) |

### Table: `_meta`
Database metadata.

| `key` | `value` example |
|---|---|
| `version` | `145.88` |
| `built_at` | `2026-06-27T13:28:00Z` |
| `source` | `https://db.ygoprodeck.com/api/v7` |
| `card_count` | `13547` |

---

## 🔍 Common Query Patterns

### Find a card by name (exact or partial)
```sql
SELECT id, name, type, race, archetype, atk, def, level, attribute
FROM cards
WHERE name LIKE '%Blue-Eyes%'
ORDER BY name;
```

### Find all cards in an archetype
```sql
SELECT id, name, type, atk, def, level
FROM cards
WHERE archetype = 'Blue-Eyes'
ORDER BY name;
```

### Find all monsters by type/race
```sql
-- All Dragon-type monsters
SELECT id, name, atk, def, level, attribute
FROM cards
WHERE race = 'Dragon' AND frameType NOT IN ('spell','trap')
ORDER BY atk DESC;
```

### Find Spell/Trap cards by sub-type
```sql
-- All Counter Traps
SELECT id, name, desc
FROM cards
WHERE type = 'Counter Trap Card';

-- All Quick-Play Spells
SELECT id, name, desc
FROM cards
WHERE race = 'Quick-Play';
```

### Find a card by set code or set name
```sql
-- Cards in "Battles of Legend: Glorious Gallery" (June 2026)
SELECT c.id, c.name, c.type, cs.set_code, cs.set_rarity
FROM cards c
JOIN card_sets cs ON cs.card_id = c.id
WHERE cs.set_name LIKE '%Glorious Gallery%'
ORDER BY cs.set_code;
```

### Find all prints/rarities of a card
```sql
SELECT cs.set_name, cs.set_code, cs.set_rarity
FROM card_sets cs
JOIN cards c ON c.id = cs.card_id
WHERE c.name = 'Blue-Eyes White Dragon'
ORDER BY cs.set_name;
```

### Find cards by effect keyword
```sql
-- Cards that mention "Quick Effect" in their text
SELECT id, name, type, desc
FROM cards
WHERE desc LIKE '%Quick Effect%';

-- Cards that negate
SELECT id, name, type
FROM cards
WHERE desc LIKE '%negate%' AND frameType IN ('effect','fusion','synchro','xyz','link');
```

### Find all Xyz monsters (by Rank)
```sql
SELECT id, name, race, atk, def, rank, attribute
FROM cards
WHERE rank IS NOT NULL
ORDER BY rank DESC, atk DESC;
```

### Find Link monsters (by Link Rating)
```sql
SELECT id, name, race, atk, linkval, attribute
FROM cards
WHERE linkval IS NOT NULL
ORDER BY linkval DESC;
```

### Check DB version
```sql
SELECT key, value FROM _meta;
```

---

## 📡 Detection Signals for Anibon Timestamper

Load this reference when **any of the following signals** appear in a transcript chunk:

| Signal | Example phrases heard in stream |
|---|---|
| Card game dueling | "ดวล", "ยูกิ", "duel", "สุ่มการ์ด", "โมนสเตอร์", "เวท", "แทรป" |
| Monster/Spell/Trap card types | "Monster", "Spell", "Trap", "ซัมมอน", "Fusion", "Synchro", "Xyz", "Link" |
| Famous card/archetype names | "Blue-Eyes", "Dark Magician", "HERO", "Branded", "Swordsoul", "Spright" |
| Battle Phases | "ยิงตรง", "โจมตี", "destroy", "ส่ง Graveyard", "ใส่ยา", "นำขึ้น" |
| Special mechanics | "Extra Deck", "Graveyard", "GY", "Banish", "เบนิช", "Tribute", "Tribute Summon" |
| OCG/TCG releases | "แพ็ค", "booster", "ชุดใหม่", "Chaos Origins", "World Premiere" |

> [!NOTE]
> Boat plays the **OCG** format (Japanese rules). Cards may have OCG-only names
> or OCG-exclusive prints. Cross-reference `set_code` prefixes:
> - **JP** prefix = OCG Japan exclusive
> - No prefix / EN prefix = TCG or both formats

---

## ⚠️ Critical Rules for YGO Data

1. **Card ID = Passcode**: The `id` field in the database is the same 8-digit
   passcode printed on the bottom-left of every physical card. This is the
   canonical cross-reference key.

2. **frameType vs. type**: `type` is more specific (e.g., `"Flip Effect Monster"`),
   while `frameType` is the visual frame category (`effect`, `spell`, `trap`, etc.).
   Use `frameType` for broad filtering, `type` for precise matching.

3. **`race` field meaning by frameType**:
   - For **monsters**: `race` = monster sub-type (Dragon, Warrior, Machine…)
   - For **spells**: `race` = spell sub-type (Normal, Quick-Play, Field, Equip, Ritual, Continuous)
   - For **traps**: `race` = trap sub-type (Normal, Continuous, Counter)

4. **Multiple archetypes**: A card can only have **one** `archetype` value in this
   database (the primary one). Cards that support multiple archetypes will not have
   all of them in this field — use `desc LIKE '%archetype_name%'` to find support cards.

5. **Pendulum monsters appear twice in card_sets**: They have both Monster and Spell
   frame types in their effect text — but in the DB they appear once with
   `frameType='pendulum_effect'` or `'pendulum_normal'`.

6. **OCG-only cards**: Some cards exist in the database but have never been
   printed in the TCG. Their `set_code` entries will only have Japanese set codes
   (e.g., `ST24-JP001`). These are the cards Boat is most likely playing in JP-format streams.

---

## 🔄 Refreshing the Database

The script compares local `version` in `_meta` against the live `checkDBVer.php`
endpoint. If versions differ, it will re-download automatically.

To force a full refresh:

```bash
python3 scripts/fetch_ygo_db.py --force --db "skills/reference/Yu-Gi-Oh DATA/ygo_cards.db"
```

Typical re-build time: **60–180 seconds**.
YGOPRODeck updates their DB almost daily (especially around new set releases).

---

## 📚 Additional Resources (Live API Queries)

For data not in the local DB, query YGOPRODeck directly:

| Data needed | API endpoint |
|---|---|
| Card detail by name | `GET /api/v7/cardinfo.php?name=<name>` |
| All cards in a set | `GET /api/v7/cardinfo.php?cardset=<set_name>` |
| Search by archetype | `GET /api/v7/cardinfo.php?archetype=<archetype>` |
| Search by type/attribute | `GET /api/v7/cardinfo.php?type=<type>&attribute=<attr>` |
| All archetypes list | `GET /api/v7/archetypes.php` |
| All card sets list | `GET /api/v7/cardsets.php` |
| DB version check | `GET /api/v7/checkDBVer.php` |

Base URL: `https://db.ygoprodeck.com`
API Guide: `https://db.ygoprodeck.com/api-guide/`
Rate limit: **20 requests/second per IP**
