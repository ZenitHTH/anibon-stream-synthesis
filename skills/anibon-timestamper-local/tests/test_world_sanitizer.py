import unittest
from anibon.world_sanitizer import sanitize_pokemon_names, clean_token_stutters, ensure_outro_timestamp


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


if __name__ == "__main__":
    unittest.main()
