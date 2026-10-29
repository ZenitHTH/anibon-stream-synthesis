# tests/test_music_anchors.py
from __future__ import annotations

import unittest
from process.signals.detector import extract_and_clean_music_anchors

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


if __name__ == "__main__":
    unittest.main()
