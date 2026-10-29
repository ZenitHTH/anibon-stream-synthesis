# tests/test_patch_music_chunks.py
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from process.music.lore import SongContextBrief
from scripts.patch_music_chunks import (
    format_song_context_briefing,
    patch_chunk_with_song_lore,
    scan_and_patch_workspace,
)

class TestPatchMusicChunks(unittest.TestCase):
    def test_patch_chunk_replaces_speech_and_prepends_lore(self):
        with TemporaryDirectory() as tmpdir:
            chunk_file = Path(tmpdir) / "chunk_01.txt"
            chunk_file.write_text("[03:45:00 - 03:50:00]\nข้อความติดลูปคุณคุณคุณคุณ", encoding="utf-8")
            brief = SongContextBrief(
                title="แอ๊ดคาราบาว",
                artist="GUNNER",
                theme="แร็ปดราม่า",
                meme_lore="แซวยอดวิว",
                keywords=["เนเน่"]
            )
            patch_chunk_with_song_lore(chunk_file, brief, "อันนี้ 4 ล้านแล้วอ่ะ ไอ้เชี่ยเกิดไป")
            content = chunk_file.read_text(encoding="utf-8")
            self.assertIn("[Song Context Briefing]", content)
            self.assertIn("อันนี้ 4 ล้านแล้วอ่ะ", content)
            self.assertNotIn("คุณคุณคุณคุณ", content)
            self.assertTrue(content.startswith("[03:45:00 - 03:50:00]"))

    def test_patch_chunk_preserves_standard_chunk_header(self):
        with TemporaryDirectory() as tmpdir:
            chunk_file = Path(tmpdir) / "chunk_45.txt"
            chunk_file.write_text("CHUNK 45 | 03:45:00–03:50:00 | cutoff=03:50:00\nข้อความสตรีม", encoding="utf-8")
            brief = SongContextBrief(
                title="พี่ไม่รักน้องเจ้า",
                artist="อ.ไม้ร่ม",
                theme="A cappella",
                meme_lore="ดักเจ้า",
                keywords=["ไม้ร่ม"]
            )
            patch_chunk_with_song_lore(chunk_file, brief, "เสียงพูดคลีน")
            content = chunk_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("CHUNK 45 | 03:45:00–03:50:00 | cutoff=03:50:00"))
            self.assertIn("[Song Context Briefing]", content)
            self.assertIn("เสียงพูดคลีน", content)

    def test_scan_and_patch_workspace(self):
        with TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            livechat_dir = ws / "livechat"
            livechat_dir.mkdir()

            chunk_file = chunks_dir / "chunk_01.txt"
            chunk_file.write_text("[03:45:00 - 03:50:00]\nข้อความติดลูป", encoding="utf-8")

            chat_file = livechat_dir / "livechat_chunk_01.txt"
            chat_file.write_text("เพลงอะไรเหรอครับ\nพี่ไม่ได้ดักเจ้าหน่อยงับ\nเพราะมาก", encoding="utf-8")

            index_file = livechat_dir / "livechat_index.json"
            index = {
                "chunk_01": {
                    "file": str(chat_file),
                    "count": 3,
                    "start": 13500,
                    "end": 13800,
                }
            }
            index_file.write_text(json.dumps(index), encoding="utf-8")

            anchors_file = ws / "music_anchors.json"
            anchors_file.write_text(json.dumps([{"symbol": "[เพลง]", "offset_ms": 13600000}]), encoding="utf-8")

            count = scan_and_patch_workspace(ws)
            self.assertEqual(count, 1)

            patched = chunk_file.read_text(encoding="utf-8")
            self.assertIn("[Song Context Briefing]", patched)
            self.assertIn("ไม้ร่ม", patched)

    def test_find_matching_lore_resolves_chalawan_and_ploy_trong_nee(self):
        from scripts.patch_music_chunks import find_matching_lore
        chalawan_chat = ["เพลงชาละวัน 5555", "เพลงวงเหล้า"]
        chalawan_brief = find_matching_lore(chalawan_chat)
        self.assertIn("ชาละวัน", chalawan_brief.title)

        ploy_chat = ["ปล่อยตรงนี้ GETFLIX", "เพลงนี้หยาบมั้ย"]
        ploy_brief = find_matching_lore(ploy_chat)
        self.assertIn("ปล่อยตรงนี้", ploy_brief.title)


if __name__ == "__main__":
    unittest.main()
