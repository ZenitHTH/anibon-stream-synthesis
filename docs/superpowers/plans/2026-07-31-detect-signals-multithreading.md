# Multithreaded Chunk Signal Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parallelize transcript chunk processing in `detect_signals.py` using standard library `ThreadPoolExecutor` and hardware-adaptive worker counts (`os.cpu_count()`).

**Architecture:** Refactor single-threaded chunk loop in `detect_signals.py` into a helper worker function `_process_single_chunk`, dispatching tasks via `concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) + 4))`, and gathering results deterministically in chunk order.

**Tech Stack:** Python 3 standard library (`concurrent.futures`, `os`, `argparse`, `json`, `pathlib`).

## Global Constraints

- Standard library only (`concurrent.futures`, `os`, `json`, `sys`, `pathlib`). No external dependencies.
- Output JSON schema of `signals.json` must remain identical to single-threaded output.
- All existing tests in `tests/test_detect_signals.py` and across the plugin suite must pass.

---

### Task 1: Refactor `detect_signals.py` with `ThreadPoolExecutor` and add unit test for multithreading

**Files:**
- Modify: `skills/anibon-timestamper/scripts/detect_signals.py:1-143`
- Modify: `tests/test_detect_signals.py:1-35`

**Interfaces:**
- Consumes: `match_chunk(chunk_text, entries, threshold)`
- Produces: `_process_single_chunk(item, entries, threshold) -> (chunk_name, res_dict, has_matched)`

- [ ] **Step 1: Write test for multithreaded chunk processing**

Add `test_process_single_chunk` and `test_multithreaded_execution` to `tests/test_detect_signals.py`:

```python
from detect_signals import _process_single_chunk, match_chunk, load_knowledge
from concurrent.futures import ThreadPoolExecutor

def test_process_single_chunk():
    entries = {"FGO": {"kind": "game", "file": "fgo.md"}}
    item = ("chunk_001", 10, "พูดถึง FGO ครับ")
    name, res, matched = _process_single_chunk(item, entries, 1)
    assert name == "chunk_001"
    assert res["start_sec"] == 10
    assert "FGO" in res["matched_keywords"]
    assert matched is True

def test_multithreaded_execution():
    entries = {"FGO": {"kind": "game", "file": "fgo.md"}}
    items = [("chunk_01", 0, "FGO"), ("chunk_02", 10, "nothing")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda it: _process_single_chunk(it, entries, 1), items))
    assert len(results) == 2
    assert results[0][0] == "chunk_01" and results[0][2] is True
    assert results[1][0] == "chunk_02" and results[1][2] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=lib:skills/whisper-corruption-recovery/scripts:skills/anibon-timestamper/scripts:skills/creating-highlight-video/scripts .venv/bin/pytest tests/test_detect_signals.py -v`  
Expected: FAIL with `ImportError: cannot import name '_process_single_chunk'`

- [ ] **Step 3: Implement `_process_single_chunk` and ThreadPoolExecutor in `detect_signals.py`**

In `skills/anibon-timestamper/scripts/detect_signals.py`:
1. Ensure imports include `os` and `from concurrent.futures import ThreadPoolExecutor`.
2. Add `_process_single_chunk` function:

```python
def _process_single_chunk(item: tuple, entries: dict, threshold: int = 1) -> tuple[str, dict, bool]:
    """Process a single chunk tuple (chunk_name, start_sec, chunk_text)."""
    chunk_name, start_sec, chunk_text = item
    matched, kinds = match_chunk(chunk_text, entries, threshold)
    matched_files = [
        {"keyword": kw, "file": data["file"], "count": data["count"]}
        for kw, data in matched.items() if data.get("file")
    ]
    signal_scores = Counter([data["kind"] for data in matched.values()])

    res = {
        "start_sec": start_sec,
        "matched_keywords": matched,
        "kinds": kinds,
        "signal_score": dict(signal_scores),
        "matched_files": matched_files
    }
    return chunk_name, res, bool(matched)
```

3. Refactor chunk loop in `main()`:

```python
    workers = min(32, (os.cpu_count() or 1) + 4)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_process_single_chunk, item, entries, args.threshold) for item in chunks_list]
        for f in futures:
            chunk_name, res, matched = f.result()
            results[chunk_name] = res
            if matched:
                total_matched += 1
```

- [ ] **Step 4: Run full test suite to verify all pass**

Run: `PYTHONPATH=lib:skills/whisper-corruption-recovery/scripts:skills/anibon-timestamper/scripts:skills/creating-highlight-video/scripts .venv/bin/pytest tests/ skills/whisper-corruption-recovery/scripts/test_fix.py`  
Expected: PASS (25 passed in 0.2s)

- [ ] **Step 5: Commit changes**

```bash
git add skills/anibon-timestamper/scripts/detect_signals.py tests/test_detect_signals.py
git commit -m "feat: add hardware-adaptive multithreading to detect_signals.py"
```
