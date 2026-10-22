import json
import tempfile
import unittest
from pathlib import Path
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



if __name__ == "__main__":
    unittest.main()
