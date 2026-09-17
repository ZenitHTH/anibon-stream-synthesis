# On-Screen LiveChat Vision Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an on-demand vision tool to crop and extract burned-in live chat and picture emotes from edited livestreams when `.live_chat.json` is missing.

**Architecture:** Python CLI that probes chat layout (bottom-right vs left), extracts cropped frames with `ffmpeg`, calls `agy` Gemini 3.6 Flash with emote dictionary prompts, deduplicates scrolling messages, and outputs standard `<sec>\t[HH:MM:SS] Author: message` raw events.

**Tech Stack:** Python 3, ffmpeg, yt-dlp, `agy` (Gemini 3.6 Flash), pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-on-screen-livechat-vision-extraction-design.md`

## Global Constraints

- Never run continuous whole-stream scanning; support on-demand / spot-inspection for requested time ranges.
- Auto-detect chat overlay between Bottom-Right (`w=0.25, h=0.42, x=0.75, y=0.54`) and Left-Side (`w=0.28, h=0.60, x=0.01, y=0.22`).
- Picture emotes must map to standard Anibon channel tokens (`:_CunnyBoat:`, `:_Nerd:`, `:_MonkeyBoat:`, `555`) via `anibon_emoji_dictionary.md`.
- Output must strictly match standard raw event format `<sec>\t[HH:MM:SS] Author: message` so `align_live_chat.py` can parse it.
- In `agy` calls, use model `Gemini 3.6 Flash (Medium)` with `--dangerously-skip-permissions`.

---

### Task 1: Core ROI Layout & Frame Cropping Logic

**Files:**
- Create: `skills/anibon-livechat-analysis/scripts/visual_chat_crop.py`
- Test: `skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py`

**Interfaces:**
- Produces: `get_chat_roi(layout: str, width: int, height: int) -> dict[str, int]`, `build_crop_filter(roi: dict[str, int]) -> str`

- [ ] **Step 1: Write the failing test**

```python
# skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py
import pytest
from skills.anibon_livechat_analysis.scripts.visual_chat_crop import get_chat_roi, build_crop_filter

def test_get_chat_roi_bottom_right():
    roi = get_chat_roi("bottom-right", 1280, 720)
    assert roi["w"] == 320
    assert roi["h"] == 302
    assert roi["x"] == 960
    assert roi["y"] == 388

def test_get_chat_roi_left():
    roi = get_chat_roi("left", 1280, 720)
    assert roi["w"] == 358
    assert roi["h"] == 432
    assert roi["x"] == 12
    assert roi["y"] == 158

def test_build_crop_filter():
    roi = {"w": 320, "h": 302, "x": 960, "y": 388}
    assert build_crop_filter(roi) == "crop=320:302:960:388"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/anibon-livechat-analysis/scripts/visual_chat_crop.py
"""ROI calculation and ffmpeg filter generation for live chat overlays."""

ROI_PRESETS = {
    "bottom-right": {
        "w_ratio": 0.25,
        "h_ratio": 0.42,
        "x_ratio": 0.75,
        "y_ratio": 0.54,
    },
    "left": {
        "w_ratio": 0.28,
        "h_ratio": 0.60,
        "x_ratio": 0.01,
        "y_ratio": 0.22,
    },
}

def get_chat_roi(layout: str, width: int, height: int) -> dict[str, int]:
    if layout not in ROI_PRESETS:
        raise ValueError(f"Unknown layout: {layout}. Valid: {list(ROI_PRESETS.keys())}")
    cfg = ROI_PRESETS[layout]
    return {
        "w": int(width * cfg["w_ratio"]),
        "h": int(height * cfg["h_ratio"]),
        "x": int(width * cfg["x_ratio"]),
        "y": int(height * cfg["y_ratio"]),
    }

def build_crop_filter(roi: dict[str, int]) -> str:
    return f"crop={roi['w']}:{roi['h']}:{roi['x']}:{roi['y']}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-livechat-analysis/scripts/visual_chat_crop.py skills/anibon-livechat-analysis/tests/test_visual_chat_crop.py
git commit -m "feat: add visual chat ROI calculation and crop filter"
```

---

### Task 2: Scroll Deduplication and Event Formatting

**Files:**
- Create: `skills/anibon-livechat-analysis/scripts/visual_chat_dedup.py`
- Test: `skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py`

**Interfaces:**
- Produces: `format_raw_event(sec: int, author: str, text: str, superchat: str | None = None) -> str`, `deduplicate_frames_messages(frames_data: list[dict]) -> list[tuple[int, str]]`

- [ ] **Step 1: Write the failing test**

```python
# skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py
from skills.anibon_livechat_analysis.scripts.visual_chat_dedup import format_raw_event, deduplicate_frames_messages

def test_format_raw_event_normal():
    line = format_raw_event(605, "@user1", "ปู่เล่นตู้ไหน :_Nerd:")
    assert line == "605\t[00:10:05] @user1: ปู่เล่นตู้ไหน :_Nerd:"

def test_format_raw_event_superchat():
    line = format_raw_event(610, "@user2", "เป็นกำลังใจให้ครับ", superchat="THB 100.00")
    assert line == "610\t[00:10:10] 💰 SUPERCHAT (THB 100.00) from @user2: เป็นกำลังใจให้ครับ"

def test_deduplicate_frames_messages():
    frames = [
        {
            "sec": 600,
            "messages": [
                {"author": "@user1", "text": "ฮัลโหล", "superchat": None},
                {"author": "@user2", "text": "555", "superchat": None},
            ]
        },
        {
            "sec": 604,
            "messages": [
                # user2 message scrolled up
                {"author": "@user2", "text": "555", "superchat": None},
                {"author": "@user3", "text": ":_CunnyBoat:", "superchat": None},
            ]
        }
    ]
    events = deduplicate_frames_messages(frames)
    assert len(events) == 3
    assert events[0] == (600, "600\t[00:10:00] @user1: ฮัลโหล")
    assert events[1] == (600, "600\t[00:10:00] @user2: 555")
    assert events[2] == (604, "604\t[00:10:04] @user3: :_CunnyBoat:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/anibon-livechat-analysis/scripts/visual_chat_dedup.py
"""Deduplicate scrolling livechat messages across sampled frames."""

def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def format_raw_event(sec: int, author: str, text: str, superchat: str | None = None) -> str:
    ts = sec_to_hhmmss(sec)
    if superchat:
        return f"{sec}\t[{ts}] 💰 SUPERCHAT ({superchat}) from {author}: {text}"
    return f"{sec}\t[{ts}] {author}: {text}"

def deduplicate_frames_messages(frames_data: list[dict]) -> list[tuple[int, str]]:
    seen = set()
    events = []
    for frame in frames_data:
        sec = int(frame.get("sec", 0))
        for msg in frame.get("messages", []):
            author = msg.get("author", "").strip()
            text = msg.get("text", "").strip()
            sc = msg.get("superchat")
            key = (author.lower(), text.strip())
            if not key[0] or not key[1]:
                continue
            if key in seen:
                continue
            seen.add(key)
            formatted = format_raw_event(sec, author, text, superchat=sc)
            events.append((sec, formatted))
    events.sort(key=lambda x: x[0])
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-livechat-analysis/scripts/visual_chat_dedup.py skills/anibon-livechat-analysis/tests/test_visual_chat_dedup.py
git commit -m "feat: add live chat message deduplication and raw event formatting"
```

---

### Task 3: Vision CLI & Layout Auto-Detector

**Files:**
- Create: `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py`
- Test: `skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py`

**Interfaces:**
- Produces: CLI tool `extract_visual_livechat.py` supporting `--video-id`, `--video-path`, `--range`, `--output`, `--force-pos`.

- [ ] **Step 1: Write the failing test**

```python
# skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py
import json
from skills.anibon_livechat_analysis.scripts.extract_visual_livechat import parse_time_range, parse_gemini_chat_json

def test_parse_time_range():
    start_sec, end_sec = parse_time_range("00:10:00-00:12:30")
    assert start_sec == 600
    assert end_sec == 750

def test_parse_gemini_chat_json():
    raw_response = """
    Here are the messages:
    ```json
    [
      {"author": "@user1", "text": "ฮัลโหล :_Nerd:", "superchat": null}
    ]
    ```
    """
    parsed = parse_gemini_chat_json(raw_response)
    assert len(parsed) == 1
    assert parsed[0]["author"] == "@user1"
    assert parsed[0]["text"] == "ฮัลโหล :_Nerd:"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Implement `skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py`:
- Parses `--range "HH:MM:SS-HH:MM:SS"`.
- Checks if local video exists or runs `yt-dlp --cookies-from-browser chrome --download-sections`.
- Auto-detects layout (probes bottom-right and left crop with a fast probe or layout argument).
- Uses ffmpeg to crop frames at 1 frame per 3-4 seconds.
- Invokes `agy --model "Gemini 3.6 Flash (Medium)" --dangerously-skip-permissions --print ... --add-dir <frames_dir>`.
- Parses JSON results, runs `deduplicate_frames_messages`, and writes raw events file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py skills/anibon-livechat-analysis/tests/test_extract_visual_livechat.py
git commit -m "feat: add extract_visual_livechat CLI with agy vision proxy"
```

---

### Task 4: Documentation & Pipeline Integration

**Files:**
- Modify: `skills/anibon-livechat-analysis/SKILL.md`
- Modify: `skills/anibon-timestamper/SKILL.md`

- [ ] **Step 1: Update `anibon-livechat-analysis/SKILL.md`**
Add Section: "Fallback: On-Screen Burned-in LiveChat Extraction (When .live_chat.json is Missing)" documenting `extract_visual_livechat.py`.

- [ ] **Step 2: Update `anibon-timestamper/SKILL.md`**
Add reference to on-demand visual chat extraction for edited streams where `live_chat` replay was deleted by YouTube Studio.

- [ ] **Step 3: Commit**

```bash
git add skills/anibon-livechat-analysis/SKILL.md skills/anibon-timestamper/SKILL.md
git commit -m "docs: document visual livechat extraction in skills"
```

---

### Task 5: End-to-End Verification on Real Stream

- [ ] **Step 1: Run spot extraction on live stream `nF7pCwCZCaE`**
Run `python3 skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py --video-id nF7pCwCZCaE --range "00:10:00-00:10:10" -o /Users/zenithth/.gemini/antigravity/brain/9d98e9cf-150f-4d50-9b47-5847875baa7f/scratch/real_spot_events.txt`

- [ ] **Step 2: Verify output file format**
Check that `real_spot_events.txt` contains:
- Valid timestamps `<sec>\t[HH:MM:SS]`
- Correct authors (e.g. `@nekoalter4231`, `@infinity8078`)
- Mapped emotes (e.g. `:_Nerd:`)

- [ ] **Step 3: Verify alignment compatibility**
Run `python3 skills/anibon-timestamper/scripts/align_live_chat.py` against `real_spot_events.txt` to prove zero breakages in downstream timestamper.
