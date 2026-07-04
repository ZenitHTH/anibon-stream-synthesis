# Anibon Reusable CLI Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the scratch timestamping scripts into reusable, lean, and testable CLI tools following Ponytail principles (minimum code, standard libraries) and Superpowers architecture (decoupled logic, argparse).

**Architecture:** Each CLI tool will separate its terminal parsing layer (`if __name__ == "__main__":`) from its core business logic functions, allowing the core logic to be easily unit tested. The tools will utilize standard libraries (`re`, `csv`, `json`, `argparse`) and eliminate over-engineered loops and manual type checking.

**Tech Stack:** Python 3 (Standard Library), `pytest`

## Global Constraints

- Must use `argparse` for scripts with more than 2 parameters or optional flags.
- Do not use external dependencies (no `click`, no `pandas`). Use only the standard library.
- Must output primary data to `stdout` and logs/errors to `stderr`.
- Must follow Ponytail's lean code principles: eliminate redundant loops, use list comprehensions/generator expressions, and use dict-insertion order for deduplication.

---

### Task 1: Reusable `merge_timestamps.py` CLI

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/merge_timestamps.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_merge_timestamps.py`

**Interfaces:**
- Consumes: A list of text file paths containing raw timestamps.
- Produces: A sorted, deduplicated text file (or stdout stream) of timestamps. `merge_logic(file_paths: list[str]) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_merge_timestamps.py
import pytest
import tempfile
import os
import sys

sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts")
from merge_timestamps import merge_logic

def test_merge_logic():
    with tempfile.NamedTemporaryFile("w", delete=False) as f1, \
         tempfile.NamedTemporaryFile("w", delete=False) as f2:
        f1.write("00:05:00 - [Talk] Hello\n00:01:00 No Tag\n")
        f2.write("00:01:00 No Tag\n00:10:00 - [News] Update\n")
        
    try:
        results = merge_logic([f1.name, f2.name])
        assert len(results) == 3
        assert results[0].startswith("00:01:00")
        assert results[1].startswith("00:05:00")
        assert results[2].startswith("00:10:00")
    finally:
        os.remove(f1.name)
        os.remove(f2.name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_merge_timestamps.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError for `merge_timestamps`.

- [ ] **Step 3: Write minimal lean implementation**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/merge_timestamps.py
import re
import argparse
import sys

def parse_time(ts_str):
    parts = list(map(int, ts_str.split(":")))
    return parts[0]*3600 + parts[1]*60 + parts[2] if len(parts) == 3 else 0

def merge_logic(file_paths):
    merged = []
    pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})\s*(?:\[(.*?)\])?\s*(.*)$')
    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    match = pattern.match(line)
                    if match:
                        ts, tag, desc = match.groups()
                        tag_str = f"[{tag}] " if tag else "[Talk] "
                        seconds = parse_time(ts)
                        merged.append({"sec": seconds, "line": f"{ts} - {tag_str}{desc}"})
        except FileNotFoundError:
            print(f"Warning: {fp} not found", file=sys.stderr)
            
    merged.sort(key=lambda x: x["sec"])
    # Deduplicate using dict insertion order (Ponytail principle)
    deduped = list({e["sec"]: e["line"] for e in merged}.values())
    return deduped

def main():
    parser = argparse.ArgumentParser(description="Merge and sort timestamps.")
    parser.add_argument("inputs", nargs="+", help="Input text files")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    results = merge_logic(args.inputs)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(results) + "\n")
    else:
        for r in results:
            print(r)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_merge_timestamps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run: 
```bash
cd /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/
git add tests/test_merge_timestamps.py skills/anibon-timestamper/scripts/merge_timestamps.py
git commit -m "feat: add lean reusable merge_timestamps CLI"
```

---

### Task 2: Reusable `assemble_timestamps.py` CLI

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/assemble_timestamps.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_assemble_timestamps.py`

**Interfaces:**
- Consumes: A draft timestamps file and a topics configuration JSON file.
- Produces: A chunked markdown file that respects the 4500 byte limit per section. `assemble_logic(lines: list[str], topics: list[dict], limit: int) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_assemble_timestamps.py
import pytest
import sys

sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts")
from assemble_timestamps import assemble_logic

def test_assemble_logic():
    lines = [
        "00:00:00 - [Talk] Start",
        "00:05:00 - [Game] Play",
        "00:10:00 - [End] Stop"
    ]
    topics = [
        {"start": "00:00:00", "title": "Intro", "summary": "Start", "topic": "Gen"}
    ]
    # Set an artificially low limit to force splitting
    result_lines = assemble_logic(lines, topics, limit_bytes=50, max_chunk_bytes=40)
    
    joined = "\n".join(result_lines)
    assert "📌 ส่วนที่ 1" in joined
    assert "📌 ส่วนที่ 2" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_assemble_timestamps.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal lean implementation**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/assemble_timestamps.py
import re
import argparse
import json
import sys

def parse_time(ts_str):
    parts = list(map(int, ts_str.split(":")))
    return parts[0]*3600 + parts[1]*60 + parts[2] if len(parts) == 3 else 0

def assemble_logic(lines, topics, limit_bytes=4500, max_chunk_bytes=2400):
    entries = []
    pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})\s*-\s*\[(.*?)\]\s*(.*)$')
    for line in lines:
        match = pattern.match(line)
        if match:
            entries.append({"sec": parse_time(match.group(1)), "ts": match.group(1), "line": line})
            
    # Group by topic using simple iteration (Ponytail)
    groups = {i: [] for i in range(len(topics))}
    for entry in entries:
        idx = max((i for i, t in enumerate(topics) if entry["sec"] >= parse_time(t["start"])), default=0)
        groups[idx].append(entry)
        
    output = ["# วิดีโอสตรีม ANIBON - ทริปส์และข่าวสารเกมกาชา\n"]
    sec_num = 1
    
    for i, t in enumerate(topics):
        topic_entries = groups[i]
        if not topic_entries: continue
        
        bytes_total = len("\n".join(e["line"] for e in topic_entries).encode("utf-8"))
        estimated = bytes_total + 300
        
        # Floor division instead of math.ceil (Ponytail)
        num_parts = (estimated + max_chunk_bytes - 1) // max_chunk_bytes if estimated > 3500 else 1
        items_per = (len(topic_entries) + num_parts - 1) // num_parts
        
        for p in range(num_parts):
            chunk = topic_entries[p * items_per : (p + 1) * items_per]
            if not chunk: continue
            
            part_suffix = f" (ตอนที่ {p+1}/{num_parts})" if num_parts > 1 else ""
            summary = f"{t['summary']}{part_suffix}"
            topic_str = f"{t['topic']} - ตอนที่ {p+1}" if num_parts > 1 else t["topic"]
            
            output.append("═════════════════════════════════════════════════════════")
            output.append(f"📌 ส่วนที่ {sec_num}: {summary}")
            output.append(f"(หัวข้อ: {topic_str} | ⏱ เริ่ม: {chunk[0]['ts']})")
            output.append("═════════════════════════════════════════════════════════")
            output.extend(e["line"] for e in chunk)
            output.append("")
            sec_num += 1
            
    return output

def main():
    parser = argparse.ArgumentParser(description="Assemble timestamps into split markdown.")
    parser.add_argument("input", help="Merged timestamps file")
    parser.add_argument("--topics", required=True, help="Topics JSON config file")
    parser.add_argument("-o", "--output", help="Output MD file (stdout if omitted)")
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        
    with open(args.topics, "r", encoding="utf-8") as f:
        topics = json.load(f)
        
    results = assemble_logic(lines, topics)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(results) + "\n")
    else:
        for r in results: print(r)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_assemble_timestamps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run: 
```bash
cd /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/
git add tests/test_assemble_timestamps.py skills/anibon-timestamper/scripts/assemble_timestamps.py
git commit -m "feat: add lean reusable assemble_timestamps CLI"
```

---

### Task 3: Reusable `analyze_transcript.py` CLI

**Files:**
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/analyze_transcript.py`
- Create: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_analyze_transcript.py`

**Interfaces:**
- Consumes: A YouTube transcript JSON array, and a JSON config of keywords mapping.
- Produces: Standard CSV output to `stdout` containing the keyword density over time. `analyze_logic(events: list, keywords: dict, window: int) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_analyze_transcript.py
import pytest
import sys

sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts")
from analyze_transcript import analyze_logic

def test_analyze_logic():
    events = [
        {"start": 10, "timestamp": "00:00:10", "text": "Playing some fate grand order today."},
        {"start": 30, "timestamp": "00:00:30", "text": "Let's roll for genshin."}
    ]
    keywords = {"Fate": ["fate", "fgo"], "Genshin": ["genshin"]}
    
    results = analyze_logic(events, keywords, window=60)
    assert len(results) == 1
    assert results[0]["Time"] == "00:00:10"
    assert results[0]["Fate"] == 1
    assert results[0]["Genshin"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_analyze_transcript.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal lean implementation**

```python
# /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/analyze_transcript.py
import json
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Fallback to local _transcript path if needed
try:
    import _transcript
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
    import _transcript

def analyze_logic(events, keywords, window=600):
    results = defaultdict(lambda: {k: 0 for k in keywords})
    time_map = {}
    
    for item in events:
        text = item.get("text", "").lower()
        slot = int(item.get("start", 0) // window)
        
        if slot not in time_map:
            time_map[slot] = item.get("timestamp", "")
            
        for key, pats in keywords.items():
            if any(p in text for p in pats):
                results[slot][key] += 1
                
    output = []
    for slot in sorted(results.keys()):
        row = {"Time": time_map[slot]}
        row.update(results[slot])
        output.append(row)
        
    return output

def main():
    parser = argparse.ArgumentParser(description="Analyze keyword density in transcripts.")
    parser.add_argument("transcript", help="Raw transcript JSON")
    parser.add_argument("--keywords", required=True, help="Keywords JSON config file")
    parser.add_argument("--window", type=int, default=600, help="Time window in seconds")
    args = parser.parse_args()
    
    with open(args.transcript, "r", encoding="utf-8") as f:
        events = _transcript._flatten_json3(json.load(f))
        
    with open(args.keywords, "r", encoding="utf-8") as f:
        keywords = json.load(f)
        
    results = analyze_logic(events, keywords, args.window)
    if not results: return
    
    writer = csv.DictWriter(sys.stdout, fieldnames=["Time"] + list(keywords.keys()))
    writer.writeheader()
    writer.writerows(results)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_analyze_transcript.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run: 
```bash
cd /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/
git add tests/test_analyze_transcript.py skills/anibon-timestamper/scripts/analyze_transcript.py
git commit -m "feat: add lean reusable analyze_transcript CLI"
```
