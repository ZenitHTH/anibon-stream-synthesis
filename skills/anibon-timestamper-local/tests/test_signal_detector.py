import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_LIB = Path(__file__).resolve().parent.parent.parent.parent / "lib"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from signal_detector import detect_signals_for_chunks, extract_metadata_signals, discover_reference_games


class TestSignalDetector(unittest.TestCase):
    def test_detect_signals_preserves_specific_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("ปู่บอทเล่น Chaos Zero Nightmare เล่นเกม สนุกมาก", encoding="utf-8")
            signals = detect_signals_for_chunks(tmp_path)
            self.assertIn("chunk_00", signals)
            files = [w["file"] for w in signals["chunk_00"]["weighted_files"]]
            self.assertTrue(any("chaos_zero_nightmare" in f.lower() for f in files))

    def test_detect_signals_prioritizes_specific_game_over_stream_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("เล่นเกม เล่นเกม เล่นเกม เล่นเกม Chaos Zero Nightmare", encoding="utf-8")
            signals = detect_signals_for_chunks(tmp_path)
            self.assertIn("chunk_00", signals)
            best = signals["chunk_00"]["best_file"]
            self.assertIsNotNone(best)
            self.assertIn("chaos_zero_nightmare", best.lower())

    def test_extract_metadata_signals_from_info_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            info_file = tmp_path / "info.json"
            info_file.write_text(json.dumps({
                "title": "สตรีมเล่น Deadlock กับเพื่อนๆ และเปิดตู้ CZN",
                "description": "วันนี้มาลุย Deadlock ยาวๆ และรีวิว Chaos Zero Nightmare",
                "tags": ["Deadlock", "CZN", "Gaming"]
            }, ensure_ascii=False), encoding="utf-8")

            signals = extract_metadata_signals(tmp_path)
            self.assertIn("deadlock", signals)
            self.assertIn("czn", signals)

    def test_discover_reference_games_from_markdown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            refs = tmp_path / "references"
            refs.mkdir()
            (refs / "Deadlock.md").write_text("# Deadlock\n", encoding="utf-8")
            (refs / "Sekiro_Shadows_Die_Twice.md").write_text("# Sekiro\n", encoding="utf-8")

            discovered = discover_reference_games(refs)
            self.assertIn("deadlock", discovered)
            self.assertIn("sekiro", discovered)

    def test_filter_standing_gaming_words_strips_dupe_codes_and_generic_terms(self):
        from signal_detector import filter_standing_gaming_words
        raw = "เปิดกาชา ตัวใหม่ C5 E6 S1 บอส ดาเมจ รอซึวสึ พเนอร์ โอเมก้าโค้ด"
        filtered, standing = filter_standing_gaming_words(raw)
        self.assertIn("c5", standing)
        self.assertIn("e6", standing)
        self.assertIn("s1", standing)
        self.assertNotIn(" c5 ", f" {filtered} ")
        self.assertNotIn(" e6 ", f" {filtered} ")
        self.assertIn("รอซึวสึ", filtered)
        self.assertIn("พเนอร์", filtered)
        self.assertIn("โอเมก้าโค้ด", filtered)

    def test_discover_reference_games_registers_special_words_and_blocks_common_character_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            refs = Path(tmp) / "references"
            refs.mkdir()
            for fn in ("Blue_Archive.md", "Chaos_Zero_Nightmare.md", "Wuthering_Waves.md", "Zenless_Zone_Zero.md", "Eternal_Return.md", "Thai_Book_Fair_Convention.md"):
                (refs / fn).write_text(f"# {fn}\n", encoding="utf-8")

            discovered = discover_reference_games(refs)
            for blocked in ("blue", "thai", "parry", "solo", "เกลือ", "yuki", "ยูกิ", "rin", "ริน", "mika", "มิกะ", "hoshino", "shiroko", "arona", "lucy", "alice", "yvonne", "kuro", "emma", "chizuru"):
                self.assertNotIn(blocked, discovered)
            for czn_kw in ("เคอส", "รอซึวสึ", "พเนอร์", "memory fragment", "โอเมก้าโค้ด", "เซรนิว"):
                self.assertIn("chaos_zero_nightmare", discovered[czn_kw].lower())
            self.assertIn("wuthering_waves", discovered["jinhsi"].lower())
            self.assertIn("zenless_zone_zero", discovered["bangboo"].lower())
            self.assertIn("blue_archive", discovered["kivotos"].lower())

    def test_chaining_weight_ignores_common_japanese_names_and_standing_dupe_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "info.json").write_text(json.dumps({
                "title": "1 ปีแล้ว ของ ฝันร้าย",
                "description": "เล่น Chaos Zero Nightmare",
                "tags": ["CZN"]
            }, ensure_ascii=False), encoding="utf-8")
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text("สวัสดีครับ วันนี้มาเล่น Chaos Zero Nightmare ครบรอบ 1 ปี", encoding="utf-8")
            (chunks / "chunk_01.txt").write_text("เปิดกาชา ได้ยูกิ E3 ได้ริน ได้มิกะ C5 E6 S1 เกลือมาก ตีบอส", encoding="utf-8")
            (chunks / "chunk_02.txt").write_text("อัปเกรดพเนอร์ รอซึวสึ โอเมก้าโค้ด เมมโมรี่แฟรกเมนต์", encoding="utf-8")

            signals = detect_signals_for_chunks(ws)
            self.assertIn("chaos_zero_nightmare", signals["chunk_01"]["best_file"].lower())
            self.assertNotIn("ยูกิ", signals["chunk_01"]["matched_keywords"])
            self.assertIn("e6", signals["chunk_01"]["standing_keywords"])
            self.assertIn("chaos_zero_nightmare", signals["chunk_02"]["best_file"].lower())
            self.assertIn("รอซึวสึ", signals["chunk_02"]["special_keywords"])
            self.assertGreater(signals["chunk_02"]["candidates"][0]["prob"], 0.85)

    def test_chaining_weight_switches_on_sustained_new_game_special_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text("เล่น Chaos Zero Nightmare ตีบอส เคอส", encoding="utf-8")
            (chunks / "chunk_01.txt").write_text("เปลี่ยนเกมมาเล่น Deadlock กับ Vindicta และ Grey Talon ใน Deadlock", encoding="utf-8")
            (chunks / "chunk_02.txt").write_text("Deadlock ตานี้ Bebop เก็บไหวิญญาณสวยมาก เล่น Deadlock ยาวๆ", encoding="utf-8")

            signals = detect_signals_for_chunks(ws)
            self.assertIn("chaos_zero_nightmare", signals["chunk_00"]["best_file"].lower())
            self.assertIn("deadlock", signals["chunk_02"]["best_file"].lower())

    def test_detect_signals_ignores_stream_rule_docs_as_game_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "info.json").write_text(json.dumps({
                "title": "สตรีมพูดคุย อนิเมะ และเล่น CZN",
                "tags": ["anime", "อนิเมะ", "CZN"]
            }, ensure_ascii=False), encoding="utf-8")
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text("สวัสดีครับ วันนี้มาเล่น Chaos Zero Nightmare", encoding="utf-8")
            signals = detect_signals_for_chunks(ws)
            for cand in signals["chunk_00"]["candidates"]:
                self.assertNotIn("phuboat-anime-talking-style", cand["file"].lower())
                self.assertNotIn("references/stream/", cand["file"].lower())

    def test_short_ascii_and_ego_do_not_misclassify_tokusatsu(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text(
                "Mission impossible Side Vision Ego อีโก้สูงมาก พูดถึงการ์ดเกมทั่วไป",
                encoding="utf-8",
            )
            (chunks / "chunk_01.txt").write_text(
                "เริ่มดูโอเมก้าฮอร์นตอนที่ 13 เอ็นคาคุ อิบารุ อีโมเกียร์ กาวาเรียน อุลตร้าแมนเทโอ",
                encoding="utf-8",
            )
            signals = detect_signals_for_chunks(ws)
            c0_files = [w["file"].lower() for w in signals["chunk_00"]["candidates"]]
            self.assertFalse(any("arknights_endfield" in f for f in c0_files))
            self.assertFalse(any("limbus_company" in f for f in c0_files))
            self.assertIn("tokusatsu_project_red", (signals["chunk_01"]["best_file"] or "").lower())

    def test_lily_blacklisted_in_stage1_and_new_toku_and_channel_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text(
                "ลิลี่ ตัวใหม่ แต่พูดถึง Suoming Unspoken Rue และ New Federation ใน WuWa",
                encoding="utf-8",
            )
            (chunks / "chunk_01.txt").write_text(
                "มาดู Kamen Rider My-Th ต่อด้วย Xenolhu กับคุณนินุ คุยข่าว James Gunn และ Skydance",
                encoding="utf-8",
            )
            discovered = discover_reference_games()
            for blocked in ("lily", "ลิลี่", "anna", "แอนนา", "rebecca", "รีเบคก้า"):
                self.assertNotIn(blocked, discovered)

            signals = detect_signals_for_chunks(ws)
            self.assertIn("wuthering_waves", (signals["chunk_00"]["best_file"] or "").lower())
            self.assertNotIn("ลิลี่", signals["chunk_00"]["matched_keywords"])
            c1_weighted = [w["file"].lower() for w in signals["chunk_01"]["weighted_files"]]
            self.assertTrue(any("channel-and-news-knowledge.md" in f for f in c1_weighted))
            self.assertNotIn("channel-and-news-knowledge", (signals["chunk_01"]["best_file"] or "").lower())
            self.assertTrue(any("tokusatsu_project_red" in f or "godzilla_minus_zero" in f for f in c1_weighted))

    def test_noisy_generic_thai_and_asr_tokens_blocked_in_stage1(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text(
                "โซล soul ชาวบ้าน villager รานะ ซิน ไม่รานะ ตีชาวบ้านเก็บโซลในฉาก",
                encoding="utf-8",
            )
            discovered = discover_reference_games()
            for noisy in ("soul", "โซล", "villager", "ชาวบ้าน", "rana", "รานะ", "hsin", "ซิน"):
                self.assertNotIn(noisy, discovered)
            signals = detect_signals_for_chunks(ws)
            self.assertIsNone(signals["chunk_00"]["best_file"])
            self.assertEqual(signals["chunk_00"]["candidates"], [])





if __name__ == "__main__":
    unittest.main()
