# tests/test_fix_hallucinations.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from fix_hallucinations import is_hallucinated


def test_detects_character_cramming():
    text = "ขอบคุณอ" * 30
    assert is_hallucinated(text) is True


def test_detects_syllable_loop():
    text = "สูง" * 40
    assert is_hallucinated(text) is True


def test_detects_laugh_loop():
    text = "ฮะ" * 50
    assert is_hallucinated(text) is True


def test_ignores_normal_filler():
    text = "ก็ไม่รู้นะ ก็แบบ ก็เหมือนกัน ก็คงจะดีนะครับ"
    assert is_hallucinated(text) is False


def test_ignores_short_text():
    text = "สูง"
    assert is_hallucinated(text) is False


def test_custom_threshold():
    # "ก็" *5 = 10 chars, suffix = 20 chars → total 30 chars
    # n-gram "ก็": 5*2/30 = 0.33 → NOT flagged at 0.4 (0.33 < 0.4), flagged at 0.2 (0.33 > 0.2)
    text = "ก็" * 5 + "ไม่รู้นะครับมากเลยอ่ะ"
    assert is_hallucinated(text, threshold=0.4) is False
    assert is_hallucinated(text, threshold=0.2) is True


# --- Task 2 tests ---

import tempfile
import os


def test_ffmpeg_cut_creates_file():
    from fix_hallucinations import ffmpeg_cut
    audio = Path.home() / "youtube_i7oPp2RmfSg_workspace/audio.wav"
    if not audio.exists():
        import pytest; pytest.skip("audio.wav not present")
    out = ffmpeg_cut(audio, start_ms=0, end_ms=3000)
    assert out.exists()
    assert out.stat().st_size > 1000
    out.unlink()


def test_run_whisper_returns_list():
    from fix_hallucinations import ffmpeg_cut, run_whisper_on_slice, MODEL_PATH
    audio = Path.home() / "youtube_i7oPp2RmfSg_workspace/audio.wav"
    if not audio.exists():
        import pytest; pytest.skip("audio.wav not present")
    slc = ffmpeg_cut(audio, start_ms=0, end_ms=5000)
    result = run_whisper_on_slice(slc, MODEL_PATH, temperature=0.2)
    assert isinstance(result, list)
    slc.unlink(missing_ok=True)


# --- Task 3 tests ---

def test_detect_and_recover_replaces_hallucinated():
    from fix_hallucinations import detect_and_recover
    items = [
        {"text": "สวัสดีครับ", "start": 0.0, "duration": 2.0, "timestamp": "00:00:00"},
        {"text": "สูง" * 50, "start": 2.0, "duration": 30.0, "timestamp": "00:00:02"},
        {"text": "ขอบคุณมาก", "start": 32.0, "duration": 2.0, "timestamp": "00:00:32"},
    ]
    audio = Path.home() / "youtube_i7oPp2RmfSg_workspace/audio.wav"
    if not audio.exists():
        import pytest; pytest.skip("audio.wav not present")
    result = detect_and_recover(items, audio)
    for item in result:
        assert ("สูง" * 10) not in item["text"]
    texts = [i["text"] for i in result]
    assert any("สวัสดีครับ" in t for t in texts)
    assert any("ขอบคุณมาก" in t for t in texts)
    starts = [i["start"] for i in result]
    assert starts == sorted(starts)


def test_detect_and_recover_passthrough_clean():
    from fix_hallucinations import detect_and_recover
    items = [
        {"text": "สวัสดีครับ", "start": 0.0, "duration": 2.0, "timestamp": "00:00:00"},
        {"text": "วันนี้เราจะพูดถึงรางวัล", "start": 2.5, "duration": 3.0, "timestamp": "00:00:02"},
    ]
    result = detect_and_recover(items, Path("/nonexistent.wav"))
    assert len(result) == 2


# --- Task 4 tests ---

import subprocess as sp


def test_cli_help():
    result = sp.run(
        ["python3", "scripts/fix_hallucinations.py", "--help"],
        cwd=str(Path(__file__).parent.parent),
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "whisper_json" in result.stdout or "whisper_json" in result.stderr
