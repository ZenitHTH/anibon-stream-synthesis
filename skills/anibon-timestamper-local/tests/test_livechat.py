"""Unit tests for livechat system integration in anibon-timestamper-local."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from interface import (
    align_livechat_feed,
    has_aligned_livechat,
    load_chunk_livechat,
    load_chunk_mood,
    run_parity_gates,
)
from align_live_chat import align, load_chunk_windows, load_events, slice_events


class TestLiveChatIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.chunks_dir = self.ws / "chunks"
        self.chunks_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_chunk_windows_supports_txt_format(self):
        (self.chunks_dir / "chunk_00.txt").write_text("00:00:00–00:05:00\nHello world", encoding="utf-8")
        (self.chunks_dir / "chunk_01.txt").write_text("00:05:00–00:10:00\nSecond chunk", encoding="utf-8")
        windows = load_chunk_windows(self.chunks_dir)
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0], ("chunk_00", 0, 300))
        self.assertEqual(windows[1], ("chunk_01", 300, 600))

    def test_align_creates_per_chunk_files_and_index(self):
        (self.chunks_dir / "chunk_00.txt").write_text("00:00:00–00:05:00\nHello", encoding="utf-8")
        (self.chunks_dir / "chunk_01.txt").write_text("00:05:00–00:10:00\nWorld", encoding="utf-8")
        events_file = self.ws / "livechat_events.txt"
        events_file.write_text(
            "10\t[00:00:10] UserA: First comment\n"
            "299\t[00:04:59] UserB: 555555\n"
            "305\t[00:05:05] UserC: SUPERCHAT (THB 100)\n",
            encoding="utf-8",
        )
        out_dir = self.ws / "livechat"
        align(events_file, self.chunks_dir, out_dir)

        self.assertTrue((out_dir / "livechat_chunk_00.txt").is_file())
        self.assertTrue((out_dir / "livechat_chunk_01.txt").is_file())
        self.assertTrue((out_dir / "livechat_index.json").is_file())

        c0 = (out_dir / "livechat_chunk_00.txt").read_text(encoding="utf-8")
        self.assertIn("UserA", c0)
        self.assertIn("UserB", c0)

        c1 = (out_dir / "livechat_chunk_01.txt").read_text(encoding="utf-8")
        self.assertIn("SUPERCHAT", c1)

    def test_load_chunk_livechat_extracts_high_value(self):
        lc_dir = self.ws / "livechat"
        lc_dir.mkdir(parents=True)
        (lc_dir / "livechat_chunk_00.txt").write_text(
            "Regular chat 1\n"
            "Regular chat 2\n"
            "💰 SUPERCHAT (THB 500) from VIP: Hype!\n"
            "User: ปู่ เล่นเกมอะไรต่อครับ?\n",
            encoding="utf-8",
        )
        snippet = load_chunk_livechat(self.ws, "chunk_00", max_lines=2)
        self.assertIn("SUPERCHAT", snippet)
        self.assertIn("ปู่ เล่นเกมอะไรต่อครับ?", snippet)

    def test_has_aligned_livechat(self):
        self.assertFalse(has_aligned_livechat(self.ws))
        lc_dir = self.ws / "livechat"
        lc_dir.mkdir(parents=True)
        (lc_dir / "livechat_index.json").write_text("{}", encoding="utf-8")
        self.assertTrue(has_aligned_livechat(self.ws))


if __name__ == "__main__":
    unittest.main()
