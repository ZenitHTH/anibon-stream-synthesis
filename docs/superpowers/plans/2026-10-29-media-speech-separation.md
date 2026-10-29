# Automated Media-vs-Streamer Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency automated pipeline in `anibon-stream-synthesis` that detects in-stream songs/videos, identifies the media title and canonical lyrics via LiveChat + catalog/search, separates ASR-garbled lyrics from Pu Boat's interjections and gameplay speech (including mid-line collisions), and injects structured ground-truth separation blocks into local LLM prompts.

**Architecture:** A modular subpackage `lib/process/media/` (`types.py`, `trigger.py`, `phonetic.py`, `identifier.py`, `separator.py`) backed by `resources/media_catalog.json`. Stage 1 (`trigger.py`) gates execution using speaker-turn (`>>`) density, Boat intent phrases, and LiveChat song queries so normal chunks incur zero overhead. Stage 2 (`identifier.py`) resolves media entries from LiveChat crowd-sourcing and transcript cues. Stage 3 (`phonetic.py` + `separator.py`) performs Thai phonetic skeleton matching and mid-line collision splitting (`MEDIA_AUDIO` vs `BOAT_SPEECH` / `BOAT_GAMEPLAY`), wired into `lib/process/runners/recursive.py` and `lib/process/prompts.py`.

**Tech Stack:** Python 3.10+ standard library (`dataclasses`, `difflib`, `json`, `re`, `pathlib`, `unittest`). Zero third-party runtime dependencies.

**Spec:** `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/docs/superpowers/specs/2026-10-29-media-speech-separation-design.md`

## Global Constraints

- Every `.py` file using `|`, `list[`, `dict[`, `tuple[`, or `set[` annotations MUST start with `from __future__ import annotations`.
- All tests MUST use `unittest.TestCase` and run via `python3 -m unittest` — zero `pytest` imports anywhere (`test_skill_structure.py::test_zero_pytest_imports_across_repo`).
- Clean Code enforcement: max 200 lines per file, max 20 lines per function, max 3 parameters per function (bundle 3+ parameters into frozen dataclasses), no boolean flag parameters, max 2 indentation levels.
- Do not add or remove directories under `skills/` (repo enforces exactly 22 skill directories).

## Review Focus

1. **Severe Thai ASR vocal melisma garbling** (`"ผีไม่ได้ดักเจ้า"` / `"พี่ไม่ได้ดักเจ้า"` / `"หมาก็ยังหยุดเหา"`): Phonetic skeleton normalizer must strip tone marks, vowel length variations, and initial aspirated/unaspirated drift (`ผ`/`พ`, `ด`/`ร`) so garbled ASR lines match canonical lyrics `"พี่ไม่รักน้องเจ้า"` and `"หมาก็ยังหยุดเห่า"` with score $\ge 0.65$.
2. **Mid-line collision between song lyrics and Boat speech** (`"วันนี้ชาติเผชิญผ่านภัยไฟลุใครไม่พร้อมออกจากช่องกูออกไปเลย"`): Intra-line splitter must detect where canonical lyric tokens end and Boat's interjection markers (`"ใครไม่พร้อม"`, `"ออกจากช่องกู"`, `"ไอ้สัตว์"`, `"เดี๋ยวนะ"`) begin, emitting both `MEDIA_AUDIO` and `BOAT_SPEECH` segments for the same timestamp.
3. **Dual-track Minecraft/gameplay vocabulary spoken over active music** (`"อุ้ย Nether Scrap โอเคครับสวย"` or `"เผลอลบดาบไปเลยเมื่อกี้"` while อ.ไม้ร่ม plays): Lines containing gameplay tokens or first-person action markers (`"กูลบดาบ"`, `"วาร์ปกลับบ้าน"`, `"Nether"`, `"คราฟต์"`) must classify as `BOAT_GAMEPLAY`, never `MEDIA_AUDIO`.
4. **False-positive trigger on normal excited dialogue**: High `>>` count alone without music/media cues in transcript or LiveChat must not misclassify normal rapid monologue as a song unless combined trigger score meets threshold ($\ge 2.0$).
5. **Raw vs cleaned chunk text loss of `>>` markers**: `load_chunk_file()` strips `>>` via `clean_transcript_noise()`. The media trigger and separator must inspect raw lines from `chunk_XX.txt` (or preserve a `raw_text` field on each item) so `>>` turn boundaries are never lost before separation.

---

### Task 1: Media Data Contracts & Canonical Media Catalog (`types.py` & `media_catalog.json`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/resources/media_catalog.json`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/__init__.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/types.py`
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py`

**Interfaces:**
- Consumes: `common.resources.resource_path`
- Produces:
  - `MediaCandidate(media_id: str, title: str, artist: str, aliases: tuple[str, ...], canonical_phrases: tuple[str, ...], garble_patterns: tuple[str, ...])`
  - `SeparatedSegment(timestamp: str, label: str, raw_text: str, ground_truth: str, media_title: str = "")`
  - `MediaTriggerResult(triggered: bool, score: float, reasons: tuple[str, ...], chat_hints: tuple[str, ...])`
  - `ChunkMediaInput(raw_lines: tuple[str, ...], livechat_lines: tuple[str, ...], gameplay_keywords: tuple[str, ...] = ())`
  - `load_media_catalog(catalog_path: Optional[Path] = None) -> list[MediaCandidate]`

- [ ] **Step 1: Write the failing test in `tests/test_media_separation.py`**

```python
from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.media.types import MediaCandidate, load_media_catalog


class TestMediaSeparation(unittest.TestCase):
    def test_load_media_catalog_contains_core_stream_songs(self) -> None:
        catalog = load_media_catalog()
        ids = {c.media_id for c in catalog}
        self.assertIn("mairom_phi_mai_rak", ids)
        self.assertIn("ksc_return_happiness", ids)
        self.assertIn("maha_chulalongkorn", ids)
        mairom = next(c for c in catalog if c.media_id == "mairom_phi_mai_rak")
        self.assertIn("พี่ไม่รักน้องเจ้า", mairom.title)
        self.assertTrue(any("ผีไม่ได้ดักเจ้า" in g for g in mairom.garble_patterns))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.media'`

- [ ] **Step 3: Create `resources/media_catalog.json` and implement `lib/process/media/types.py` + `lib/process/media/__init__.py`**

Populate `resources/media_catalog.json` with recurring Anibon stream songs/clips (`mairom_phi_mai_rak`, `ksc_return_happiness`, `maha_chulalongkorn`, plus extensible schema for new discoveries) including `aliases` (LiveChat keywords like `"ไม้ร่ม"`, `"อาจารย์ไม้ร่ม"`, `"พี่ไม่รักน้องเจ้า"`, `"คืนความสุข"`, `"เราจะทำตามสัญญา"`, `"เพลงจุฬา"`, `"มหาจุฬาลงกรณ์"`), `canonical_phrases` (actual lyric/spoken intro lines), and `garble_patterns` (known ASR distortions). Implement frozen dataclasses and `load_media_catalog(catalog_path: Optional[Path] = None) -> list[MediaCandidate]` in `lib/process/media/types.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis add resources/media_catalog.json lib/process/media/ tests/test_media_separation.py
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis commit -m "feat(media): add media catalog and separation data contracts"
```

---

### Task 2: Stage 1 Zero-Cost Media Event Trigger (`trigger.py`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/trigger.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/__init__.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py`

**Interfaces:**
- Consumes: `ChunkMediaInput`, `MediaTriggerResult` from `process.media.types`
- Produces: `detect_media_trigger(media_input: ChunkMediaInput) -> MediaTriggerResult`

- [ ] **Step 1: Add failing trigger tests (including false-positive guard) to `tests/test_media_separation.py`**

```python
from process.media.types import ChunkMediaInput
from process.media.trigger import detect_media_trigger

    def test_trigger_activates_on_song_chunk_with_turn_markers_and_chat(self) -> None:
        raw_lines = (
            "(03:45:46) >> อ่าเพลงที่ผมจะร้องให้นี้",
            "(03:45:48) >> ไม่ใช่ผมจะร้องไห้คือเพลงที่ผมจะร้องนี้",
            "(03:46:01) >> ปลัดกระทรวงมหาดไทยตามหา",
            "(03:46:04) >> ไปที่ราชธานีก็ไม่เจอผมก็เลยมาหาที่นี้",
            "(03:46:22) >> อ่าเพลงนี้นะครับเป็นเพลงที่เพราะที่สุด",
            "(03:46:30) >> เพราะแม่ผมร้องให้ฟังตั้งแต่เด็กๆ",
            "(03:47:00) >> ศิลปินโลกุตตระเชิญฟังนะครับ",
        )
        chat_lines = (
            "[03:46:10] UserA: อาจารย์ไม้ร่ม 5555",
            "[03:47:41] UserB: ขอเพลงสำหรับคนรักพ่อหน่อยครับ",
        )
        res = detect_media_trigger(ChunkMediaInput(raw_lines=raw_lines, livechat_lines=chat_lines))
        self.assertTrue(res.triggered)
        self.assertGreaterEqual(res.score, 2.0)
        self.assertIn("อาจารย์ไม้ร่ม", " ".join(res.chat_hints))

    def test_trigger_ignores_normal_excited_gameplay_without_media_cues(self) -> None:
        raw_lines = tuple(f"(01:00:{i:02d}) >> ตีมอนสเตอร์ในดันเจี้ยน" for i in range(10))
        chat_lines = ("[01:00:05] UserA: ดาบแรงมากครับปู่",)
        res = detect_media_trigger(ChunkMediaInput(raw_lines=raw_lines, livechat_lines=chat_lines))
        self.assertFalse(res.triggered)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.media.trigger'`

- [ ] **Step 3: Implement `detect_media_trigger(media_input: ChunkMediaInput) -> MediaTriggerResult` in `lib/process/media/trigger.py`**

Score components:
- Speaker-turn density (`>>` count $\ge 6$ in chunk) contributes `+0.75` (never $\ge 2.0$ alone).
- Explicit transcript media-intent cues (`"เปิดเพลง"`, `"ฟังเพลง"`, `"เพลงที่ผมจะร้อง"`, `"เพลงนี้"`, `"ขอเพลง"`, `"ฟังศิลปะ"`, `"เวอร์ชั่นรีมิก"`, `"คอรัส"`, `"อินโทร"`, `"[เพลง]"`, `"♪"`) contribute `+1.5`.
- LiveChat media/song cues (`"เพลง"`, `"ไม้ร่ม"`, `"ลุงตู่"`, `"คืนความสุข"`, `"จุฬา"`, `"ร้องสด"`, `"เปิดคลิป"`) contribute `+1.0` and populate `chat_hints`.
- Threshold: `score >= 2.0` sets `triggered=True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis add lib/process/media/ tests/test_media_separation.py
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis commit -m "feat(media): add zero-cost media event trigger with false-positive guard"
```

---

### Task 3: Thai Phonetic Skeleton Matcher & Media Identifier (`phonetic.py` & `identifier.py`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/phonetic.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/identifier.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/__init__.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py`

**Interfaces:**
- Consumes: `ChunkMediaInput`, `MediaCandidate`, `load_media_catalog` from `process.media.types`
- Produces:
  - `thai_phonetic_skeleton(text: str) -> str`
  - `phonetic_Phrase_similarity(text_a: str, text_b: str) -> float`
  - `identify_active_media(media_input: ChunkMediaInput, catalog: Optional[list[MediaCandidate]] = None) -> list[MediaCandidate]`

- [ ] **Step 1: Add failing phonetic and media identification tests to `tests/test_media_separation.py`**

```python
from process.media.phonetic import thai_phonetic_skeleton, phonetic_phrase_similarity
from process.media.identifier import identify_active_media

    def test_thai_phonetic_skeleton_matches_melisma_garbles(self) -> None:
        sim1 = phonetic_phrase_similarity("ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้า", "พี่ไม่รักน้องเจ้า")
        sim2 = phonetic_phrase_similarity("หมาก็ยังหยุดเหาเลยครับ", "หมาก็ยังหยุดเห่าเลยครับ")
        self.assertGreaterEqual(sim1, 0.65)
        self.assertGreaterEqual(sim2, 0.85)

    def test_identify_active_media_resolves_mairom_and_ksc_from_chunk(self) -> None:
        inp = ChunkMediaInput(
            raw_lines=(
                "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้า",
                "(03:57:18) >> ขอดูแลคุ้มครองด้วยใจนี่คือคำสัญญา",
            ),
            livechat_lines=("[03:46:10] UserA: อาจารย์ไม้ร่มมาแล้ว",),
        )
        matched = identify_active_media(inp)
        matched_ids = [m.media_id for m in matched]
        self.assertIn("mairom_phi_mai_rak", matched_ids)
        self.assertIn("ksc_return_happiness", matched_ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.media.phonetic'`

- [ ] **Step 3: Implement `phonetic.py` and `identifier.py`**

In `lib/process/media/phonetic.py`:
- Strip Thai tone marks (`\u0e48-\u0e4e`), silence/melisma fillers (`เอ้อ`, `เอ้`, `เฮ้`, `ฮะ`, `อื`), and collapse homologous consonant families (`ผ/พ/ภ -> พ`, `ด/ร/ล -> ร`, `ข/ค/ฆ -> ค`, `ส/ศ/ษ/ซ -> ส`) so ASR vowel/consonant drift maps to a canonical skeleton, then compute best sliding-window `SequenceMatcher` ratio in `phonetic_phrase_similarity(text_a: str, text_b: str) -> float`.
In `lib/process/media/identifier.py`:
- Match `ChunkMediaInput` against `catalog` (via `aliases` in `livechat_lines` + `raw_lines`, `garble_patterns`, and `phonetic_phrase_similarity >= 0.65` against `canonical_phrases`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis add lib/process/media/ tests/test_media_separation.py
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis commit -m "feat(media): add Thai phonetic skeleton matcher and media identifier"
```

---

### Task 4: Line & Mid-Line Collision Separator + Prompt Block Formatter (`separator.py`)

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/separator.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/media/__init__.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py`

**Interfaces:**
- Consumes: `ChunkMediaInput`, `MediaCandidate`, `SeparatedSegment` from `process.media.types`; `detect_media_trigger` from `process.media.trigger`; `identify_active_media` from `process.media.identifier`; `phonetic_phrase_similarity` from `process.media.phonetic`
- Produces:
  - `separate_chunk_media(media_input: ChunkMediaInput, candidates: Optional[list[MediaCandidate]] = None) -> list[SeparatedSegment]`
  - `build_media_separation_prompt_block(media_input: ChunkMediaInput) -> str`

- [ ] **Step 1: Add failing tests for line separation, mid-line collision splitting, and dual-track gameplay classification to `tests/test_media_separation.py`**

```python
from process.media.separator import separate_chunk_media, build_media_separation_prompt_block

    def test_separator_splits_midline_collision_and_preserves_gameplay(self) -> None:
        inp = ChunkMediaInput(
            raw_lines=(
                "(03:48:11) >> แล้วถึงจะยอดเยี่ยมนะครับอือุ้ยnล scap",
                "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้าพี่ไม่",
                "(03:48:32) ได้ดักเจ้าพี่ไม่ได้เไม่ได้รักไงเออก็ไม่เข้าใจไง",
                "(03:52:18) >> เดี๋ยวนะโอตกใจเหมือนกูว่ากูลบดาบไอ้เหี้ย",
                "(03:57:26) วันนี้ชาติเผชิญผ่านภัยไฟลุใครไม่พร้อมออกจากช่องกูออกไปเลย",
            ),
            livechat_lines=("[03:46:10] UserA: เพลงอาจารย์ไม้ร่ม + คืนความสุข",),
            gameplay_keywords=("scap", "ลบดาบ", "nether", "วิลเลเจอร์"),
        )
        segments = separate_chunk_media(inp)
        by_ts = {}
        for seg in segments:
            by_ts.setdefault(seg.timestamp, []).append(seg)

        # 03:48:27 is pure garbled song lyric
        self.assertEqual(by_ts["03:48:27"][0].label, "MEDIA_AUDIO")
        self.assertIn("พี่ไม่รักน้องเจ้า", by_ts["03:48:27"][0].ground_truth)

        # 03:52:18 is Boat gameplay reaction while song plays
        self.assertEqual(by_ts["03:52:18"][0].label, "BOAT_GAMEPLAY")

        # 03:57:26 mid-line collision splits into MEDIA_AUDIO + BOAT_SPEECH
        labels_5726 = [s.label for s in by_ts["03:57:26"]]
        self.assertEqual(labels_5726, ["MEDIA_AUDIO", "BOAT_SPEECH"])

        block = build_media_separation_prompt_block(inp)
        self.assertIn("## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)", block)
        self.assertIn("[MEDIA_AUDIO", block)
        self.assertIn("[BOAT_SPEECH]", block)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'process.media.separator'`

- [ ] **Step 3: Implement `separate_chunk_media` and `build_media_separation_prompt_block` in `lib/process/media/separator.py`**

Key logic in `separator.py` (< 180 lines, functions $\le 20$ lines):
1. `_find_midline_split(text: str, candidate: MediaCandidate) -> Optional[tuple[str, str]]`: If a line starts with a canonical lyric or garble pattern and transitions mid-line into a Boat interjection marker (`"ใครไม่พร้อม"`, `"ใครได้บอก"`, `"ออกจากช่องกู"`, `"ไอ้สัตว์"`, `"ไอ้เหี้ย"`, `"เดี๋ยวนะ"`, `"กูมีเวท"`, `"ผมมีเวท"`, `"พี่ไม่ได้รักไง"`, `"เค้าไม่เข้าใจไง"`), split into `(lyric_part, boat_part)`.
2. `_classify_single_text(text: str, candidates: list[MediaCandidate], gameplay_kws: tuple[str, ...]) -> tuple[str, str, str]`:
   - If text matches Boat interjection markers (`"กู"`, `"มึง"`, `"ไอ้สัตว์"`, `"ไอ้เหี้ย"`, `"ช่องแชท"`, `"ขอบคุณ"`, `"คุณนารู"`) and has no unsplit lyric prefix $\rightarrow$ check gameplay keywords (`"ลบดาบ"`, `"วาร์ป"`, `"nether"`, `"scap"`, `"วิลเลเจอร์"`, `"วิจอร์"`, `"stone"`, `"คราฟ"`) to return `BOAT_GAMEPLAY` or `BOAT_SPEECH`.
   - If text matches any `candidate.garble_patterns`, `candidate.canonical_phrases`, or `phonetic_phrase_similarity >= 0.65` $\rightarrow$ return `("MEDIA_AUDIO", f"เนื้อเพลง/เสียงคลิป: {candidate.title}", candidate.title)`.
   - If text contains gameplay keywords $\rightarrow$ return `("BOAT_GAMEPLAY", text, "")`.
   - Default to `("BOAT_SPEECH", text, "")`.
3. `build_media_separation_prompt_block(media_input: ChunkMediaInput) -> str`:
   - Run `detect_media_trigger(media_input)`. If `not triggered`, return `""`.
   - Run `identify_active_media` and `separate_chunk_media`. If no `MEDIA_AUDIO` lines exist, return `""`.
   - Format a compact markdown block under `## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)` listing active media titles, warning the LLM never to attribute `[MEDIA_AUDIO]` lines or garbled lyrics to Pu Boat's own speech, and listing the separated timeline lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis add lib/process/media/ tests/test_media_separation.py
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis commit -m "feat(media): implement line and mid-line collision separator and prompt block"
```

---

### Task 5: Pipeline Wiring (`state.py`, `prompts.py`, `recursive.py`, `interface.py`)

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py:131-172`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/prompts.py:300-390`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/runners/recursive.py:165-188`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/process/__init__.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/interface.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py`

**Interfaces:**
- Consumes: `ChunkMediaInput`, `build_media_separation_prompt_block`, `separate_chunk_media` from `process.media`
- Produces:
  - `chunk["items"][i]["raw_text"]` preserved in `chunk.state.load_chunk_file()`
  - Automatic injection of `media_separation_block` in `process.prompts.build_recursive_prompt()` and `process.prompts.build_group_prompt()`
  - Re-exports `build_media_separation_prompt_block` and `separate_chunk_media` in `process` and `interface`

- [ ] **Step 1: Add failing end-to-end integration test in `tests/test_media_separation.py`**

```python
import tempfile
from chunk.state import load_chunk_file
from process.prompts import build_recursive_prompt

    def test_end_to_end_chunk_load_and_recursive_prompt_injects_media_separation(self) -> None:
        sample_chunk = (
            "# chunk_50 (03:45:00–03:50:30, cutoff=03:50:30)\n"
            "(03:45:46) >> อ่าเพลงที่ผมจะร้องให้นี้\n"
            "(03:47:00) >> ศิลปินโลกุตตระเชิญฟังนะครับ\n"
            "(03:47:06) >> รอก่อนไอ้สัตว์อย่ารีบเออคนฟังอ่ะช่องแชท\n"
            "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้าพี่ไม่\n"
            "(03:48:32) ได้ดักเจ้าพี่ไม่ได้เไม่ได้รักไงเออก็ไม่เข้าใจไง\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "chunk_50.txt"
            p.write_text(sample_chunk, encoding="utf-8")
            chunk_data = load_chunk_file(p)
            self.assertIn("raw_text", chunk_data["items"][0])
            self.assertTrue(chunk_data["items"][0]["raw_text"].startswith(">>"))

            prompt = build_recursive_prompt(
                chunk=chunk_data,
                current_topic="เล่น Minecraft สำรวจ Nether",
                rolling_summary="ปู่โบ๊ตสำรวจ Nether",
                livechat="[03:46:10] UserA: เพลงอาจารย์ไม้ร่ม 555",
            )
            self.assertIn("## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)", prompt)
            self.assertIn("พี่ไม่รักน้องเจ้า", prompt)
            self.assertIn("[BOAT_SPEECH]", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_media_separation.py -v`
Expected: FAIL (`"raw_text"` not in `chunk_data["items"][0]` and `## DETECTED MEDIA & LYRIC SEPARATION` not in `prompt`)

- [ ] **Step 3: Wire `raw_text` preservation in `lib/chunk/state.py` and automatic media block injection in `lib/process/prompts.py`, `lib/process/__init__.py`, and `lib/interface.py`**

1. In `lib/chunk/state.py`: In `load_chunk_file()`, store `"raw_text": raw_text` alongside `"text": clean_text` in each item dict so `>>` markers are preserved.
2. In `lib/process/prompts.py`: Add helper `_build_chunk_media_block(chunk: dict, livechat: str) -> str` that constructs `ChunkMediaInput` from `chunk["items"]` (using `it.get("raw_text") or it.get("text")`) and `livechat.splitlines()`, calls `build_media_separation_prompt_block()`, and appends the non-empty block to `context_extras` in both `build_recursive_prompt()` and `build_group_prompt()`.
3. Export `build_media_separation_prompt_block` and `separate_chunk_media` in `lib/process/__init__.py` and `lib/interface.py`.

- [ ] **Step 4: Run full repository test suite to verify all tests pass**

Run: `python3 -m unittest discover -s /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests -v`
Expected: PASS (all existing tests including `test_skill_structure.py` and `test_interface.py` + all new tests in `test_media_separation.py`).

- [ ] **Step 5: Commit**

```bash
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis add lib/ tests/test_media_separation.py docs/superpowers/
git -C /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis commit -m "feat(media): wire automated media-vs-boat separation into prompt pipeline"
```
