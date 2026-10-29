from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.media.types import ChunkMediaInput, MediaCandidate, load_media_catalog
from process.media.trigger import detect_media_trigger


class TestMediaSeparation(unittest.TestCase):
    def test_load_media_catalog_contains_core_stream_songs(self) -> None:
        catalog = load_media_catalog()
        ids = {c.media_id for c in catalog}
        self.assertIn("mairom_phi_mai_rak", ids)
        self.assertIn("ksc_return_happiness", ids)
        self.assertIn("maha_chulalongkorn", ids)
        mairom = next(c for c in catalog if c.media_id == "mairom_phi_mai_rak")
        self.assertIn("พี่ไม่รักน้องเจ้า", mairom.title)
        self.assertTrue(any("ผีไม่ได้ดักเจ้า" in g for g in mairom.garble_patterns))

    def test_trigger_activates_on_song_chunk_with_turn_markers_and_chat(self) -> None:
        raw_lines = (
            "(03:45:46) >> อ่าเพลงที่ผมจะร้องให้นี้",
            "(03:45:48) >> ไม่ใช่ผมจะร้องไห้คือเพลงที่ผมจะร้องนี้",
            "(03:46:01) >> ปลัดกระทรวงมหาดไทยตามหา",
            "(03:46:04) >> ไปที่ราชธานีก็ไม่เจอผมก็เลยมาหาที่นี้",
            "(03:46:22) >> อ่าเพลงนี้นะครับเป็นเพลงที่เพราะที่สุด",
            "(03:46:30) >> เพราะแม่ผมร้องให้ฟังตั้งแต่เด็กๆ",
            "(03:47:00) >> ศิลปินโลกุตตระเชิญฟังนะครับ",
        )
        chat_lines = (
            "[03:46:10] UserA: อาจารย์ไม้ร่ม 5555",
            "[03:47:41] UserB: ขอเพลงสำหรับคนรักพ่อหน่อยครับ",
        )
        res = detect_media_trigger(ChunkMediaInput(raw_lines=raw_lines, livechat_lines=chat_lines))
        self.assertTrue(res.triggered)
        self.assertGreaterEqual(res.score, 2.0)
        self.assertIn("อาจารย์ไม้ร่ม", " ".join(res.chat_hints))

    def test_trigger_ignores_normal_excited_gameplay_without_media_cues(self) -> None:
        raw_lines = tuple(f"(01:00:{i:02d}) >> ตีมอนสเตอร์ในดันเจี้ยน" for i in range(10))
        chat_lines = ("[01:00:05] UserA: ดาบแรงมากครับปู่",)
        res = detect_media_trigger(ChunkMediaInput(raw_lines=raw_lines, livechat_lines=chat_lines))
        self.assertFalse(res.triggered)

