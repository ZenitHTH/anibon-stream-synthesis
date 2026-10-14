import sys
import unittest
from pathlib import Path

_test_dir = Path(__file__).resolve().parent
if str(_test_dir) not in sys.path:
    sys.path.insert(0, str(_test_dir))
import conftest  # noqa: F401

from skills.anibon_livechat_analysis.scripts.visual_chat_dedup import (
    sec_to_hhmmss,
    format_raw_event,
    deduplicate_frames_messages,
)


class TestVisualChatDedup(unittest.TestCase):
    def test_sec_to_hhmmss(self):
        self.assertEqual(sec_to_hhmmss(0), "00:00:00")
        self.assertEqual(sec_to_hhmmss(65), "00:01:05")
        self.assertEqual(sec_to_hhmmss(3665), "01:01:05")
        self.assertEqual(sec_to_hhmmss(7325), "02:02:05")

    def test_format_raw_event_normal(self):
        line = format_raw_event(605, "@user1", "ปู่เล่นตู้ไหน :_Nerd:")
        self.assertEqual(line, "605\t[00:10:05] @user1: ปู่เล่นตู้ไหน :_Nerd:")

    def test_format_raw_event_superchat(self):
        line = format_raw_event(610, "@user2", "เป็นกำลังใจให้ครับ", superchat="THB 100.00")
        self.assertEqual(line, "610\t[00:10:10] 💰 SUPERCHAT (THB 100.00) from @user2: เป็นกำลังใจให้ครับ")

    def test_deduplicate_frames_messages(self):
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
                    {"author": "@user2", "text": "555", "superchat": None},
                    {"author": "@user3", "text": ":_CunnyBoat:", "superchat": None},
                ],
            },
        ]
        events = deduplicate_frames_messages(frames)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0], (600, "600\t[00:10:00] @user1: ฮัลโหล"))
        self.assertEqual(events[1], (600, "600\t[00:10:00] @user2: 555"))
        self.assertEqual(events[2], (604, "604\t[00:10:04] @user3: :_CunnyBoat:"))

    def test_deduplicate_empty_and_whitespace(self):
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
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], (100, "100\t[00:01:40] @User3: valid message"))

    def test_deduplicate_superchat(self):
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
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], (200, "200\t[00:03:20] 💰 SUPERCHAT (THB 500.00) from @donor: รักปู่ครับ"))

    def test_deduplicate_sliding_window_60s(self):
        frames = [
            {
                "sec": 10,
                "messages": [
                    {"author": "@user1", "text": "555"},
                ],
            },
            {
                "sec": 50,  # 50 - 10 = 40 <= 60 -> suppressed
                "messages": [
                    {"author": "@user1", "text": "555"},
                ],
            },
            {
                "sec": 75,  # 75 - 10 = 65 > 60 -> allowed again
                "messages": [
                    {"author": "@user1", "text": "555"},
                    {"author": "@user2", "text": "GG"},
                ],
            },
            {
                "sec": 100,  # 100 - 75 = 25 <= 60 -> suppressed
                "messages": [
                    {"author": "@user1", "text": "555"},
                ],
            },
        ]
        # Default / None: global set deduplication (only first occurrence)
        global_events = deduplicate_frames_messages(frames, window_sec=None)
        self.assertEqual(len(global_events), 2)
        self.assertEqual(global_events[0], (10, "10\t[00:00:10] @user1: 555"))
        self.assertEqual(global_events[1], (75, "75\t[00:01:15] @user2: GG"))

        # window_sec=60: allows repeat after 60s
        window_events = deduplicate_frames_messages(frames, window_sec=60)
        self.assertEqual(len(window_events), 3)
        self.assertEqual(window_events[0], (10, "10\t[00:00:10] @user1: 555"))
        self.assertEqual(window_events[1], (75, "75\t[00:01:15] @user1: 555"))
        self.assertEqual(window_events[2], (75, "75\t[00:01:15] @user2: GG"))


if __name__ == "__main__":
    unittest.main()
