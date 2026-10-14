#!/usr/bin/env python3
"""Self-check for refactored detect_signals.py."""
import json
import os
import sys
import tempfile
import unittest
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


class TestDetectSignals(unittest.TestCase):
    def test_load_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            k_file = tmp_path / "knowledge.json"
            k_data = {"entries": {"FGO": {"kind": "game", "file": "fgo.md"}}}
            k_file.write_text(json.dumps(k_data), encoding="utf-8")

            result = load_knowledge(k_file)
            self.assertEqual(result, {"FGO": {"kind": "game", "file": "fgo.md"}})

    def test_load_chunk_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            c_file = tmp_path / "chunk_001.json"
            c_data = {
                "start_sec": 15,
                "items": [{"text": "Hello"}, {"text": "World"}]
            }
            c_file.write_text(json.dumps(c_data), encoding="utf-8")

            name, start_sec, text = load_chunk_json(c_file)
            self.assertEqual(name, "chunk_001")
            self.assertEqual(start_sec, 15)
            self.assertEqual(text, "Hello World")

    def test_load_chunk_xml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            c_file = tmp_path / "chunk_001.xml"
            xml_content = '<transcript start_sec="30"><item>XML</item><item>Chunk</item></transcript>'
            c_file.write_text(xml_content, encoding="utf-8")

            name, start_sec, text = load_chunk_xml(c_file)
            self.assertEqual(name, "chunk_001")
            self.assertEqual(start_sec, 30)
            self.assertEqual(text, "XML Chunk")

    def test_load_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Single JSON file
            j_file = tmp_path / "chunk_001.json"
            j_file.write_text(json.dumps({"start_sec": 10, "items": [{"text": "one"}]}), encoding="utf-8")
            chunks_single = list(load_chunks(j_file))
            self.assertEqual(len(chunks_single), 1)
            self.assertEqual(chunks_single[0], ("chunk_001", 10, "one"))

            # Directory with JSON files
            dir_path = tmp_path / "chunks"
            dir_path.mkdir()
            (dir_path / "chunk_002.json").write_text(json.dumps({"start_sec": 20, "items": [{"text": "two"}]}), encoding="utf-8")
            (dir_path / "chunk_001.json").write_text(json.dumps({"start_sec": 10, "items": [{"text": "one"}]}), encoding="utf-8")

            chunks_dir = list(load_chunks(dir_path))
            self.assertEqual(len(chunks_dir), 2)
            self.assertEqual(chunks_dir[0][0], "chunk_001")
            self.assertEqual(chunks_dir[1][0], "chunk_002")

    def test_match_chunk_finds_keywords(self):
        entries = {
            "FGO": {"kind": "game", "file": "fgo-knowledge.md"},
            "Fate": {"kind": "game", "file": "fgo-knowledge.md"},
            "Unknown": {"kind": "other", "file": "other.md"},
        }
        matched, kinds = match_chunk("วันนี้พูดเรื่อง FGO กับ Fate ครับ", entries, threshold=1)
        self.assertTrue("FGO" in matched and "Fate" in matched)
        self.assertNotIn("Unknown", matched)
        self.assertEqual(kinds, ["game"])

    def test_match_chunk_threshold(self):
        entries = {
            "FGO": {"kind": "game", "file": "fgo-knowledge.md"},
            "Fate": {"kind": "game", "file": "fgo-knowledge.md"},
        }
        matched, _ = match_chunk("FGO FGO Fate", entries, threshold=2)
        self.assertIn("FGO", matched)
        self.assertNotIn("Fate", matched)

    def test_process_single_chunk(self):
        entries = {"FGO": {"kind": "game", "file": "fgo.md"}}
        item = ("chunk_001", 10, "พูดถึง FGO ครับ")
        name, res, matched = _process_single_chunk(item, entries, {"FGO": 1}, 1, 1)
        self.assertEqual(name, "chunk_001")
        self.assertEqual(res["start_sec"], 10)
        self.assertIn("FGO", res["matched_keywords"])
        self.assertTrue(matched)

    def test_multithreaded_execution(self):
        entries = {"FGO": {"kind": "game", "file": "fgo.md"}}
        items = [("chunk_01", 0, "FGO"), ("chunk_02", 10, "nothing")]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda it: _process_single_chunk(it, entries, {"FGO": 1}, 2, 1), items))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], "chunk_01")
        self.assertTrue(results[0][2])
        self.assertEqual(results[1][0], "chunk_02")
        self.assertFalse(results[1][2])


if __name__ == "__main__":
    unittest.main()
