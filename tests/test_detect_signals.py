#!/usr/bin/env python3
"""Self-check for refactored detect_signals.py."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-timestamper" / "scripts"))
from detect_signals import (
    _process_single_chunk,
    load_chunk_json,
    load_chunk_xml,
    load_chunks,
    load_knowledge,
    match_chunk,
)


def test_load_knowledge(tmp_path):
    k_file = tmp_path / "knowledge.json"
    k_data = {"entries": {"FGO": {"kind": "game", "file": "fgo.md"}}}
    k_file.write_text(json.dumps(k_data), encoding="utf-8")

    result = load_knowledge(k_file)
    assert result == {"FGO": {"kind": "game", "file": "fgo.md"}}


def test_load_chunk_json(tmp_path):
    c_file = tmp_path / "chunk_001.json"
    c_data = {
        "start_sec": 15,
        "items": [{"text": "Hello"}, {"text": "World"}]
    }
    c_file.write_text(json.dumps(c_data), encoding="utf-8")

    name, start_sec, text = load_chunk_json(c_file)
    assert name == "chunk_001"
    assert start_sec == 15
    assert text == "Hello World"


def test_load_chunk_xml(tmp_path):
    c_file = tmp_path / "chunk_001.xml"
    xml_content = '<transcript start_sec="30"><item>XML</item><item>Chunk</item></transcript>'
    c_file.write_text(xml_content, encoding="utf-8")

    name, start_sec, text = load_chunk_xml(c_file)
    assert name == "chunk_001"
    assert start_sec == 30
    assert text == "XML Chunk"


def test_load_chunks(tmp_path):
    # Single JSON file
    j_file = tmp_path / "chunk_001.json"
    j_file.write_text(json.dumps({"start_sec": 10, "items": [{"text": "one"}]}), encoding="utf-8")
    chunks_single = list(load_chunks(j_file))
    assert len(chunks_single) == 1
    assert chunks_single[0] == ("chunk_001", 10, "one")

    # Directory with JSON files
    dir_path = tmp_path / "chunks"
    dir_path.mkdir()
    (dir_path / "chunk_002.json").write_text(json.dumps({"start_sec": 20, "items": [{"text": "two"}]}), encoding="utf-8")
    (dir_path / "chunk_001.json").write_text(json.dumps({"start_sec": 10, "items": [{"text": "one"}]}), encoding="utf-8")

    chunks_dir = list(load_chunks(dir_path))
    assert len(chunks_dir) == 2
    assert chunks_dir[0][0] == "chunk_001"
    assert chunks_dir[1][0] == "chunk_002"


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
