# `anibon-stream-activity` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `anibon-stream-activity` skill and scripts to extract high-resolution storyboard frames, generate a continuous on-screen activity & webcam timeline (`activity_timeline.json`), and inject visual grounding context into `anibon-timestamper` subagents to eliminate speech-action divergence errors.

**Architecture:** Python CLI tools for downloading high-res YouTube storyboards (`sb3`/`sb2`/`sb1`/`sb0`), adaptively slicing crisp tiles, batch-classifying gameplay and webcam state (AFK/presence, facial expression, layout) via Gemini Vision / `agy`, aligning to transcript chunks, and providing explicit divergence disambiguation rules to chunk timestamper subagents.

**Tech Stack:** Python 3.10+, `yt-dlp`, `Pillow` (PIL) / `imagehash` for grid slicing & scene change detection, `pytest`, Antigravity `agy` CLI / Gemini Vision API.

**Spec:** `docs/superpowers/specs/2026-08-28-anibon-stream-activity-design.md`

## Global Constraints

- Python 3 with `-X utf8` compatibility across macOS and Windows.
- High-res storyboard format priority: `sb3/sb2/sb1/sb0` (never hardcode low-res `sb0` exclusively).
- Subagents keep speech-primary tagging: `[Talk]` / `[News]` when conversing during casual gameplay, with game context in parentheses (e.g. `[Talk] เม้าท์มอยเรื่อง... (ระหว่างเล่น Monster Hunter)`).
- Zero lore hallucination: real-life stories must never be attributed as game lore.
- Empty chair / speaker away detection tags silent gaps as `[AFK] พักเบรก / ลุกจากโต๊ะ`.

---

### Task 1: High-Resolution Storyboard Unpacker & Cropper

**Files:**
- Create: `skills/anibon-stream-activity/scripts/unpack_storyboard.py`
- Test: `tests/test_unpack_storyboard.py`

**Interfaces:**
- Consumes: MHTML storyboard file or JPEG sprite sheets downloaded by `yt-dlp`.
- Produces: `unpack_storyboard_mhtml(mhtml_path, out_dir)` -> list of JPEG slide paths; `crop_timestamp_frame(slide_paths, target_sec, duration_sec, out_path)` -> crisp cropped JPEG image.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_unpack_storyboard.py
import os
import pytest
from PIL import Image
from skills.anibon_stream_activity.scripts.unpack_storyboard import (
    extract_slides_from_mhtml_bytes,
    calculate_tile_bbox,
    crop_frame_at_second,
)

def test_calculate_tile_bbox():
    # 3x3 grid on a 960x540 image (each tile 320x180)
    bbox = calculate_tile_bbox(tile_index=4, grid_cols=3, grid_rows=3, img_w=960, img_h=540)
    assert bbox == (320, 180, 640, 360)

def test_extract_slides_from_mhtml_bytes(tmp_path):
    # Mock MHTML multipart content with JPEG markers
    fake_jpeg = b"\xff\xd8fakejpegcontent\xff\xd9"
    mhtml_content = b"--boundary\r\nContent-Type: image/jpeg\r\n\r\n" + fake_jpeg + b"\r\n--boundary--"
    slides = extract_slides_from_mhtml_bytes(mhtml_content, str(tmp_path))
    assert len(slides) == 1
    assert os.path.exists(slides[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_unpack_storyboard.py -v`  
Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/anibon-stream-activity/scripts/unpack_storyboard.py
import os
import glob
from PIL import Image

def extract_slides_from_mhtml_bytes(data: bytes, output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    parts = data.split(b"--")
    slide_paths = []
    valid_count = 0
    for p in parts:
        if b"image/jpeg" in p or b"\xff\xd8" in p:
            idx = p.find(b"\xff\xd8")
            end_idx = p.rfind(b"\xff\xd9")
            if idx != -1:
                valid_count += 1
                jpg_data = p[idx:end_idx+2] if end_idx != -1 else p[idx:]
                out_path = os.path.join(output_dir, f"slide_{valid_count:04d}.jpg")
                with open(out_path, "wb") as f:
                    f.write(jpg_data)
                slide_paths.append(out_path)
    return slide_paths

def calculate_tile_bbox(tile_index: int, grid_cols: int, grid_rows: int, img_w: int, img_h: int) -> tuple[int, int, int, int]:
    col = tile_index % grid_cols
    row = tile_index // grid_cols
    tile_w = img_w // grid_cols
    tile_h = img_h // grid_rows
    x1 = col * tile_w
    y1 = row * tile_h
    return (x1, y1, x1 + tile_w, y1 + tile_h)

def crop_frame_at_second(slide_paths: list[str], target_sec: float, total_duration: float, out_path: str, grid_cols: int = 3, grid_rows: int = 3) -> str:
    if not slide_paths:
        raise ValueError("No slides provided")
    total_slides = len(slide_paths)
    tiles_per_slide = grid_cols * grid_rows
    total_tiles = total_slides * tiles_per_slide
    
    sec_per_tile = total_duration / total_tiles if total_tiles > 0 else 10.0
    tile_global_idx = min(total_tiles - 1, max(0, int(target_sec / sec_per_tile)))
    
    slide_idx = tile_global_idx // tiles_per_slide
    tile_in_slide = tile_global_idx % tiles_per_slide
    
    slide_path = slide_paths[min(slide_idx, len(slide_paths) - 1)]
    with Image.open(slide_path) as img:
        bbox = calculate_tile_bbox(tile_in_slide, grid_cols, grid_rows, img.width, img.height)
        cropped = img.crop(bbox)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        cropped.save(out_path, "JPEG", quality=95)
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_unpack_storyboard.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-stream-activity/scripts/unpack_storyboard.py tests/test_unpack_storyboard.py
git commit -m "feat(activity): add high-res storyboard unpacker and tile cropper"
```

---

### Task 2: Activity & Webcam Timeline Extractor

**Files:**
- Create: `skills/anibon-stream-activity/scripts/extract_activity_timeline.py`
- Test: `tests/test_extract_activity_timeline.py`

**Interfaces:**
- Consumes: Sliced storyboard frames, stream duration.
- Produces: `<workspace>/activity_timeline.json` containing merged time intervals with gameplay, app, and webcam state (`speaker_present`, `expression`, `layout`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_activity_timeline.py
import json
import pytest
from skills.anibon_stream_activity.scripts.extract_activity_timeline import merge_frame_classifications

def test_merge_frame_classifications():
    raw_frames = [
        {
            "sec": 0,
            "timestamp": "00:00:00",
            "app_or_game": "Steam Store",
            "category": "Web Browsing",
            "state": "browsing sales",
            "webcam": {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"}
        },
        {
            "sec": 60,
            "timestamp": "00:01:00",
            "app_or_game": "Steam Store",
            "category": "Web Browsing",
            "state": "browsing reviews",
            "webcam": {"speaker_present": True, "expression": "laughing", "layout": "corner_cam"}
        },
        {
            "sec": 120,
            "timestamp": "00:02:00",
            "app_or_game": "Monster Hunter Wilds",
            "category": "Gameplay",
            "state": "hunting",
            "webcam": {"speaker_present": True, "expression": "focused", "layout": "corner_cam"}
        },
        {
            "sec": 180,
            "timestamp": "00:03:00",
            "app_or_game": "Monster Hunter Wilds",
            "category": "Gameplay",
            "state": "hunting",
            "webcam": {"speaker_present": False, "expression": "away", "layout": "corner_cam"}
        }
    ]
    
    merged = merge_frame_classifications(raw_frames, step_sec=60)
    assert len(merged) == 3
    assert merged[0]["app_or_game"] == "Steam Store"
    assert merged[0]["start"] == "00:00:00"
    assert merged[0]["end"] == "00:02:00"
    assert merged[1]["app_or_game"] == "Monster Hunter Wilds"
    assert merged[1]["webcam"]["speaker_present"] is True
    assert merged[2]["webcam"]["speaker_present"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract_activity_timeline.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# skills/anibon-stream-activity/scripts/extract_activity_timeline.py
import json
import argparse
import os

def format_timestamp(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def merge_frame_classifications(frames: list[dict], step_sec: int = 60) -> list[dict]:
    if not frames:
        return []
    
    intervals = []
    current = None
    
    for f in frames:
        sec = f.get("sec", 0)
        app = f.get("app_or_game", "Unknown")
        cat = f.get("category", "Other")
        state = f.get("state", "")
        wb = f.get("webcam", {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"})
        speaker_present = wb.get("speaker_present", True)
        
        # Check if same interval
        if (current is not None and 
            current["app_or_game"] == app and 
            current["category"] == cat and 
            current["webcam"]["speaker_present"] == speaker_present):
            current["end_sec"] = sec + step_sec
            current["end"] = format_timestamp(current["end_sec"])
            if state and state not in current["states"]:
                current["states"].append(state)
        else:
            if current is not None:
                intervals.append({
                    "start": current["start"],
                    "end": current["end"],
                    "start_sec": current["start_sec"],
                    "end_sec": current["end_sec"],
                    "app_or_game": current["app_or_game"],
                    "category": current["category"],
                    "details": "; ".join(current["states"]) or current["app_or_game"],
                    "webcam": current["webcam"]
                })
            current = {
                "start": format_timestamp(sec),
                "end": format_timestamp(sec + step_sec),
                "start_sec": sec,
                "end_sec": sec + step_sec,
                "app_or_game": app,
                "category": cat,
                "states": [state] if state else [],
                "webcam": wb
            }
            
    if current is not None:
        intervals.append({
            "start": current["start"],
            "end": current["end"],
            "start_sec": current["start_sec"],
            "end_sec": current["end_sec"],
            "app_or_game": current["app_or_game"],
            "category": current["category"],
            "details": "; ".join(current["states"]) or current["app_or_game"],
            "webcam": current["webcam"]
        })
    return intervals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract_activity_timeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-stream-activity/scripts/extract_activity_timeline.py tests/test_extract_activity_timeline.py
git commit -m "feat(activity): add activity and webcam timeline merging logic"
```

---

### Task 3: Chunk Activity Aligner

**Files:**
- Create: `skills/anibon-stream-activity/scripts/align_activity_timeline.py`
- Test: `tests/test_align_activity_timeline.py`

**Interfaces:**
- Consumes: `<workspace>/activity_timeline.json` and `<workspace>/chunks/chunk_*.xml`.
- Produces: `<workspace>/activity/activity_chunk_NN.txt` and summary index.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_align_activity_timeline.py
import pytest
from skills.anibon_stream_activity.scripts.align_activity_timeline import align_intervals_to_chunk

def test_align_intervals_to_chunk():
    intervals = [
        {
            "start": "00:00:00",
            "end": "00:07:00",
            "start_sec": 0,
            "end_sec": 420,
            "app_or_game": "Steam Store",
            "category": "Web Browsing",
            "details": "looking at sales",
            "webcam": {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"}
        },
        {
            "start": "00:07:00",
            "end": "00:30:00",
            "start_sec": 420,
            "end_sec": 1800,
            "app_or_game": "Monster Hunter Wilds",
            "category": "Gameplay",
            "details": "hunting monsters",
            "webcam": {"speaker_present": True, "expression": "focused", "layout": "corner_cam"}
        }
    ]
    
    # Chunk covering 00:05:00 to 00:10:00 (300s to 600s)
    text = align_intervals_to_chunk(intervals, chunk_start_sec=300, chunk_end_sec=600)
    assert "Steam Store" in text
    assert "Monster Hunter Wilds" in text
    assert "[Gameplay]" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_align_activity_timeline.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# skills/anibon-stream-activity/scripts/align_activity_timeline.py
import json
import os

def align_intervals_to_chunk(intervals: list[dict], chunk_start_sec: float, chunk_end_sec: float) -> str:
    matching = []
    for item in intervals:
        i_start = item.get("start_sec", 0)
        i_end = item.get("end_sec", 0)
        # Check overlap
        if max(chunk_start_sec, i_start) < min(chunk_end_sec, i_end):
            matching.append(item)
            
    if not matching:
        return "No specific visual activity detected for this window."
        
    lines = []
    for m in matching:
        wb = m.get("webcam", {})
        afk_note = " [⚠️ SPEAKER AWAY/AFK]" if not wb.get("speaker_present", True) else ""
        lines.append(f"- {m['start']} - {m['end']}: {m['app_or_game']} [{m['category']}]{afk_note} ({m.get('details', '')})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_align_activity_timeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-stream-activity/scripts/align_activity_timeline.py tests/test_align_activity_timeline.py
git commit -m "feat(activity): add chunk activity aligner"
```

---

### Task 4: Skill Definition & Activity Documentation

**Files:**
- Create: `skills/anibon-stream-activity/SKILL.md`
- Create: `skills/anibon-stream-activity/references/activity_categories.md`

- [ ] **Step 1: Write `skills/anibon-stream-activity/SKILL.md`** with complete instructions, CLI usage, and high-res storyboard downloading guidance.
- [ ] **Step 2: Write `skills/anibon-stream-activity/references/activity_categories.md`** defining all standard categories (`Gameplay`, `Menu/Inventory`, `Gacha`, `Web Browsing`, `Video Reaction`, `AFK/Intermission`, `Fullscreen Cam`).
- [ ] **Step 3: Commit**

```bash
git add skills/anibon-stream-activity/SKILL.md skills/anibon-stream-activity/references/activity_categories.md
git commit -m "docs(skill): add anibon-stream-activity skill definition and category reference"
```

---

### Task 5: Orchestrator & Agent Prompt Integration

**Files:**
- Modify: `skills/anibon-timestamper/SKILL.md` (Add Step 3.6 Activity & Webcam Timeline)
- Modify: `skills/anibon-timestamper/references/subagent-prompt-template.md` (Inject `ON_SCREEN_ACTIVITY`)
- Modify: `agents/anibon-chunk-timestamper.md` (Add Divergence, AFK & Webcam Emotion rules)
- Modify: `skills/antigravity-vision-proxy/SKILL.md` (Update sb0 -> sb3 format selector)

- [ ] **Step 1: Update `skills/anibon-timestamper/SKILL.md`** to add Step 3.6 for building `activity_timeline.json` and aligning to chunk directories.
- [ ] **Step 2: Update `skills/anibon-timestamper/references/subagent-prompt-template.md`** to format and inject `ON_SCREEN_ACTIVITY` per chunk.
- [ ] **Step 3: Update `agents/anibon-chunk-timestamper.md`** with the explicit Divergence Rule, AFK Empty Chair Grounding, and Deictic Grounding.
- [ ] **Step 4: Update `skills/antigravity-vision-proxy/SKILL.md`** with the high-res format selector `-f "sb3/sb2/sb1/sb0"`.
- [ ] **Step 5: Run existing plugin test suite**

Run: `pytest tests/ -v`  
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/anibon-timestamper/ agents/ skills/antigravity-vision-proxy/
git commit -m "feat(timestamper): integrate visual activity & webcam grounding into orchestrator pipeline and chunk subagents"
```
