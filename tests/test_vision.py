import sys, os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import _vision

def test_keywords_filter():
    # Test that the keywords correctly match target Thai and English terms
    test_items = [
        {"text": "สวัสดีครับวันนี้มาเล่นเกม", "start": 0, "timestamp": "00:00:00"},
        {"text": "คนนี้แหละที่เราจะพูดถึง", "start": 10, "timestamp": "00:00:10"},
        {"text": "who is this character on screen?", "start": 20, "timestamp": "00:00:20"},
        {"text": "ไม่มีคีย์เวิร์ดเลยนะ", "start": 30, "timestamp": "00:00:30"}
    ]
    
    import re
    patterns = [re.compile(p, re.I) for p in _vision.KEYWORDS]
    
    matched = []
    for item in test_items:
        if any(p.search(item["text"]) for p in patterns):
            matched.append(item)
            
    assert len(matched) == 2
    assert matched[0]["start"] == 10
    assert matched[1]["start"] == 20

@patch("subprocess.run")
def test_get_stream_url(mock_run):
    mock_proc = MagicMock()
    mock_proc.stdout = "https://manifest.googlevideo.com/api/..."
    mock_proc.returncode = 0
    mock_run.return_value = mock_proc
    
    url = _vision.get_stream_url("https://youtube.com/watch?v=123")
    assert url == "https://manifest.googlevideo.com/api/..."
    mock_run.assert_called_once()
