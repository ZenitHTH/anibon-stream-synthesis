import pytest
from anibon.vision_verify import (
    is_ambiguous,
    stamp_seconds,
    parse_verify_response,
    build_verify_prompt,
    extract_frame,
    verify_ambiguous_stamps,
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


def test_verify_corrects_only_ambiguous(tmp_path):
    calls = []

    def fake_call(e, m, p, img, **k):
        calls.append(img)
        return '{"corrected": "03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock", "confidence": 0.9}'

    def fake_frame(v, s, o):
        o.write_bytes(b"image")
        return o

    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    stamps = [
        "02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ",
        ORIG,
    ]
    out = verify_ambiguous_stamps(
        stamps,
        tmp_path,
        video,
        "http://mock",
        "mock-model",
        call_fn=fake_call,
        frame_fn=fake_frame,
    )
    assert out[0] == stamps[0]
    assert "McGinnis" in out[1]
    assert len(calls) == 1


def test_verify_skips_without_video(tmp_path):
    out = verify_ambiguous_stamps(
        [ORIG],
        tmp_path,
        tmp_path / "missing.mp4",
        "http://mock",
        "mock-model",
    )
    assert out == [ORIG]


def test_verify_keeps_original_on_exception(tmp_path):
    def boom(*a, **k):
        raise OSError("down")

    def fake_frame(v, s, o):
        o.write_bytes(b"image")
        return o

    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    out = verify_ambiguous_stamps(
        [ORIG],
        tmp_path,
        video,
        "http://mock",
        "mock-model",
        call_fn=boom,
        frame_fn=fake_frame,
    )
    assert out == [ORIG]


def test_verify_uses_cache(tmp_path):
    calls = []

    def fake_call(e, m, p, img, **k):
        calls.append(img)
        return '{"corrected": "03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock", "confidence": 0.9}'

    def fake_frame(v, s, o):
        o.write_bytes(b"image")
        return o

    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    stamps = [ORIG]

    # First run
    out1 = verify_ambiguous_stamps(
        stamps,
        tmp_path,
        video,
        "http://mock",
        "mock-model",
        call_fn=fake_call,
        frame_fn=fake_frame,
    )
    assert len(calls) == 1
    assert "Seven" in out1[0]

    # Second run should read cache and not call model again
    def boom(*a, **k):
        raise RuntimeError("Should not be called")

    out2 = verify_ambiguous_stamps(
        stamps,
        tmp_path,
        video,
        "http://mock",
        "mock-model",
        call_fn=boom,
        frame_fn=fake_frame,
    )
    assert out2 == out1
    assert len(calls) == 1
