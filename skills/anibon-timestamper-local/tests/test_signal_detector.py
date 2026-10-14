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


if __name__ == "__main__":
    unittest.main()
