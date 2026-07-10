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
def test_download_reference_video(mock_run, tmp_path):
    # Setup mock
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_run.return_value = mock_proc
    
    # Test successful download
    result = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
    
    # Assertions
    assert result == tmp_path / "reference_video.mp4"
    mock_run.assert_called_once()
    
    # Test skipping download if file exists
    (tmp_path / "reference_video.mp4").touch()
    mock_run.reset_mock()
    result_existing = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
    assert result_existing == tmp_path / "reference_video.mp4"
    mock_run.assert_not_called()

@patch("subprocess.run")
def test_extract_frame_timeout(mock_run, tmp_path):
    import subprocess
    # Setup mock to raise TimeoutExpired
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15)
    
    video_path = tmp_path / "reference_video.mp4"
    out_path = tmp_path / "frame.jpg"
    
    result = _vision.extract_frame(video_path, 10.5, out_path)
    
    # It should catch the timeout and return False
    assert result is False
    mock_run.assert_called_once()
