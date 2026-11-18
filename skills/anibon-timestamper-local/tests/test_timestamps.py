import unittest
import re
from common.timestamps import (
    TAGS,
    TAG_REMAP,
    normalize_tag,
    sanitize_timestamp_line,
    parse_timestamps,
    validate_timestamps,
    is_continuation,
    deduplicate_consecutive_timestamps,
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

    def test_deduplicate_consecutive_timestamps(self):
        stamps = [
            "00:01:00 - [Talk] พูดถึงเกม Elden Ring สายเวท",
            "00:02:15 - [Talk] บ่นเรื่องดาเมจในเกม Elden Ring",
            "00:05:00 - [Talk] วิเคราะห์การเล่นเกม Elden Ring ต่อเนื่อง",
            "00:15:00 - [Gameplay] เริ่มเล่นเกม Minecraft โหมดใหม่",
        ]
        deduped = deduplicate_consecutive_timestamps(stamps, min_gap_sec=120, max_dedup_gap_sec=600)
        # 00:02:15 and 00:05:00 should be deduplicated into the earliest 00:01:00 stamp
        self.assertEqual(len(deduped), 2)
        self.assertIn("00:01:00", deduped[0])
        self.assertIn("00:15:00", deduped[1])

    def test_rapid_distinct_reactions_preserved_above_collision_floor(self):
        stamps = [
            "03:36:15 - [Reaction] อึ้งหลังซูมดูรายละเอียดตัวละครใหม่แบบใกล้ชิด",
            "03:37:24 - [Reaction] ตบมือกุมหัวร้องลั่นหลังเปิดภาพร่างสุดท้ายจนโดเนทเด้ง",
            "03:44:23 - [Reaction] หัวเราะลั่นท่าลอยตัวกลางอากาศของร่างหนึ่ง",
            "03:45:34 - [Reaction] ตาโตเห็นตุ๊กตาจิ๋วกับเอฟเฟกต์น้ำแข็งไสสุดล้ำ",
        ]
        deduped = deduplicate_consecutive_timestamps(stamps, min_gap_sec=120, max_dedup_gap_sec=600)
        self.assertEqual(len(deduped), 4)

    def test_duplicate_banter_reactions_within_150s_still_collapsed(self):
        stamps = [
            "01:10:00 - [Reaction] ขำมุกแชทเรื่องกาชาเกลือมาก",
            "01:11:40 - [Reaction] ขำมุกแชทเรื่องกาชาเกลือซ้ำ",
        ]
        deduped = deduplicate_consecutive_timestamps(stamps, min_gap_sec=120, max_dedup_gap_sec=600)
        self.assertEqual(len(deduped), 1)

    def test_parse_timestamps_allows_45s_reaction_separation(self):
        raw = (
            "04:43:30 - [Gameplay] ฟาร์มเควสต์ฟรีเตรียมปลดล็อกตัวละคร\n"
            "04:44:24 - [Reaction] เหลียวขำแชทขอสกินร่างสามหลังเห็นชุดใหม่\n"
        )
        parsed = parse_timestamps(raw, max_stamps=4)
        self.assertEqual(len(parsed), 2)


if __name__ == "__main__":
    unittest.main()
