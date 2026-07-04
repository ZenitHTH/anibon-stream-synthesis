import pytest
import sys

sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts")
from assemble_timestamps import assemble_logic

def test_assemble_logic():
    lines = [
        "00:00:00 - [Talk] Start",
        "00:05:00 - [Game] Play",
        "00:05:00 - [Game] Play updated",
        "00:10:00 - [End] Stop"
    ]
    topics = [
        {"start": "00:00:00", "title": "Intro", "summary": "Start", "topic": "Gen"}
    ]
    # Set an artificially low limit to force splitting
    result_lines = assemble_logic(lines, topics, limit_bytes=50, max_chunk_bytes=40)
    
    joined = "\n".join(result_lines)
    assert "📌 ส่วนที่ 1" in joined
    assert "📌 ส่วนที่ 2" in joined
    assert "Play updated" in joined
    assert "00:05:00 - [Game] Play\n" not in joined + "\n"
