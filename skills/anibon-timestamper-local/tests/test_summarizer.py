import unittest
from anibon.summarizer import (
    generate_part_summary,
    assemble_parts,
    find_best_boundary,
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
        assembled = assemble_parts(stamps, deduplicate=False)
        self.assertIn("ส่วนที่ 1:", assembled)
        self.assertIn("ส่วนที่ 2:", assembled)
        self.assertIn("═" * 57, assembled)
        # Check that individual parts do not exceed 3,500 bytes
        for part in assembled.split("\n\n"):
            self.assertLess(len(part.encode("utf-8")), 3500)

    def test_find_best_boundary_snaps_to_transition(self):
        stamps = [
            f"00:{i:02d}:00 - [Talk] ประเด็นการเมืองข้อที่ {i}"
            for i in range(11)
        ] + [
            "00:11:00 - [Talk] ปู่โบ๊ตสรุปการพูดคุยเรื่องการเมืองและเตรียมเปลี่ยนไปคุยเรื่องความบันเทิง",
            "00:12:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 1",
            "00:13:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 2",
            "00:14:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 3",
            "00:15:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 4",
        ]
        # target_idx is 14, but stamp 11 has the transition marker.
        # Boundary should snap to 12 (ending block after stamp 11).
        best = find_best_boundary(stamps, target_idx=14, window=4)
        self.assertEqual(best, 12)

    def test_find_best_boundary_picks_closest_transition(self):
        stamps = [
            f"00:{i:02d}:00 - [Talk] ประเด็นการเมืองข้อที่ {i}"
            for i in range(11)
        ] + [
            "00:11:00 - [Talk] เข้าสู่ช่วงการพูดคุยย่อย",
            "00:12:00 - [Talk] ประเด็นการเมืองข้อที่ 11",
            "00:13:00 - [Talk] ปู่โบ๊ตสรุปการพูดคุยเรื่องการเมืองและเตรียมเปลี่ยนไปคุยเรื่องความบันเทิง",
            "00:14:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 1",
            "00:15:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 2",
        ]
        # target_idx is 14. Markers exist at 11 and 13.
        # Marker 13 (dist 1) is closer than marker 11 (dist 3).
        # Best boundary should snap to 14 (after stamp 13).
        best = find_best_boundary(stamps, target_idx=14, window=4)
        self.assertEqual(best, 14)

    def test_find_best_boundary_at_end_of_list(self):
        stamps = [f"00:{i:02d}:00 - [Talk] หัวข้อ {i}" for i in range(15)] + [
            "00:15:00 - [Talk] สรุปการพูดคุยเรื่องการเมืองและเตรียมเปลี่ยนไปคุยเรื่องความบันเทิง",
        ]
        # target_idx is 14. Last stamp (15) has the marker and must not be excluded.
        best = find_best_boundary(stamps, target_idx=14, window=4)
        self.assertEqual(best, 16)

    def test_assemble_parts_snaps_series_to_next_part(self):
        stamps = [
            f"00:{i:02d}:00 - [Talk] ประเด็นการเมืองข้อที่ {i}"
            for i in range(11)
        ] + [
            "00:11:00 - [Talk] ปู่โบ๊ตสรุปการพูดคุยเรื่องการเมืองและเตรียมเปลี่ยนไปคุยเรื่องความบันเทิง",
            "00:12:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 1",
            "00:13:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 2",
            "00:14:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 3",
            "00:15:00 - [Talk] รีวิวซีรีส์ Lanterns ตอนที่ 4",
        ]
        assembled = assemble_parts(stamps, deduplicate=False)
        parts = assembled.split("\n\n")
        self.assertEqual(len(parts), 2)
        # Part 1 ends with politics transition cue
        self.assertIn("สรุปการพูดคุยเรื่องการเมืองและเตรียมเปลี่ยนไปคุยเรื่องความบันเทิง", parts[0])
        self.assertNotIn("รีวิวซีรีส์ Lanterns", parts[0])
        # Part 2 starts with series discussion
        self.assertIn("รีวิวซีรีส์ Lanterns ตอนที่ 1", parts[1])

    def test_enforce_byte_cap_splits_and_renumbers(self):
        from anibon.summarizer import enforce_byte_cap
        b = "═" * 57
        big = "\n".join(f"00:{i:02d}:00 - [Talk] " + "ก" * 120 for i in range(20))
        md = f"{b}\n ส่วนที่ 1: หัวข้อ (⏱ เริ่ม: 00:00:00)\n{b}\n{big}\n\n{b}\n ส่วนที่ 2: ท้าย (⏱ เริ่ม: 00:30:00)\n{b}\n00:30:00 - [Chat] ปิดไลฟ์"
        out = enforce_byte_cap(md, limit=3500)
        parts = out.split("\n\n")
        self.assertGreater(len(parts), 2)
        for i, p in enumerate(parts, 1):
            self.assertLessEqual(len(p.encode("utf-8")), 3500)
            self.assertIn(f"ส่วนที่ {i}:", p)
        self.assertEqual(out.count("[Talk]"), 20)

    def test_enforce_byte_cap_multiline_header(self):
        from anibon.summarizer import enforce_byte_cap
        b = "═" * 57
        big = "\n".join(f"00:{i:02d}:00 - [Talk] " + "ก" * 120 for i in range(20))
        # 2-line header between borders
        md = f"{b}\n📌 ส่วนที่ 1: หัวข้อการวิเคราะห์\n(⏱ เริ่ม: 00:00:00)\n{b}\n{big}"
        out = enforce_byte_cap(md, limit=3500)
        parts = out.split("\n\n")
        self.assertGreater(len(parts), 1)
        for p in parts:
            # Check that borders are not duplicated (exactly 2 borders per part)
            self.assertEqual(p.count(b), 2)
            self.assertLessEqual(len(p.encode("utf-8")), 3500)

    def test_assemble_parts_macro_grouping_avoids_over_splitting(self):
        # 200 timestamps should NOT be chopped into 15+ micro parts
        stamps = [
            f"0{i//60}:{i%60:02d}:00 - [Talk] ประเด็นที่ {i} ในการสนทนา"
            for i in range(200)
        ]
        assembled = assemble_parts(stamps, deduplicate=False)
        parts = assembled.split("\n\n")
        # Macro grouping must produce 4 to 6 parts
        self.assertGreaterEqual(len(parts), 4)
        self.assertLessEqual(len(parts), 6)

    def test_run_local_summarizer_pass_enforces_byte_cap(self):
        from unittest.mock import patch
        from anibon.summarizer import run_local_summarizer_pass

        stamps = [f"00:{i:02d}:00 - [Talk] " + ("ก" * 120) for i in range(25)]
        fake_llm_output = (
            "Part 1: 00:00:00\nSummary: เปิดสตรีมคุยข่าวใหญ่\n\n"
            "Part 2: 00:20:00\nSummary: ปิดท้ายสตรีม\n"
        )
        with patch("anibon.summarizer.call_local", return_value=fake_llm_output):
            md = run_local_summarizer_pass("http://127.0.0.1:1234", "test-model", stamps)

        self.assertIsNotNone(md)
        for part in md.split("\n\n"):
            self.assertLessEqual(len(part.encode("utf-8")), 3500)


if __name__ == "__main__":
    unittest.main()


