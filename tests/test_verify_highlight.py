import sys
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))
import verify_highlight

def test_to_hhmmss():
    assert verify_highlight.to_hhmmss(0) == "00:00:00"
    assert verify_highlight.to_hhmmss(65) == "00:01:05"
    assert verify_highlight.to_hhmmss(3665) == "01:01:05"

@patch('verify_highlight.run_ffprobe')
def test_verify_highlight_pass(mock_ffprobe, tmp_path, capsys):
    mp4_path = tmp_path / "test.mp4"
    mp4_path.touch()
    
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"total_expected_duration_seconds": 120}))
    
    def ffprobe_side_effect(cmd_args):
        if "-show_format" in cmd_args:
            return {"format": {"duration": "120.5"}}
        elif "-show_streams" in cmd_args:
            return {"streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"},
                {"codec_type": "audio", "codec_name": "aac"}
            ]}
        return {}
        
    mock_ffprobe.side_effect = ffprobe_side_effect
    
    with patch('sys.argv', ['verify_highlight.py', str(mp4_path), str(plan_path)]):
        with pytest.raises(SystemExit) as e:
            verify_highlight.main()
            
    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "✅ PASS" in captured.out
    assert "Duration: 00:02:00 (expected 00:02:00) ✅" in captured.out

@patch('verify_highlight.run_ffprobe')
def test_verify_highlight_fail_duration(mock_ffprobe, tmp_path, capsys):
    mp4_path = tmp_path / "test.mp4"
    mp4_path.touch()
    
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"total_expected_duration_seconds": 120}))
    
    def ffprobe_side_effect(cmd_args):
        if "-show_format" in cmd_args:
            return {"format": {"duration": "130.5"}}
        elif "-show_streams" in cmd_args:
            return {"streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"},
                {"codec_type": "audio", "codec_name": "aac"}
            ]}
        return {}
        
    mock_ffprobe.side_effect = ffprobe_side_effect
    
    with patch('sys.argv', ['verify_highlight.py', str(mp4_path), str(plan_path)]):
        with pytest.raises(SystemExit) as e:
            verify_highlight.main()
            
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "❌ FAIL" in captured.out
    assert "diff > 5s" in captured.out

@patch('verify_highlight.run_ffprobe')
def test_verify_highlight_fail_codec(mock_ffprobe, tmp_path, capsys):
    mp4_path = tmp_path / "test.mp4"
    mp4_path.touch()
    
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"total_expected_duration_seconds": 120}))
    
    def ffprobe_side_effect(cmd_args):
        if "-show_format" in cmd_args:
            return {"format": {"duration": "120.0"}}
        elif "-show_streams" in cmd_args:
            return {"streams": [
                {"codec_type": "video", "codec_name": "hevc", "pix_fmt": "yuv420p"},
                {"codec_type": "audio", "codec_name": "mp3"}
            ]}
        return {}
        
    mock_ffprobe.side_effect = ffprobe_side_effect
    
    with patch('sys.argv', ['verify_highlight.py', str(mp4_path), str(plan_path)]):
        with pytest.raises(SystemExit) as e:
            verify_highlight.main()
            
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "❌ FAIL" in captured.out
    assert "Video: missing or wrong codec" in captured.out
    assert "Audio: missing or wrong codec" in captured.out
