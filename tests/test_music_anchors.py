# tests/test_music_anchors.py
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_ROOT = Path(__file__).resolve().parent.parent
_LIB = str(_ROOT / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from process.signals.detector import extract_and_clean_music_anchors
from scripts.prepare_video import chunk_transcript

class TestMusicAnchors(unittest.TestCase):
    def test_extract_music_brackets_preserves_anchor(self):
        raw = "สวัสดีครับ [เพลง] วันนี้มาเล่นเกม ♪ เพลงเพราะมาก"
        clean, anchors = extract_and_clean_music_anchors(raw, offset_ms=10000)
        self.assertNotIn("[เพลง]", clean)
        self.assertNotIn("♪", clean)
        self.assertEqual(len(anchors), 2)
        self.assertEqual(anchors[0]["symbol"], "[เพลง]")
        self.assertEqual(anchors[0]["offset_ms"], 10000)
        self.assertEqual(anchors[1]["symbol"], "♪")

    def test_chunk_transcript_extracts_and_saves_music_anchors(self):
        with TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            raw = [
                {"start": 10.0, "duration": 5.0, "timestamp": "00:00:10", "text": "สวัสดีครับ [เพลง] วันนี้เล่นเกม"},
                {"start": 20.0, "duration": 5.0, "timestamp": "00:00:20", "text": "♪ เพลงเพราะจัง"},
            ]
            (ws / "raw_transcript.json").write_text(json.dumps(raw), encoding="utf-8")
            n = chunk_transcript(ws, block=300, overlap=30, fmt="txt")
            self.assertGreater(n, 0)
            anchors_file = ws / "music_anchors.json"
            self.assertTrue(anchors_file.exists())
            anchors = json.loads(anchors_file.read_text(encoding="utf-8"))
            self.assertEqual(len(anchors), 2)
            chunk_text = (ws / "chunks" / "chunk_00.txt").read_text(encoding="utf-8")
            self.assertNotIn("[เพลง]", chunk_text)
            self.assertNotIn("♪", chunk_text)


if __name__ == "__main__":
    unittest.main()
