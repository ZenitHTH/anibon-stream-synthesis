import unittest
from pathlib import Path
import tempfile
import json

from anibon.state import (
    load_state,
    save_state,
    load_chunk_livechat,
    load_chunk_activity,
    load_chunk_mood,
    discover_chunks,
    load_chunk_file,
)


class TestState(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_and_load_state(self):
        state = {"current_chunk": 5, "all_timestamps": ["00:01:00 - [Talk] Hello"]}
        save_state(self.ws, state)
        loaded = load_state(self.ws)
        self.assertEqual(loaded["current_chunk"], 5)
        self.assertIn("last_updated", loaded)

    def test_discover_chunks(self):
        chunks_dir = self.ws / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "chunk_01.txt").write_text("(00:01:00) Hi", encoding="utf-8")
        (chunks_dir / "chunk_00.txt").write_text("(00:00:00) Start", encoding="utf-8")

        files = discover_chunks(self.ws)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].stem, "chunk_00")
        self.assertEqual(files[1].stem, "chunk_01")

    def test_multimodal_loaders(self):
        lc_dir = self.ws / "livechat"
        lc_dir.mkdir()
        (lc_dir / "livechat_chunk_00.txt").write_text("User1: 55555\nUser2: Lol", encoding="utf-8")

        act_dir = self.ws / "activity"
        act_dir.mkdir()
        (act_dir / "activity_chunk_00.txt").write_text("Game on screen: FGO", encoding="utf-8")

        (self.ws / "mood_555.json").write_text(json.dumps({
            "chunk_00": {"verdict": "HYPE", "tone": {"tone": "Excited"}}
        }), encoding="utf-8")

        self.assertIn("User1: 55555", load_chunk_livechat(self.ws, "chunk_00"))
        self.assertEqual("Game on screen: FGO", load_chunk_activity(self.ws, "chunk_00"))
        self.assertIn("HYPE", load_chunk_mood(self.ws, "chunk_00"))

    def test_load_chunk_file_scrubs_speaker_name_and_phonetics(self):
        chunks_dir = self.ws / "chunks"
        chunks_dir.mkdir()
        chunk_file = chunks_dir / "chunk_00.txt"
        chunk_file.write_text(
            "CHUNK 00 | 00:00:00–00:05:00 | cutoff=00:04:30\n"
            "(00:01:00) ปู่บอทกำลังเล่น อัพโฟโล สายต่อย\n"
            "(00:02:00) ลุงบอทบ่นเรื่อง เค้าสิ่งนี้แม่ ว่าแจกเยอะ\n",
            encoding="utf-8"
        )
        mappings = [
            {"correct": "Abrams", "patterns": ["อัพโฟโล"]},
            {"correct": "Chaos Zero Nightmare", "patterns": ["เค้าสิ่งนี้แม่"]},
        ]
        data = load_chunk_file(chunk_file, mappings=mappings)
        texts = [item["text"] for item in data["items"]]
        self.assertIn("ปู่โบ๊ตกำลังเล่น Abrams สายต่อย", texts[0])
        self.assertIn("ปู่โบ๊ตบ่นเรื่อง Chaos Zero Nightmare ว่าแจกเยอะ", texts[1])
        self.assertNotIn("ปู่บอท", texts[0])
        self.assertNotIn("ลุงบอท", texts[1])


if __name__ == "__main__":
    unittest.main()

