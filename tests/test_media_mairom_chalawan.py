from __future__ import annotations

import sys
import unittest
from pathlib import Path

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.media.identifier import identify_active_media
from process.media.separator import separate_chunk_media
from process.media.types import ChunkMediaInput, load_media_catalog


class TestMediaMairomAndChalawan(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_media_catalog()

    def test_chalawan_detected_and_separated(self) -> None:
        media_input = ChunkMediaInput(
            raw_lines=(
                "(07:43:45) >> นี่ฟังเพลงแบบสบายๆสนุกๆดีกว่า",
                "(07:44:41) >> น้ำมา เจอผู้หญิงอาบน้ำ เจอผู้หญิงอาบน้ำ",
                "(07:45:21) >> เลี้ยงเมียมันเลี้ยงหมา พ่อตา ฆ่าพ่อตาให้ตายแล้วเอาแม่ยายทำเมีย",
                "(07:46:17) แป๊บนึงครับเพลงมันหยาบไปครับ",
            ),
            livechat_lines=("ชาละวัน 5555",),
            gameplay_keywords=("minecraft",),
        )
        active = identify_active_media(media_input, self.catalog)
        active_titles = [c.title for c in active]
        self.assertTrue(any("ชาละวัน" in t for t in active_titles))
        segs = separate_chunk_media(media_input, active)
        audio_segs = [s for s in segs if s.label == "MEDIA_AUDIO"]
        self.assertTrue(len(audio_segs) >= 2)
        boat_segs = [s for s in segs if s.label == "BOAT_SPEECH"]
        self.assertTrue(any("แป๊บนึงครับ" in s.raw_text for s in boat_segs))

    def test_mairom_wanmae_detected(self) -> None:
        media_input = ChunkMediaInput(
            raw_lines=(
                "(07:33:24) อะไรเนี่ยอูแวอๆแวเพลงวันแม่ทำชาวเน็ต",
                "(07:34:11) หมายร่วมบทเพลงวันแม่",
            ),
            livechat_lines=("อูแว้", "เพลงวันแม่"),
            gameplay_keywords=("minecraft",),
        )
        active = identify_active_media(media_input, self.catalog)
        active_titles = [c.title for c in active]
        self.assertTrue(any("บทเพลงวันแม่" in t for t in active_titles))

    def test_mairom_unging_detected(self) -> None:
        media_input = ChunkMediaInput(
            raw_lines=(
                "(07:41:08) อาจารย์ไมค์รุ่มร้องเพลงกำลังใจทหารล่าสุดปล่อยเพลงอุ้งอิงออกไป",
                "(07:41:17) >> ก่อนจะจบขอร้องเพลงให้กำลังใจทหารหา",
                "(07:41:55) >> ผมให้ชื่อว่าอุ้งเอ๋ง อุ้งเอิง พุ่งเองออกไป",
            ),
            livechat_lines=("อุ๊งอิ๊งออกไป",),
            gameplay_keywords=("minecraft",),
        )
        active = identify_active_media(media_input, self.catalog)
        active_titles = [c.title for c in active]
        self.assertTrue(any("อุ๊งอิ๊งออกไป" in t for t in active_titles))


if __name__ == "__main__":
    unittest.main()
