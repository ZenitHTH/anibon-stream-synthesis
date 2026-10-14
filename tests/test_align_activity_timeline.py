#!/usr/bin/env python3
"""Tests for align_activity_timeline.py."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-stream-activity" / "scripts"))
from align_activity_timeline import (
    align_intervals_to_chunk,
    process_all_chunks,
)


class TestAlignActivityTimeline(unittest.TestCase):
    def test_align_intervals_to_chunk(self):
        intervals = [
            {
                "start": "00:00:00",
                "end": "00:07:00",
                "start_sec": 0,
                "end_sec": 420,
                "app_or_game": "Steam Store",
                "category": "Web Browsing",
                "details": "looking at sales",
                "webcam": {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"},
            },
            {
                "start": "00:07:00",
                "end": "00:30:00",
                "start_sec": 420,
                "end_sec": 1800,
                "app_or_game": "Monster Hunter Wilds",
                "category": "Gameplay",
                "details": "hunting monsters",
                "webcam": {"speaker_present": True, "expression": "focused", "layout": "corner_cam"},
            },
            {
                "start": "00:30:00",
                "end": "00:35:00",
                "start_sec": 1800,
                "end_sec": 2100,
                "app_or_game": "Monster Hunter Wilds",
                "category": "Gameplay",
                "details": "AFK break",
                "webcam": {"speaker_present": False, "expression": "away", "layout": "corner_cam"},
            },
        ]

        text_c1 = align_intervals_to_chunk(intervals, chunk_start_sec=300, chunk_end_sec=600)
        self.assertIn("Steam Store", text_c1)
        self.assertIn("Monster Hunter Wilds", text_c1)
        self.assertIn("[Gameplay]", text_c1)

        text_c2 = align_intervals_to_chunk(intervals, chunk_start_sec=1740, chunk_end_sec=2040)
        self.assertIn("SPEAKER AWAY/AFK", text_c2)

        text_c3 = align_intervals_to_chunk(intervals, chunk_start_sec=3600, chunk_end_sec=3900)
        self.assertIn("No specific visual activity detected", text_c3)

    def test_process_all_chunks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            intervals = [
                {
                    "start": "00:00:00",
                    "end": "00:10:00",
                    "start_sec": 0,
                    "end_sec": 600,
                    "app_or_game": "Elden Ring",
                    "category": "Gameplay",
                    "details": "Boss fight",
                    "webcam": {"speaker_present": True, "expression": "shocked_facepalm", "layout": "corner_cam"},
                }
            ]
            timeline_file = tmp_path / "activity_timeline.json"
            timeline_file.write_text(json.dumps(intervals), encoding="utf-8")

            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_01.xml").write_text('<transcript><text start="0.0" dur="300.0">Hello</text></transcript>', encoding="utf-8")
            (chunks_dir / "chunk_02.xml").write_text('<transcript><text start="300.0" dur="300.0">World</text></transcript>', encoding="utf-8")

            out_dir = tmp_path / "activity"
            process_all_chunks(str(timeline_file), str(chunks_dir), str(out_dir))

            self.assertTrue((out_dir / "activity_chunk_01.txt").exists())
            self.assertTrue((out_dir / "activity_chunk_02.txt").exists())
            c1_content = (out_dir / "activity_chunk_01.txt").read_text(encoding="utf-8")
            self.assertIn("Elden Ring", c1_content)


if __name__ == "__main__":
    unittest.main()
