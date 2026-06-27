# FGO JP Data — Database Reference Guide

> **Purpose**: This document replaces the old fat markdown reference file.
> All FGO game data is now stored in a lean SQLite database (`atlas_fgo.db`)
> that is downloaded **on-demand** from Atlas Academy API when the skill is invoked.

---

## ⚡ Bootstrap Protocol (CRITICAL — Read First)

**When the `anibon-gaming-stream` or `anibon-event-stream` skill detects FGO content,
you MUST run this check before querying any FGO data:**

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable,
     "scripts/fetch_fgo_db.py",
     "--check",
     "--db", "skills/reference/FGO and DATA/atlas_fgo.db"],
    cwd="<SKILL_ROOT>",   # path to anibon-timestamper/
    capture_output=True
)
if result.returncode != 0:
    subprocess.run(
        [sys.executable,
         "scripts/fetch_fgo_db.py",
         "--db", "skills/reference/FGO and DATA/atlas_fgo.db"],
        cwd="<SKILL_ROOT>"
    )
```

Or from Antigravity's `run_command`:
```
python3 scripts/fetch_fgo_db.py --check --db "skills/reference/FGO and DATA/atlas_fgo.db"
# exit 1? → then run:
python3 scripts/fetch_fgo_db.py --db "skills/reference/FGO and DATA/atlas_fgo.db"
```

**The script is idempotent** — if `atlas_fgo.db` already exists and is fresh, it returns immediately.

---

## 📦 What the Database Contains

| Table | Source URL | Key columns | Approx. size |
|---|---|---|---|
| `basic_servant` | `/export/JP/basic_servant_lang_en.json` | `id`, `collectionNo`, `name` (EN), `originalName` (JP), `className`, `rarity` | ~500 KB |
| `basic_equip` | `/export/JP/basic_equip_lang_en.json` | `id`, `collectionNo`, `name`, `originalName`, `rarity` | ~750 KB |
| `basic_svt` | `/export/JP/basic_svt_lang_en.json` | `id`, `collectionNo`, `name`, `originalName`, `className`, `type` | ~2 MB |
| `basic_event` | `/export/JP/basic_event_lang_en.json` | `id`, `name`, `originalName`, `type` | ~286 KB |
| `basic_war` | `/export/JP/basic_war_lang_en.json` | `id`, `name`, `originalName`, `longName` | ~59 KB |
| `basic_command_code` | `/export/JP/basic_command_code_lang_en.json` | `id`, `collectionNo`, `name`, `originalName`, `rarity` | ~31 KB |
| `basic_mystic_code` | `/export/JP/basic_mystic_code_lang_en.json` | `id`, `name`, `originalName` | ~5 KB |
| `nice_item` | `/export/JP/nice_item_lang_en.json` | `id`, `name`, `originalName`, `type`, `priority` | ~1.2 MB |
| `nice_bgm` | `/export/JP/nice_bgm_lang_en.json` | `id`, `name`, `originalName`, `fileName` | ~930 KB |
| `nice_cv` | `/export/JP/nice_cv_lang_en.json` | `id`, `name`, `originalName` | ~15 KB |
| `nice_illustrator` | `/export/JP/nice_illustrator_lang_en.json` | `id`, `name`, `originalName` | ~28 KB |
| `nice_trait` | `/export/JP/nice_trait.json` | `data` (JSON blob) | ~9 KB |
| `nice_enums` | `/export/JP/nice_enums.json` | `data` (JSON blob) | ~47 KB |
| `_meta` | — | `key`, `value` (version, built_at) | — |

> **Not included**: `nice_servant_lore`, `nice_equip_lore`, `nice_event` (full), `nice_war` (full)
> — these are 20–90 MB each. Query Atlas Academy API directly if you need them.

---

## 🔍 Common Query Patterns

### Find a Servant by JP name (partial match)
```sql
SELECT id, collectionNo, name, originalName, className, rarity
FROM basic_servant
WHERE originalName LIKE '%ウルズ%'
   OR name LIKE '%Urd%';
```

### Find a Servant by class and rarity
```sql
SELECT id, collectionNo, name, originalName
FROM basic_servant
WHERE className = 'archer' AND rarity = 5
ORDER BY collectionNo;
```

### Find all servants that changed their name (svtChange / class designation)
```sql
-- basic_svt has ALL svt types including hidden-name servants
SELECT id, collectionNo, name, originalName, type
FROM basic_svt
WHERE type IN ('normal', 'heroine')
  AND originalName LIKE '%のアーチャー%';
```

### Look up a material/item by JP name
```sql
SELECT id, name, originalName, type
FROM nice_item
WHERE originalName LIKE '%琥珀%'
   OR name LIKE '%Amber%';
```

### Find an event by name
```sql
SELECT id, name, originalName, type
FROM basic_event
WHERE originalName LIKE '%オルレアン%'
   OR name LIKE '%Orleans%'
ORDER BY id DESC;
```

### Get enums (e.g., class names mapping)
```sql
SELECT json_extract(data, '$.SvtClass') FROM nice_enums;
```

### Check DB version
```sql
SELECT value FROM _meta WHERE key = 'version';
SELECT value FROM _meta WHERE key = 'built_at';
```

---

## ⚠️ Critical Rules for FGO Data

1. **True Name vs. Class Designation**: In `basic_svt`, some servants have their
   real name in `originalName` (e.g., `ウルズ`) while the displayed class title
   (e.g., `終末のアーチャー`) is stored only in the full `nice_servant` payload
   under `svtChange[].name`. The basic tables use the **true name**.

2. **`basic_servant` vs `basic_svt`**: `basic_servant` only lists actual playable
   servants. `basic_svt` includes NPC versions, enemies, event bosses, etc.
   Use `basic_svt WHERE type='normal'` to filter to playable ones.

3. **JP vs. NA naming**: `name` = English name, `originalName` = Japanese name.
   Boat plays **JP server**, so he refers to servants by their **Japanese names**.
   Always cross-reference `originalName` first.

4. **collectionNo vs. id**: `collectionNo` is the in-game catalogue number shown
   to players. `id` is the internal database primary key. For most lookups,
   `collectionNo` is what streams will reference.

5. **Card type enums**: In the database: `quick=1`, `arts=3`, `buster=2`.
   The `nice_enums.data` JSON blob contains the full enum mapping.

6. **Rarity**: SSR = 5, SR = 4, R = 3, UC = 2, C = 1.

---

## 🔄 Refreshing the Database

The script compares the local DB version against `/info` endpoint on Atlas Academy.
The DB will **auto-refresh** if the game data version changes. To force a refresh:

```bash
python3 scripts/fetch_fgo_db.py --force --db "skills/reference/FGO and DATA/atlas_fgo.db"
```

Typical download time: **30–120 seconds** depending on connection speed.
Resulting DB size: **~30–60 MB** (vs. 293 MB original).

---

## 📚 Additional Data (API on-demand)

For detailed skill/NP data not in the lightweight DB, query Atlas Academy directly:

| Data needed | API endpoint |
|---|---|
| Full servant data (skills, NP, materials) | `GET /nice/JP/servant/{id}?lang=en` |
| Full CE with lore | `GET /nice/JP/equip/{id}?lang=en&lore=true` |
| Full war/chapter data | `GET /nice/JP/war/{id}?lang=en` |
| Servant search by trait | `GET /nice/JP/servant/search?trait=...&lang=en` |
| NP details | `GET /nice/JP/NP/{np_id}?lang=en` |

Base URL: `https://api.atlasacademy.io`
Docs: `https://api.atlasacademy.io/docs`
