# check_sections Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up over-engineered patterns in `check_sections.py` to be lean and maintainable.

**Architecture:** We are refactoring existing functions in `check_sections.py` to remove redundant abstractions, simplify logic, and fix a bug in the split suggestion logic based on the Ponytail audit.

**Tech Stack:** Python standard library, `re`, `argparse`.

## Global Constraints

- Must run on standard Python 3.
- Do not break existing tests in `tests/test_check_sections.py`.

---

### Task 1: Refactor _full_blocks to use re.findall

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/check_sections.py`
- Test: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py`

**Interfaces:**
- Consumes: text string
- Produces: List of dicts `[{"label": str, "full": str, "body": str}]`

- [ ] **Step 1: Run tests to verify they currently pass**
```bash
pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py -v
```
Expected: All tests pass.

- [ ] **Step 2: Update regex and _full_blocks implementation**
Replace `SEP` and `_full_blocks` in `skills/anibon-timestamper/scripts/check_sections.py` with:
```python
BLOCK_RE = re.compile(r'((?:═+|-+)\n📌[^\n]+\n[^\n]+\n(?:═+|-+)\n*)(.*?)(?=(?:═+|-+)\n📌|\Z)', re.DOTALL)

def _full_blocks(text: str) -> list[dict]:
    """Extract full pasted blocks (separator header + body)."""
    results = []
    for header, body in BLOCK_RE.findall(text):
        full = header + body
        label = next((l for l in header.splitlines() if l.startswith("📌")), header[:60])
        results.append({"label": label, "full": full, "body": body})
    return results
```

- [ ] **Step 3: Run tests to verify they still pass**
```bash
pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add skills/anibon-timestamper/scripts/check_sections.py
git commit -m "refactor: simplify _full_blocks using re.findall"
```

### Task 2: Inline _byte_size

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/check_sections.py`

**Interfaces:**
- Consumes: `_byte_size(s)` calls
- Produces: Direct `len(s.encode("utf-8"))` usage

- [ ] **Step 1: Remove _byte_size function and inline**
Delete the `_byte_size` function entirely.
Then update `main()` to inline the logic. Replace:
```python
nbytes = _byte_size(r["full"].strip())
```
With:
```python
nbytes = len(r["full"].strip().encode("utf-8"))
```
Make sure to do this in both places where `_byte_size` is called inside `main()`.

- [ ] **Step 2: Run tests to verify**
```bash
pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py -v
```
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add skills/anibon-timestamper/scripts/check_sections.py
git commit -m "refactor: inline _byte_size for simplicity"
```

### Task 3: Fix suggest_split for byte-midpoint

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/check_sections.py`

**Interfaces:**
- Consumes: body string
- Produces: string (timestamp)

- [ ] **Step 1: Rewrite suggest_split to use byte-weight midpoint**
Replace `suggest_split` in `skills/anibon-timestamper/scripts/check_sections.py` with:
```python
def suggest_split(body: str) -> str | None:
    """Find the timestamp line closest to the byte-midpoint of a too-long body."""
    lines = [l for l in body.splitlines() if re.match(r'\d{2}:\d{2}:\d{2}', l.strip())]
    if len(lines) < 2:
        return None
        
    total_bytes = len(body.encode("utf-8"))
    midpoint = total_bytes / 2
    
    current_bytes = 0
    # Use next() with enumerate to find the split line efficiently
    split_idx = next((i for i, line in enumerate(lines) 
                      if (current_bytes := current_bytes + len(line.encode("utf-8"))) >= midpoint), 
                     len(lines) // 2)
                     
    return lines[split_idx].split(" - ")[0].strip()
```

- [ ] **Step 2: Run tests to verify**
```bash
pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py -v
```
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add skills/anibon-timestamper/scripts/check_sections.py
git commit -m "fix: use byte-midpoint for split suggestions instead of line count"
```

### Task 4: Refactor main() loops and argparse

**Files:**
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/check_sections.py`
- Modify: `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py`

**Interfaces:**
- Consumes: command line args
- Produces: CLI output

- [ ] **Step 1: Update main() implementation**
Replace `main()` in `skills/anibon-timestamper/scripts/check_sections.py` with this simplified version:
```python
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="Timestamp .md file")
    args = ap.parse_args()
    
    path = Path(args.file)
    if not path.exists():
        print(f"[!] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    blocks = _full_blocks(text)

    if not blocks:
        print("[!] No sections found. Make sure the file uses the ═══ separator format.")
        sys.exit(0)

    any_fail = False
    suggestions = []
    print(f"\n{'Status':10} {'Bytes':>6}  {'Chars':>6}  Section")
    print("─" * 80)
    
    for r in blocks:
        nbytes = len(r["full"].strip().encode("utf-8"))
        nchars = len(r["full"].strip())
        
        if nbytes > LIMIT:
            status = "❌ OVER  "
            any_fail = True
            label = "❌ "
        elif nbytes > WARN:
            status = "⚠️  WARN "
            any_fail = True
            label = "⚠️ "
        else:
            status = "✅ OK    "
            
        print(f"{status}  {nbytes:5}B  {nchars:5}c  {r['label'][:55]}")
        
        if nbytes > WARN:
            mid_ts = suggest_split(r["body"])
            tip = f"split at ≈ {mid_ts}" if mid_ts else "section too short to split"
            suggestions.append(f"  {label}{r['label'][:55]}\n     → {tip}  ({nbytes} bytes, {nchars} chars)")

    if any_fail:
        print("\n── Suggested split points ──────────────────────────────────────────────")
        for sug in suggestions:
            print(sug)
        sys.exit(1)
    else:
        print("\n✅ All sections are within the YouTube comment byte limit.")
```

- [ ] **Step 2: Update tests**
Modify `/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py`.
Find the `_run` function and remove the `--file` flag. 
Replace:
```python
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(f)],
        capture_output=True,
        env=env,
    )
```
With:
```python
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(f)],
        capture_output=True,
        env=env,
    )
```

- [ ] **Step 3: Run tests to verify**
```bash
pytest /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/tests/test_check_sections.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add skills/anibon-timestamper/scripts/check_sections.py tests/test_check_sections.py
git commit -m "refactor: simplify argparse and consolidate print loops in check_sections"
```
