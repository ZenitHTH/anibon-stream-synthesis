import pytest
from anibon.vision_verify import (
    is_ambiguous,
    stamp_seconds,
    parse_verify_response,
    build_verify_prompt,
)

ORIG = "03:52:49 - [Gameplay] เซเวนกับไหมกีนิด"


def test_is_ambiguous_cases():
    assert is_ambiguous("03:51:33 - [Donation] ขอบคุณคุณนี้น่ะ")
    assert is_ambiguous("03:28:41 - [Talk] Zelda")
    assert is_ambiguous("04:00:04 - [Gameplay] ปู่บอทสู้มอนสเตอร์ในเกมแล้วไม่ไหวจนเกือบตาย")
    assert is_ambiguous("00:01:00 - [Talk] [?] มาแล้วทุกคน")
    assert not is_ambiguous("02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ")


def test_stamp_seconds():
    assert stamp_seconds("01:02:03 - [Talk] x") == 3723
    assert stamp_seconds("00:00:15 - [Greeting] เริ่มสตรีม") == 15


def test_parse_accepts_valid():
    raw = '{"corrected": "03:52:49 - [Gameplay] วิเคราะห์ฮีโร่ Seven และ McGinnis ใน Deadlock", "confidence": 0.8}'
    result = parse_verify_response(raw, ORIG)
    assert result == "03:52:49 - [Gameplay] วิเคราะห์ฮีโร่ Seven และ McGinnis ใน Deadlock"


def test_parse_rejects_non_json():
    assert parse_verify_response("I think this is Deadlock", ORIG) == ORIG


def test_parse_rejects_changed_time_or_tag():
    assert parse_verify_response('{"corrected": "03:53:00 - [Gameplay] x y z", "confidence": 0.9}', ORIG) == ORIG
    assert parse_verify_response('{"corrected": "03:52:49 - [Talk] x y z", "confidence": 0.9}', ORIG) == ORIG


def test_parse_rejects_low_confidence():
    assert parse_verify_response('{"corrected": "03:52:49 - [Gameplay] Seven", "confidence": 0.3}', ORIG) == ORIG


def test_build_verify_prompt():
    prompt = build_verify_prompt(ORIG, "context transcript")
    assert "03:52:49" in prompt
    assert "Seven" not in prompt or "McGinnis" not in prompt
    assert "JSON" in prompt
