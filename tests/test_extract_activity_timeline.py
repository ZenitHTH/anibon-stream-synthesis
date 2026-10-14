#!/usr/bin/env python3
"""Tests for extract_activity_timeline.py."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-stream-activity" / "scripts"))
from extract_activity_timeline import (
    format_timestamp,
    merge_frame_classifications,
    parse_vision_response_json,
)


class TestExtractActivityTimeline(unittest.TestCase):
    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00:00")
        self.assertEqual(format_timestamp(65), "00:01:05")
        self.assertEqual(format_timestamp(3661), "01:01:01")

    def test_merge_frame_classifications(self):
        raw_frames = [
            {
                "sec": 0,
                "timestamp": "00:00:00",
                "app_or_game": "Steam Store",
                "category": "Web Browsing",
                "state": "browsing sales",
                "webcam": {"speaker_present": True, "expression": "neutral", "layout": "corner_cam"},
            },
            {
                "sec": 60,
                "timestamp": "00:01:00",
                "app_or_game": "Steam Store",
                "category": "Web Browsing",
                "state": "browsing reviews",
                "webcam": {"speaker_present": True, "expression": "laughing", "layout": "corner_cam"},
            },
            {
                "sec": 120,
                "timestamp": "00:02:00",
                "app_or_game": "Monster Hunter Wilds",
                "category": "Gameplay",
                "state": "hunting",
                "webcam": {"speaker_present": True, "expression": "focused", "layout": "corner_cam"},
            },
            {
                "sec": 180,
                "timestamp": "00:03:00",
                "app_or_game": "Monster Hunter Wilds",
                "category": "Gameplay",
                "state": "hunting",
                "webcam": {"speaker_present": False, "expression": "away", "layout": "corner_cam"},
            },
        ]

        merged = merge_frame_classifications(raw_frames, step_sec=60)
        self.assertEqual(len(merged), 3)

        # Segment 1: Steam Store (00:00:00 - 00:02:00)
        self.assertEqual(merged[0]["app_or_game"], "Steam Store")
        self.assertEqual(merged[0]["start"], "00:00:00")
        self.assertEqual(merged[0]["end"], "00:02:00")
        self.assertIn("browsing sales", merged[0]["details"])
        self.assertIn("browsing reviews", merged[0]["details"])
        self.assertTrue(merged[0]["webcam"]["speaker_present"])

        # Segment 2: Monster Hunter Wilds Present (00:02:00 - 00:03:00)
        self.assertEqual(merged[1]["app_or_game"], "Monster Hunter Wilds")
        self.assertTrue(merged[1]["webcam"]["speaker_present"])

        # Segment 3: Monster Hunter Wilds AFK (00:03:00 - 00:04:00)
        self.assertEqual(merged[2]["app_or_game"], "Monster Hunter Wilds")
        self.assertFalse(merged[2]["webcam"]["speaker_present"])

    def test_parse_vision_response_json(self):
        text_with_fences = """```json
        [
          {
            "timestamp": "00:01:00",
            "app_or_game": "Elden Ring",
            "category": "Gameplay",
            "state": "Boss fight Malenia",
            "on_screen_text": "YOU DIED",
            "webcam": {
              "speaker_present": true,
              "expression": "shocked_facepalm",
              "layout": "corner_cam"
            }
          }
        ]
        ```"""
        data = parse_vision_response_json(text_with_fences)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["app_or_game"], "Elden Ring")
        self.assertEqual(data[0]["webcam"]["expression"], "shocked_facepalm")

    def test_merge_frame_classifications_none_webcam_and_expressions(self):
        raw_frames = [
            {
                "sec": 0,
                "timestamp": "00:00:00",
                "app_or_game": "Genshin Impact",
                "category": "Gameplay",
                "state": "exploring",
                "webcam": None,
            },
            {
                "sec": 60,
                "timestamp": "00:01:00",
                "app_or_game": "Genshin Impact",
                "category": "Gameplay",
                "state": "boss fight",
                "webcam": {"speaker_present": True, "expression": "shocked_facepalm", "layout": "corner_cam"},
            },
        ]

        merged = merge_frame_classifications(raw_frames, step_sec=60)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["app_or_game"], "Genshin Impact")
        self.assertTrue(merged[0]["webcam"]["speaker_present"])
        self.assertEqual(merged[0]["webcam"]["expression"], "shocked_facepalm")
        self.assertIn("shocked_facepalm", merged[0]["expressions"])


if __name__ == "__main__":
    unittest.main()
