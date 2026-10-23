"""Tests for validate_tags.py — keyword-based tag validation + retag."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "scripts"))
from validate_tags import (
    parse_line,
    suggest_retag,
    check_false_positive,
    validate_file,
)


class TestValidateTags(unittest.TestCase):
    def test_parse_standard(self):
        result = parse_line("00:15:30 - [Gameplay] Fighting god boss")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "00:15:30")
        self.assertEqual(result[1], "[Gameplay]")
        self.assertEqual(result[2], "Fighting god boss")

    def test_parse_no_match(self):
        self.assertIsNone(parse_line("garbage line without timestamp"))

    def test_parse_empty(self):
        self.assertIsNone(parse_line(""))

    def test_boss_retag(self):
        tag, reason = suggest_retag("สู้บอสตัวนี้ยากมาก", "[Gameplay]")
        self.assertEqual(tag, "[Boss]", f"Expected [Boss], got {tag}")
        self.assertIsNotNone(reason)

    def test_boss_already_correct(self):
        result = suggest_retag("สู้บอสตัวนี้ยากมาก", "[Boss]")
        self.assertIsNone(result[0])

    def test_boss_english(self):
        tag, _ = suggest_retag("boss fight at final stage", "[Gameplay]")
        self.assertEqual(tag, "[Boss]")

    def test_death_retag(self):
        tag, _ = suggest_retag("ตายแล้วไอ้นี่", "[Gameplay]")
        self.assertEqual(tag, "[Death]")

    def test_death_already_correct(self):
        result = suggest_retag("ตายหมดทั้งทีม", "[Death]")
        self.assertIsNone(result[0])

    def test_victory_retag(self):
        tag, _ = suggest_retag("เคลียร์บอสแล้ว", "[Gameplay]")
        self.assertEqual(tag, "[Victory]")

    def test_victory_english(self):
        tag, _ = suggest_retag("clear mission complete", "[Gameplay]")
        self.assertEqual(tag, "[Victory]")

    def test_victory_already_correct(self):
        result = suggest_retag("เคลียร์บอสแล้ว", "[Victory]")
        self.assertIsNone(result[0])

    def test_gacha_retag(self):
        tag, _ = suggest_retag("จิ้มกาชา 10 โรล", "[Gameplay]")
        self.assertEqual(tag, "[Gacha]")

    def test_chat_retag(self):
        tag, _ = suggest_retag("ในแชทบอกว่าให้ลองใหม่", "[Talk]")
        self.assertEqual(tag, "[Chat]")

    def test_reaction_retag(self):
        tag, _ = suggest_retag("ดูคลิปอนิเมะตัวอย่าง", "[Talk]")
        self.assertEqual(tag, "[Reaction]")

    def test_news_retag(self):
        tag, _ = suggest_retag("มีข่าวอัปเดตเกมใหม่", "[Gameplay]")
        self.assertEqual(tag, "[News]")

    def test_donation_retag(self):
        tag, _ = suggest_retag("ขอบคุณครับสำหรับ super chat", "[Talk]")
        self.assertEqual(tag, "[Donation]")

    def test_no_keyword_match(self):
        result = suggest_retag("เดินเล่นในเมืองเฉยๆ", "[Gameplay]")
        self.assertIsNone(result[0])

    def test_generic_talk(self):
        result = suggest_retag("วันนี้อากาศดี", "[Talk]")
        self.assertIsNone(result[0])

    def test_boss_false_positive(self):
        result = suggest_retag("บอสว่ายังไงบ้าง", "[Gameplay]")
        self.assertIsNone(result[0], f"Should be blocked: {result}")

    def test_boss_false_positive_chat(self):
        result = suggest_retag("พูดถึงบอสเก่า", "[Talk]")
        self.assertIsNone(result[0])

    def test_false_positive_blocks(self):
        self.assertTrue(check_false_positive("บอสว่ายังไง", "[Boss]"))
        self.assertFalse(check_false_positive("สู้บอส", "[Boss]"))
        self.assertTrue(check_false_positive("พูดถึงบอส", "[Boss]"))
        self.assertTrue(check_false_positive("เกียวตาย", "[Death]"))
        self.assertFalse(check_false_positive("ตายแล้ว", "[Death]"))

    def test_validate_file_retags(self):
        input_lines = [
            "00:15:30 - [Gameplay] สู้บอสตัวนี้ยากมาก\n",
            "00:20:00 - [Gameplay] เดินเล่นในเมือง\n",
            "00:25:00 - [Gameplay] ตายหมดทั้งทีม\n",
            "01:00:00 - [Boss] สู้บอสอีกตัว\n",
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f_in:
            f_in.writelines(input_lines)
            in_path = pathlib.Path(f_in.name)

        out_path = in_path.parent / f"{in_path.stem}_validated.txt"

        try:
            stats = validate_file(in_path, out_path)
            self.assertEqual(stats["total"], 4)
            self.assertEqual(stats["changed"], 2)
            self.assertEqual(stats["unchanged"], 2)
            self.assertEqual(stats["skipped"], 0)

            out_lines = out_path.read_text(encoding="utf-8").strip().split("\n")
            self.assertIn("[Boss]", out_lines[0])
            self.assertIn("[Gameplay]", out_lines[1])
            self.assertIn("[Death]", out_lines[2])
            self.assertIn("[Boss]", out_lines[3])
        finally:
            in_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)

    def test_validate_file_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f_in:
            in_path = pathlib.Path(f_in.name)

        out_path = in_path.parent / f"{in_path.stem}_validated.txt"

        try:
            stats = validate_file(in_path, out_path)
            self.assertEqual(stats["total"], 0)
            self.assertEqual(stats["changed"], 0)
            out_content = out_path.read_text(encoding="utf-8").strip()
            self.assertEqual(out_content, "")
        finally:
            in_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
