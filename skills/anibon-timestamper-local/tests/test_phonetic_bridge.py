import unittest
from process.knowledge.phonetic_bridge import load_phonetic_bridge, match_phonemes


class TestPhoneticBridge(unittest.TestCase):
    def test_load_and_match_phonemes(self):
        bridge = load_phonetic_bridge()
        self.assertIsInstance(bridge, dict)
        self.assertGreater(len(bridge), 0)
        self.assertIn("เรดแรปเตอร์", bridge)
        self.assertEqual(bridge["เรดแรปเตอร์"]["en"], "Raidraptor")
        self.assertEqual(bridge["เรดแรปเตอร์"]["domain"], "yugioh")

        text = "ปู่โบ๊ตวิเคราะห์เด็ค เรดแรปเตอร์ เจอขัดด้วย แม็กซ์ ซี แต่ยังกาง อัลทิเมตฟอลคอน ได้"
        hits = match_phonemes(text, bridge)
        self.assertGreaterEqual(len(hits), 3)
        en_names = [h["en"] for h in hits]
        self.assertIn("Raidraptor", en_names)
        self.assertIn('Maxx "C"', en_names)
        self.assertIn("Raidraptor - Ultimate Falcon", en_names)

    def test_match_phonemes_pokemon_and_limbus(self):
        bridge = load_phonetic_bridge()
        text = "ส่งตัว การ์โชมป์ และ เป็ดต้นหอม ลงสู้ ก่อนที่วันพรุ่งนี้ ริมัส คันเ 10 จะมา"
        hits = match_phonemes(text, bridge)
        en_names = [h["en"] for h in hits]
        self.assertIn("Garchomp", en_names)
        self.assertIn("Farfetch'd", en_names)
        self.assertIn("Limbus Company", en_names)
        self.assertIn("Canto X", en_names)


if __name__ == "__main__":
    unittest.main()
