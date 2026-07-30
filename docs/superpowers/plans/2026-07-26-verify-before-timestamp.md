# World Identity Verification Before Timestamping

> **For agentic workers:** Prevent wrong lore/character names in timestamp output by enforcing verification before any story description is written.

**Goal:** Eliminate knowledge-cutoff errors (wrong planet, wrong character, wrong story arc) from timestamp generation workflow.

**Architecture:** Add a mandatory `world-identity-verify` gate at story start boundary. The gate: websearch current HSR version → identify new planet/characters → download reference SRT → build name map → verify each story stamp against map. No stamp written until gate passes.

**Tech Stack:** websearch, python3 (SRT parser), existing chunk JSONs

---

### Task 1: Add Pre-Write Verification Gate to Workflow

**Files:**
- Modify: `AGENTS.md` (workflow instructions)

- [ ] **Step 1: Write verification gate checklist**

```
=== WORLD IDENTITY VERIFICATION GATE ===
BEFORE writing any [WatchParty] stamp:
1. Websearch: "Honkai Star Rail [current version] [month] [year] story"
   - Confirm planet/region name (not from training data)
   - Extract: new characters, factions, key lore terms
2. If reference video URL available:
   - Download SRT: yt-dlp --write-subs --sub-lang en --skip-download <URL>
   - Parse SRT for: character names, location names, event keywords
   - Build mapping table: Thai transcript phoneme → verified EN name
3. Scan chunk transcripts at story boundary (~03:18 onward) for each candidate name
   - Match Thai phonemes against verified name map
   - If ambiguous, search web for Thai community name
4. Only then: write stamp descriptions
========================================
```

- [ ] **Step 2: Define rejection rules**

```
REJECT any stamp description containing:
- Training-data inference for post-cutoff content (any game version after training date)
- Character name from earlier version of same game ("Penacony character in Planarcadia")
- Phonetic match without websearch confirmation
```

- [ ] **Step 3: Integrate into AGENTS.md**

### Task 2: Build SRT Scene Aligner Script

**Files:**
- Create: `tools/align_ref_timeline.py`

**Interfaces:**
- Consumes: reference SRT file, stream chunk JSON files
- Produces: alignment table (ref_timestamp, stream_timestamp, scene_description, confidence)

- [ ] **Step 1: Write script skeleton**

```python
#!/usr/bin/env python3
"""Align reference video scene timestamps with stream timestamps.

Usage: python3 align_ref_timeline.py ref_story.srt chunks/ output.json

Parses SRT timestamp blocks → extracts scene descriptions → searches 
stream chunks for matching keywords → outputs alignment table.
"""
import json, re, sys
from pathlib import Path

def parse_srt(path):
    """Return list of {start_sec, end_sec, text} blocks."""
    pass

def search_chunks(chunks_dir, keyword):
    """Return list of chunk timestamps containing keyword."""
    pass

def build_alignment(srt_blocks, chunks_dir):
    """Map ref scenes to stream timestamps."""
    pass

if __name__ == "__main__":
    result = build_alignment(sys.argv[1], sys.argv[2])
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
```

- [ ] **Step 2: Implement parse_srt**

```python
def parse_srt(path):
    raw = Path(path).read_text(encoding='utf-8')
    blocks = re.split(r'\n\n+', raw.strip())
    result = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 3:
            continue
        time_match = re.match(r'(\d{2}):(\d{2}):(\d{2})', lines[1])
        if not time_match:
            continue
        h, m, s = int(time_match[1]), int(time_match[2]), int(time_match[3])
        start_sec = h * 3600 + m * 60 + s
        end_match = re.search(r'(\d{2}):(\d{2}):(\d{2})', lines[1].split('-->')[1])
        end_sec = 0
        if end_match:
            h,m,s = int(end_match[1]), int(end_match[2]), int(end_match[3])
            end_sec = h * 3600 + m * 60 + s
        text = ' '.join(lines[2:]).strip()
        result.append({'start_sec': start_sec, 'end_sec': end_sec, 'text': text})
    return result
```

- [ ] **Step 3: Implement search_chunks**

```python
def search_chunks(chunks_dir, keywords):
    """Find earliest stream timestamp for each keyword."""
    results = {}
    for path in sorted(Path(chunks_dir).glob('chunk_*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        start_sec = data.get('start_sec', 0)
        for seg in data.get('items', []):
            text = seg.get('text', '')
            for kw in keywords:
                if kw.lower() in text.lower() and kw not in results:
                    results[kw] = start_sec
    return results
```

- [ ] **Step 4: Implement build_alignment**

```python
def build_alignment(srt_blocks, chunks_dir):
    # Extract key scenes (character first appearance, lore drops)
    key_phrases = ['Sparkle', 'Silver Wolf', 'Jing Yuan', 'Aha', 
                   'Phantasmoon', 'mask', 'Mourning Actor', 'Yao Guang',
                   'Pearl', 'IPC', 'Graia', 'Himeko', 'Black Swan']
    chunk_hits = search_chunks(chunks_dir, key_phrases)
    
    alignment = []
    for block in srt_blocks:
        matched_chunk = None
        for phrase in key_phrases:
            if phrase.lower() in block['text'].lower():
                matched_chunk = chunk_hits.get(phrase)
                break
        alignment.append({
            'ref_sec': block['start_sec'],
            'ref_time': f"{block['start_sec']//3600:02d}:{(block['start_sec']%3600)//60:02d}",
            'text_preview': block['text'][:80],
            'stream_sec_guess': matched_chunk
        })
    return alignment
```

- [ ] **Step 5: Verify on real data**

Run: `python3 tools/align_ref_timeline.py ref_story.en.srt chunks/ alignment.json`

Expected: Output alignment table identifying when each character/scene appears in stream

### Task 3: Add Post-Write Byte Check Automation

**Files:**
- Create: `tools/check_parts.py`

- [ ] **Step 1: Write byte check script**

```python
#!/usr/bin/env python3
"""Check anibon_timestamps.md parts are under 3500B."""
import re, sys

def check(path):
    text = open(path, encoding='utf-8').read()
    dividers = [m.start() for m in re.finditer(r'═{40,}', text)]
    if len(dividers) < 3:
        print("FAIL: Need at least 3 dividers for 2 parts")
        return False
    
    p1 = text[:dividers[2]]
    p2 = text[dividers[2]:]
    b1, b2 = len(p1.encode('utf-8')), len(p2.encode('utf-8'))
    
    ok = True
    for name, b in [("Part 1", b1), ("Part 2", b2)]:
        status = "✅" if b <= 3500 else "❌"
        print(f"{name}: {b}B {status}")
        if b > 3500:
            ok = False
    return ok

if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1]) else 1)
```

- [ ] **Step 2: Verify on current file**

Run: `python3 tools/check_parts.py anibon_timestamps.md`

Expected: `Part 1: 3494B ✅`, `Part 2: 793B ✅`
