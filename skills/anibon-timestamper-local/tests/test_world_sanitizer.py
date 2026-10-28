import unittest
from process.world_sanitizer import (
    sanitize_pokemon_names,
    clean_token_stutters,
    ensure_outro_timestamp,
    diversify_repetitive_stamps,
)
from process.prompts import _extract_recent_opening_verbs


class TestWorldSanitizer(unittest.TestCase):
    def test_sanitize_pokemon_names_and_stutter(self):
        raw = "01:15:00 - [Gameplay] ใช้ การ์โชมป์ สู้ใน Zelda: Breath of the Wildild"
        step1 = sanitize_pokemon_names(raw)
        self.assertIn("การ์โชมป์ (Garchomp)", step1)

        step2 = clean_token_stutters(step1)
        self.assertNotIn("Wildild", step2)
        self.assertIn("Wild", step2)

    def test_ensure_outro_timestamp(self):
        existing = "07:00:00 - [Gameplay] สำรวจโซนภูเขาไฟ\n"
        last_chunk = "(07:23:15) ขอบคุณทุกคนมากครับ ราตรีสวัสดิ์เจอกันใหม่ไลฟ์หน้า บ๊ายบายครับ"

        updated = ensure_outro_timestamp(existing, last_chunk)
        self.assertIn("07:23:15 - [Ending]", updated)
        self.assertIn("ขอบคุณทุกคน", updated)

    def test_ensure_outro_not_duplicated(self):
        existing = "07:23:15 - [Ending] ปู่โบ๊ตกล่าวขอบคุณผู้ชมและปิดสตรีม\n"
        last_chunk = "(07:23:15) ขอบคุณทุกคนมากครับ ราตรีสวัสดิ์"

        # Should not duplicate if [Ending] stamp is already present in last minutes
        updated = ensure_outro_timestamp(existing, last_chunk)
        self.assertEqual(updated.count("[Ending]"), 1)

    def test_diversify_repetitive_stamps(self):
        raw = (
            "00:10:00 - [Talk] วิเคราะห์เนื้อเรื่องตอนที่ 1 ใน Bleach\n"
            "00:15:00 - [Talk] วิเคราะห์พลังของจูฮาบัช ใน Bleach\n"
            "00:20:00 - [Talk] วิเคราะห์บังไคของชินจิ ใน Bleach\n"
        )
        cleaned = diversify_repetitive_stamps(raw)
        lines = [l for l in cleaned.splitlines() if l.strip()]
        self.assertEqual(sum(1 for l in lines if "วิเคราะห์" in l), 1)
        self.assertIn("เจาะลึกพลังของจูฮาบัช", lines[1])
        self.assertNotIn("ใน Bleach", lines[1])
        self.assertIn("ชำแหละบังไคของชินจิ", lines[2])

    def test_extract_recent_opening_verbs(self):
        stamps = [
            "00:10:00 - [Talk] วิเคราะห์เนื้อเรื่อง Bleach",
            "00:15:00 - [Reaction] อึ้ง! บทกลอนตอนที่ 50",
        ]
        verbs = _extract_recent_opening_verbs(stamps)
        self.assertEqual(verbs, ["วิเคราะห์", "อึ้ง!"])


if __name__ == "__main__":
    unittest.main()
