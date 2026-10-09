# World Identity Modular Library Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `anibon-world-identity` into `anibon-timestamper-local` by building a clean, modular library (`anibon.*`) where each file has a single responsibility and stays under ~150 lines (zero monolithic files).

**Architecture:** 
1. `anibon.phonetic_bridge`: Maps Whisper Thai phonetic tokens to canonical entity keys via `thai_phonetic_bridge.json`.
2. `anibon.domain_db`: Connects to SQLite (`atlas_fgo.db`, `ygo_cards.db`, `pokemon.db`) with 2-tier archetype filtering to strictly bound prompt tokens.
3. `anibon.topic_scanner`: Multi-resolution topic detection (Global Macro Anchor from `info.json` + rolling chunk pivot detection for variety streams).
4. `anibon.world_sanitizer`: Deterministic Stage 5 post-pass audit (enforcing Pokémon Thai naming, fixing stutter, injecting outro stamp).
5. Orchestration: `process_chunks_local.py` acts purely as a lean CLI workflow coordinator importing from `anibon.*`.

**Tech Stack:** Python 3.14 (stdlib: `sqlite3`, `re`, `json`, `pathlib`), pytest.

**Spec:** Modular library requirement — no monolithic files, clear separation of concerns, high test coverage.

## Global Constraints
- Maximum file size target: $\le 150-200$ lines per module.
- Standard library only: no heavy external dependencies.
- Windows UTF-8 safe (`-X utf8`).
- Strict prompt budget: entity prompt injection per chunk MUST NOT exceed 300 tokens (average ~35 tokens).
- Strict output ceiling: YouTube comment parts in `anibon_timestamps.md` must stay under 3,500 bytes.
- All test suites must pass via `python -m pytest tests/ -v`.

## Modular File Structure
```
skills/anibon-timestamper-local/scripts/anibon/
├── phonetic_bridge.py   # [NEW] Thai phonetic mapping & Whisper matching (~80-120 lines)
├── domain_db.py         # [NEW] SQLite connectors (FGO, YGO, Pokemon) with JIT limiting (~100-150 lines)
├── topic_scanner.py     # [NEW] Macro title anchor & mid-stream pivot detector (~80-120 lines)
├── world_sanitizer.py   # [NEW] Stage 5 deterministic output audit & outro injector (~100-130 lines)
├── knowledge_reader.py  # Markdown parsing & entity glossary discovery
├── cleaner.py           # ASR cleaner (YouTube Auto-Transcript garbled replacements)
├── prompts.py           # LLM prompt construction (compact entity injection)
└── summarizer.py        # Part assembly & character/byte budget
```

---

### Task 1: Module `anibon.phonetic_bridge` & `thai_phonetic_bridge.json`

**Files:**
- Create: `skills/anibon-world-identity/references/thai_phonetic_bridge.json`
- Create: `skills/anibon-timestamper-local/scripts/anibon/phonetic_bridge.py`
- Test: `skills/anibon-timestamper-local/tests/test_phonetic_bridge.py`

**Interfaces:**
- `load_phonetic_bridge(search_dirs: Optional[List[Path]]) -> Dict[str, dict]`
- `match_phonemes(text: str, bridge: dict) -> List[dict]`

- [ ] **Step 1: Create `thai_phonetic_bridge.json` in `anibon-world-identity/references/`**
Populate prominent Thai phonemes for FGO, YGO, Pokémon, Limbus, Type-Moon, and Anime.

- [ ] **Step 2: Write failing test in `tests/test_phonetic_bridge.py`**
```python
def test_match_phonemes():
    from anibon.phonetic_bridge import load_phonetic_bridge, match_phonemes
    bridge = load_phonetic_bridge()
    text = "ปู่โบ๊ตวิเคราะห์เด็ค เรดแรปเตอร์ เจอขัดด้วย แม็กซ์ ซี"
    hits = match_phonemes(text, bridge)
    assert any(h["en"] == "Raidraptor" for h in hits)
    assert any(h["en"] == "Maxx \"C\"" for h in hits)
```

- [ ] **Step 3: Run test to verify it fails**
Run: `python -m pytest tests/test_phonetic_bridge.py -v`
Expected: FAIL

- [ ] **Step 4: Implement `anibon/phonetic_bridge.py` (~90 lines)**
Clean, focused module handling dictionary loading and case-insensitive Thai/English phoneme scanning.

- [ ] **Step 5: Run test to verify it passes**
Run: `python -m pytest tests/test_phonetic_bridge.py -v`
Expected: PASS

---

### Task 2: Module `anibon.domain_db` (JIT SQLite Router for FGO, YGO, Pokémon)

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/domain_db.py`
- Test: `skills/anibon-timestamper-local/tests/test_domain_db.py`

**Interfaces:**
- `query_ygo_by_archetype(archetype: str, limit: int = 5) -> List[str]`
- `query_fgo_servants(names: List[str]) -> List[dict]`
- `query_pokemon(name: str) -> Optional[dict]`
- `resolve_entities_for_chunk(chunk_text: str, bridge: dict, max_entities: int = 12) -> List[str]`

- [ ] **Step 1: Write failing test in `tests/test_domain_db.py`**
```python
def test_query_ygo_by_archetype():
    from anibon.domain_db import query_ygo_by_archetype
    cards = query_ygo_by_archetype("Raidraptor", limit=5)
    assert len(cards) > 0
    assert all("Raidraptor" in c for c in cards)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_domain_db.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `anibon/domain_db.py` (~120 lines)**
Encapsulated SQLite queries with safe connection management and strict limit caps ($\le 5-10$ items).

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_domain_db.py -v`
Expected: PASS

---

### Task 3: Module `anibon.topic_scanner` (Macro Anchor & Mid-Stream Pivot Scanner)

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/topic_scanner.py`
- Test: `skills/anibon-timestamper-local/tests/test_topic_scanner.py`

**Interfaces:**
- `extract_macro_anchor(info_data: dict) -> Optional[str]`
- `scan_chunk_topic_pivot(chunk_text: str, current_anchor: str) -> Optional[str]`
- `build_stream_topic_profile(workspace: Path, signals: dict) -> dict`

- [ ] **Step 1: Write failing test in `tests/test_topic_scanner.py`**
```python
def test_scan_chunk_topic_pivot():
    from anibon.topic_scanner import scan_chunk_topic_pivot
    current = "Zelda: Breath of the Wild"
    chunk_text = "เนี่ยนะก็เลย Limbus Company เว้ยโห อัตราการเคลียร์บอส"
    pivot = scan_chunk_topic_pivot(chunk_text, current)
    assert pivot == "Limbus Company"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_topic_scanner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `anibon/topic_scanner.py` (~100 lines)**
Analyzes macro info while dynamically detecting mid-stream franchise pivots in rolling chunks.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_topic_scanner.py -v`
Expected: PASS

---

### Task 4: Module `anibon.world_sanitizer` (Stage 5 Deterministic Audit)

**Files:**
- Create: `skills/anibon-timestamper-local/scripts/anibon/world_sanitizer.py`
- Test: `skills/anibon-timestamper-local/tests/test_world_sanitizer.py`

**Interfaces:**
- `sanitize_pokemon_names(text: str) -> str`
- `clean_token_stutters(text: str) -> str`
- `ensure_outro_timestamp(timestamps_text: str, last_chunk_text: str) -> str`
- `audit_and_sanitize_final_markdown(md_content: str, workspace: Path) -> Tuple[str, dict]`

- [ ] **Step 1: Write failing test in `tests/test_world_sanitizer.py`**
```python
def test_sanitize_pokemon_names_and_stutter():
    from anibon.world_sanitizer import sanitize_pokemon_names, clean_token_stutters
    raw = "ใช้ การ์โชมป์ สู้ใน Zelda: Breath of the Wildild"
    step1 = sanitize_pokemon_names(raw)
    step2 = clean_token_stutters(step1)
    assert "การ์โชมป์ (Garchomp)" in step2
    assert "Wildild" not in step2
    assert "Wild" in step2
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/test_world_sanitizer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `anibon/world_sanitizer.py` (~110 lines)**
Post-pass sanitization with 0 LLM tokens, enforcing exact naming rules and byte limits.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/test_world_sanitizer.py -v`
Expected: PASS

---

### Task 5: Wire Modules into Pipeline & Codify `SKILL.md`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/prompts.py`
- Modify: `skills/anibon-timestamper-local/SKILL.md`
- Test: Full regression test suite (`tests/`)

- [ ] **Step 1: Wire new modules into `prompts.py` and `process_chunks_local.py`**
Replace inline logic with clean library imports:
```python
from anibon.phonetic_bridge import load_phonetic_bridge
from anibon.domain_db import resolve_entities_for_chunk
from anibon.topic_scanner import extract_macro_anchor, scan_chunk_topic_pivot
from anibon.world_sanitizer import audit_and_sanitize_final_markdown
```

- [ ] **Step 2: Update `SKILL.md` Stage 5 Gate documentation**
Codify `/anibon-world-identity` as the mandatory quality sign-off gate.

- [ ] **Step 3: Run full regression test suite**
Run: `python -m pytest tests/ -v`
Expected: 100% pass across all unit and e2e tests.
