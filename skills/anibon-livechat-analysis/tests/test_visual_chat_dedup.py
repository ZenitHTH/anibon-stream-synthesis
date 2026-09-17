import pytest
from skills.anibon_livechat_analysis.scripts.visual_chat_dedup import (
    sec_to_hhmmss,
    format_raw_event,
    deduplicate_frames_messages,
)


def test_sec_to_hhmmss():
    assert sec_to_hhmmss(0) == "00:00:00"
    assert sec_to_hhmmss(65) == "00:01:05"
    assert sec_to_hhmmss(3665) == "01:01:05"
    assert sec_to_hhmmss(7325) == "02:02:05"


def test_format_raw_event_normal():
    line = format_raw_event(605, "@user1", "ปู่เล่นตู้ไหน :_Nerd:")
    assert line == "605\t[00:10:05] @user1: ปู่เล่นตู้ไหน :_Nerd:"


def test_format_raw_event_superchat():
    line = format_raw_event(610, "@user2", "เป็นกำลังใจให้ครับ", superchat="THB 100.00")
    assert line == "610\t[00:10:10] 💰 SUPERCHAT (THB 100.00) from @user2: เป็นกำลังใจให้ครับ"


def test_deduplicate_frames_messages():
    frames = [
        {
            "sec": 600,
            "messages": [
                {"author": "@user1", "text": "ฮัลโหล", "superchat": None},
                {"author": "@user2", "text": "555", "superchat": None},
            ],
        },
        {
            "sec": 604,
            "messages": [
                # user2 message scrolled up
                {"author": "@user2", "text": "555", "superchat": None},
                {"author": "@user3", "text": ":_CunnyBoat:", "superchat": None},
            ],
        },
    ]
    events = deduplicate_frames_messages(frames)
    assert len(events) == 3
    assert events[0] == (600, "600\t[00:10:00] @user1: ฮัลโหล")
    assert events[1] == (600, "600\t[00:10:00] @user2: 555")
    assert events[2] == (604, "604\t[00:10:04] @user3: :_CunnyBoat:")


def test_deduplicate_empty_and_whitespace():
    frames = [
        {
            "sec": 100,
            "messages": [
                {"author": "", "text": "no author"},
                {"author": "   ", "text": "blank author"},
                {"author": "@user1", "text": ""},
                {"author": "@user2", "text": "   "},
                {"author": " @User3 ", "text": "  valid message  "},
            ],
        }
    ]
    events = deduplicate_frames_messages(frames)
    assert len(events) == 1
    assert events[0] == (100, "100\t[00:01:40] @User3: valid message")


def test_deduplicate_superchat():
    frames = [
        {
            "sec": 200,
            "messages": [
                {"author": "@donor", "text": "รักปู่ครับ", "superchat": "THB 500.00"},
            ],
        },
        {
            "sec": 204,
            "messages": [
                {"author": "@donor", "text": "รักปู่ครับ", "superchat": "THB 500.00"},
            ],
        },
    ]
    events = deduplicate_frames_messages(frames)
    assert len(events) == 1
    assert events[0] == (200, "200\t[00:03:20] 💰 SUPERCHAT (THB 500.00) from @donor: รักปู่ครับ")
