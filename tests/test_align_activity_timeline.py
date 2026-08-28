#!/usr/bin/env python3
"""Tests for align_activity_timeline.py."""
import json
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-stream-activity" / "scripts"))
from align_activity_timeline import (
    align_intervals_to_chunk,
    process_all_chunks,
)


def test_align_intervals_to_chunk():
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

    # Chunk 1: 00:05:00 to 00:10:00 (300s to 600s) -> overlaps both Steam Store and MH Wilds
    text_c1 = align_intervals_to_chunk(intervals, chunk_start_sec=300, chunk_end_sec=600)
    assert "Steam Store" in text_c1
    assert "Monster Hunter Wilds" in text_c1
    assert "[Gameplay]" in text_c1

    # Chunk 2: 00:29:00 to 00:34:00 (1740s to 2040s) -> overlaps MH Wilds and AFK break
    text_c2 = align_intervals_to_chunk(intervals, chunk_start_sec=1740, chunk_end_sec=2040)
    assert "SPEAKER AWAY/AFK" in text_c2

    # Chunk 3: 01:00:00 to 01:05:00 (3600s to 3900s) -> no overlap
    text_c3 = align_intervals_to_chunk(intervals, chunk_start_sec=3600, chunk_end_sec=3900)
    assert "No specific visual activity detected" in text_c3


def test_process_all_chunks(tmp_path):
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

    # Create fake chunk XML files
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_01.xml").write_text('<transcript><text start="0.0" dur="300.0">Hello</text></transcript>', encoding="utf-8")
    (chunks_dir / "chunk_02.xml").write_text('<transcript><text start="300.0" dur="300.0">World</text></transcript>', encoding="utf-8")

    out_dir = tmp_path / "activity"
    process_all_chunks(str(timeline_file), str(chunks_dir), str(out_dir))

    assert (out_dir / "activity_chunk_01.txt").exists()
    assert (out_dir / "activity_chunk_02.txt").exists()
    c1_content = (out_dir / "activity_chunk_01.txt").read_text(encoding="utf-8")
    assert "Elden Ring" in c1_content
