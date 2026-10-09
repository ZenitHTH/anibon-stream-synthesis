import json
import pytest
from pathlib import Path

def test_detect_youtube_auto_transcript_by_json3(tmp_path):
    from anibon.transcript_source import detect_transcript_source, is_youtube_auto_transcript
    
    (tmp_path / "raw_transcript.th.json3").write_text("{}", encoding="utf-8")
    assert detect_transcript_source(tmp_path) == "youtube-auto"
    assert is_youtube_auto_transcript(tmp_path) is True

def test_detect_youtube_auto_transcript_by_wiremagic(tmp_path):
    from anibon.transcript_source import detect_transcript_source, is_youtube_auto_transcript
    
    (tmp_path / "raw_transcript.json").write_text('{"wireMagic": "pb3", "events": []}', encoding="utf-8")
    assert detect_transcript_source(tmp_path) == "youtube-auto"
    assert is_youtube_auto_transcript(tmp_path) is True

def test_detect_whisper_source(tmp_path):
    from anibon.transcript_source import detect_transcript_source, is_youtube_auto_transcript
    
    (tmp_path / "whisper_output.json").write_text('[]', encoding="utf-8")
    assert detect_transcript_source(tmp_path) == "whisper"
    assert is_youtube_auto_transcript(tmp_path) is False

def test_detect_whisper_by_audio_recovery(tmp_path):
    from anibon.transcript_source import detect_transcript_source, is_youtube_auto_transcript
    
    (tmp_path / "audio_recovered.json").write_text('[]', encoding="utf-8")
    assert detect_transcript_source(tmp_path) == "whisper"
    assert is_youtube_auto_transcript(tmp_path) is False

def test_detect_source_by_info_json(tmp_path):
    from anibon.transcript_source import detect_transcript_source, is_youtube_auto_transcript
    
    (tmp_path / "info.json").write_text(json.dumps({"transcript_source": "whisper"}), encoding="utf-8")
    assert detect_transcript_source(tmp_path) == "whisper"
    assert is_youtube_auto_transcript(tmp_path) is False
