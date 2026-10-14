import unittest
from anibon.topic_scanner import extract_macro_anchor, scan_chunk_topic_pivot


class TestTopicScanner(unittest.TestCase):
    def test_extract_macro_anchor(self):
        info = {"title": "【Zelda BotW】ปู่โบ๊ตลุยเทพอสูรวารูตะ #3 | ANIBON"}
        anchor = extract_macro_anchor(info)
        self.assertEqual(anchor, "Zelda: Breath of the Wild")

        info_fgo = {"title": "สตรีม FGO กูดะกูดะ วิเคราะห์ตัวละคร | ANIBON"}
        anchor_fgo = extract_macro_anchor(info_fgo)
        self.assertEqual(anchor_fgo, "Fate/Grand Order")

    def test_scan_chunk_topic_pivot(self):
        current = "Zelda: Breath of the Wild"
        chunk_text = "เนี่ยนะก็เลย Limbus Company เว้ยโห หนักอยู่นะเนี่ย อัตราการเคลียร์บอส"
        pivot = scan_chunk_topic_pivot(chunk_text, current)
        self.assertEqual(pivot, "Limbus Company")

        # Same topic should not trigger pivot
        same_chunk = "ปู่โบ๊ตลุยเก็บหีบสมบัติในปราสาทไฮรูล"
        self.assertIsNone(scan_chunk_topic_pivot(same_chunk, current))


if __name__ == "__main__":
    unittest.main()
