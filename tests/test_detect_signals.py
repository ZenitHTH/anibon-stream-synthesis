#!/usr/bin/env python3
"""Self-check for refactored detect_signals.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-timestamper" / "scripts"))
from detect_signals import _process_single_chunk, match_chunk, load_knowledge
from concurrent.futures import ThreadPoolExecutor

def test_match_chunk_finds_keywords():
    entries = {
        "FGO": {"kind": "game", "file": "fgo-knowledge.md"},
        "Fate": {"kind": "game", "file": "fgo-knowledge.md"},
        "Unknown": {"kind": "other", "file": "other.md"},
    }
    matched, kinds = match_chunk("วันนี้พูดเรื่อง FGO กับ Fate ครับ", entries, threshold=1)
    assert "FGO" in matched and "Fate" in matched
    assert "Unknown" not in matched
    assert kinds == ["game"]

def test_match_chunk_threshold():
    entries = {
        "FGO": {"kind": "game", "file": "fgo-knowledge.md"},
        "Fate": {"kind": "game", "file": "fgo-knowledge.md"},
    }
    matched, _ = match_chunk("FGO FGO Fate", entries, threshold=2)
    assert "FGO" in matched
    assert "Fate" not in matched

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



