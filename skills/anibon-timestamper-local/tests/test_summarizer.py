import unittest
from anibon.summarizer import (
    generate_part_summary,
    assemble_parts,
)


class TestSummarizer(unittest.TestCase):

    def test_generate_part_summary(self):
        stamps = [
            "00:00:10 - [Greeting] เริ่มต้นสตรีม",
            "00:05:00 - [Talk] อัปเดตประเด็นข่าวเกม",
            "00:15:30 - [Gameplay] เริ่มเล่นเควสต์หลัก",
        ]
        summary = generate_part_summary(stamps)
        self.assertIn("เริ่มต้นสตรีม", summary)
        self.assertIn("เริ่มเล่นเควสต์หลัก", summary)

    def test_assemble_parts_borders_and_byte_limit(self):
        stamps = [
            f"00:{i:02d}:00 - [Talk] ประเด็นที่ {i} รายละเอียดสตรีมประจำวัน"
            for i in range(15)
        ]
        assembled = assemble_parts(stamps)
        self.assertIn("ส่วนที่ 1:", assembled)
        self.assertIn("ส่วนที่ 2:", assembled)
        self.assertIn("═" * 57, assembled)
        # Check that individual parts do not exceed 3,500 bytes
        for part in assembled.split("\n\n"):
            self.assertLess(len(part.encode("utf-8")), 3500)


if __name__ == "__main__":
    unittest.main()
