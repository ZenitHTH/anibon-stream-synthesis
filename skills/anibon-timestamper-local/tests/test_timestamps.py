import unittest
import re
from anibon.timestamps import (
    TAGS,
    TAG_REMAP,
    normalize_tag,
    sanitize_timestamp_line,
    parse_timestamps,
    validate_timestamps,
    is_continuation,
)


class TestTimestamps(unittest.TestCase):

    def test_normalize_tag(self):
        m = re.search(r"\[([^\]]+)\]", "[วิเคราะห์]")
        self.assertEqual(normalize_tag(m), "[Talk]")

        m2 = re.search(r"\[([^\]]+)\]", "[Gameplay]")
        self.assertEqual(normalize_tag(m2), "[Gameplay]")

    def test_sanitize_timestamp_line(self):
        line1 = "00:01:23 - [วิเคราะห์] วิเคราะห์แพตช์ใหม่ - 12 words"
        self.assertEqual(sanitize_timestamp_line(line1), "00:01:23 - [Talk] วิเคราะห์แพตช์ใหม่")

        line2 = "`00:05:00 - [Gacha] เปิดกาชาตัวใหม่ (Note: lucky pull)`"
        self.assertEqual(sanitize_timestamp_line(line2), "00:05:00 - [Gacha] เปิดกาชาตัวใหม่")

        line3 = "00:10:00 - [Talk] บ่นเรื่องราคาการ์ด. Wait, check price"
        self.assertEqual(sanitize_timestamp_line(line3), "00:10:00 - [Talk] บ่นเรื่องราคาการ์ด")

    def test_validate_timestamps(self):
        stamps = [
            "00:01:00 - [Talk] Valid inside window",
            "00:06:30 - [Gameplay] Out of bounds",
        ]
        # start_sec=60, end_sec=300 -> window [0, 360]
        valid = validate_timestamps(stamps, start_sec=60, end_sec=300)
        self.assertEqual(len(valid), 1)
        self.assertIn("00:01:00", valid[0])

    def test_parse_timestamps_loop_and_collision(self):
        raw = """
00:01:00 - [Greeting] เริ่มต้นสตรีม
00:01:20 - [Talk] คุยเรื่องข่าว (collision < 60s)
00:02:30 - [Talk] คุยเรื่องการ์ตูน
00:01:00 - [Greeting] Loop breaker restart
00:04:00 - [Gameplay] Never reached
"""
        parsed = parse_timestamps(raw, max_stamps=4)
        self.assertEqual(len(parsed), 2)
        self.assertIn("00:01:00", parsed[0])
        self.assertIn("00:02:30", parsed[1])

    def test_is_continuation(self):
        self.assertTrue(is_continuation("SKIP"))
        self.assertTrue(is_continuation("CONTINUATION"))
        self.assertFalse(is_continuation("00:01:00 - [Talk] Topic"))


if __name__ == "__main__":
    unittest.main()
