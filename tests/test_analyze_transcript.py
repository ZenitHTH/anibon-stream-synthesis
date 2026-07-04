import pytest
import sys
from pathlib import Path

# Dynamically resolve path to scripts directory
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "anibon-timestamper" / "scripts"))
from analyze_transcript import analyze_logic

def test_analyze_logic():
    events = [
        {"start": 10, "timestamp": "00:00:10", "text": "Playing some fate grand order today."},
        {"start": 30, "timestamp": "00:00:30", "text": "Let's roll for genshin."}
    ]
    keywords = {"Fate": ["fate", "fgo"], "Genshin": ["genshin"]}
    
    results = analyze_logic(events, keywords, window=60)
    assert len(results) == 1
    assert results[0]["Time"] == "00:00:10"
    assert results[0]["Fate"] == 1
    assert results[0]["Genshin"] == 1
