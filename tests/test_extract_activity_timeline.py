#!/usr/bin/env python3
"""Tests for extract_activity_timeline.py."""
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-stream-activity" / "scripts"))
from extract_activity_timeline import (
    format_timestamp,
    merge_frame_classifications,
    parse_vision_response_json,
)


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(65) == "00:01:05"
    assert format_timestamp(3661) == "01:01:01"


def test_merge_frame_classifications():
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
    assert len(merged) == 3

    # Segment 1: Steam Store (00:00:00 - 00:02:00)
    assert merged[0]["app_or_game"] == "Steam Store"
    assert merged[0]["start"] == "00:00:00"
    assert merged[0]["end"] == "00:02:00"
    assert "browsing sales" in merged[0]["details"]
    assert "browsing reviews" in merged[0]["details"]
    assert merged[0]["webcam"]["speaker_present"] is True

    # Segment 2: Monster Hunter Wilds Present (00:02:00 - 00:03:00)
    assert merged[1]["app_or_game"] == "Monster Hunter Wilds"
    assert merged[1]["webcam"]["speaker_present"] is True

    # Segment 3: Monster Hunter Wilds AFK (00:03:00 - 00:04:00)
    assert merged[2]["app_or_game"] == "Monster Hunter Wilds"
    assert merged[2]["webcam"]["speaker_present"] is False


def test_parse_vision_response_json():
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
    assert len(data) == 1
    assert data[0]["app_or_game"] == "Elden Ring"
    assert data[0]["webcam"]["expression"] == "shocked_facepalm"
