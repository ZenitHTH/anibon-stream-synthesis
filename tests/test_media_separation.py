from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from chunk.state import load_chunk_file
from process.prompts import build_recursive_prompt
from process.media.types import ChunkMediaInput, MediaCandidate, load_media_catalog
from process.media.trigger import detect_media_trigger
from process.media.phonetic import thai_phonetic_skeleton, phonetic_phrase_similarity
from process.media.identifier import identify_active_media
from process.media.separator import separate_chunk_media, build_media_separation_prompt_block


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

    def test_thai_phonetic_skeleton_matches_melisma_garbles(self) -> None:
        sim1 = phonetic_phrase_similarity("ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้า", "พี่ไม่รักน้องเจ้า")
        sim2 = phonetic_phrase_similarity("หมาก็ยังหยุดเหาเลยครับ", "หมาก็ยังหยุดเห่าเลยครับ")
        self.assertGreaterEqual(sim1, 0.65)
        self.assertGreaterEqual(sim2, 0.85)

    def test_identify_active_media_resolves_mairom_and_ksc_from_chunk(self) -> None:
        inp = ChunkMediaInput(
            raw_lines=(
                "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้า",
                "(03:57:18) >> ขอดูแลคุ้มครองด้วยใจนี่คือคำสัญญา",
            ),
            livechat_lines=("[03:46:10] UserA: อาจารย์ไม้ร่มมาแล้ว",),
        )
        matched = identify_active_media(inp)
        matched_ids = [m.media_id for m in matched]
        self.assertIn("mairom_phi_mai_rak", matched_ids)
        self.assertIn("ksc_return_happiness", matched_ids)

    def test_separator_splits_midline_collision_and_preserves_gameplay(self) -> None:
        inp = ChunkMediaInput(
            raw_lines=(
                "(03:48:11) >> แล้วถึงจะยอดเยี่ยมนะครับอือุ้ยnล scap",
                "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้าพี่ไม่",
                "(03:48:32) ได้ดักเจ้าพี่ไม่ได้เไม่ได้รักไงเออก็ไม่เข้าใจไง",
                "(03:52:18) >> เดี๋ยวนะโอตกใจเหมือนกูว่ากูลบดาบไอ้เหี้ย",
                "(03:57:26) วันนี้ชาติเผชิญผ่านภัยไฟลุใครไม่พร้อมออกจากช่องกูออกไปเลย",
            ),
            livechat_lines=("[03:46:10] UserA: เพลงอาจารย์ไม้ร่ม + คืนความสุข",),
            gameplay_keywords=("scap", "ลบดาบ", "nether", "วิลเลเจอร์"),
        )
        segments = separate_chunk_media(inp)
        by_ts = {}
        for seg in segments:
            by_ts.setdefault(seg.timestamp, []).append(seg)

        self.assertEqual(by_ts["03:48:27"][0].label, "MEDIA_AUDIO")
        self.assertIn("พี่ไม่รักน้องเจ้า", by_ts["03:48:27"][0].ground_truth)
        self.assertEqual(by_ts["03:52:18"][0].label, "BOAT_GAMEPLAY")

        labels_5726 = [s.label for s in by_ts["03:57:26"]]
        self.assertEqual(labels_5726, ["MEDIA_AUDIO", "BOAT_SPEECH"])

        block = build_media_separation_prompt_block(inp)
        self.assertIn("## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)", block)
        self.assertIn("[MEDIA_AUDIO", block)
        self.assertIn("[BOAT_SPEECH]", block)

    def test_end_to_end_chunk_load_and_recursive_prompt_injects_media_separation(self) -> None:
        sample_chunk = (
            "# chunk_50 (03:45:00–03:50:30, cutoff=03:50:30)\n"
            "(03:45:46) >> อ่าเพลงที่ผมจะร้องให้นี้\n"
            "(03:47:00) >> ศิลปินโลกุตตระเชิญฟังนะครับ\n"
            "(03:47:06) >> รอก่อนไอ้สัตว์อย่ารีบเออคนฟังอ่ะช่องแชท\n"
            "(03:48:27) ผีไม่ได้ดักเจ้าพี่ไม่ได้ดักเจ้าพี่ไม่\n"
            "(03:48:32) ได้ดักเจ้าพี่ไม่ได้เไม่ได้รักไงเออก็ไม่เข้าใจไง\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "chunk_50.txt"
            p.write_text(sample_chunk, encoding="utf-8")
            chunk_data = load_chunk_file(p)
            self.assertIn("raw_text", chunk_data["items"][0])
            self.assertTrue(chunk_data["items"][0]["raw_text"].startswith(">>"))

            prompt = build_recursive_prompt(
                chunk=chunk_data,
                current_topic="เล่น Minecraft สำรวจ Nether",
                rolling_summary="ปู่โบ๊ตสำรวจ Nether",
                lang="th",
                livechat="[03:46:10] UserA: เพลงอาจารย์ไม้ร่ม 555",
            )
            self.assertIn("## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)", prompt)
            self.assertIn("พี่ไม่รักน้องเจ้า", prompt)
            self.assertIn("[BOAT_SPEECH]", prompt)

    def test_real_workspace_chunks_detect_all_core_songs(self) -> None:
        chunks_dir = Path("/Users/zenithth/youtube_l00khgGzmIg_workspace/chunks")
        if not (chunks_dir / "chunk_50.txt").is_file():
            self.skipTest("Real workspace chunks not present on local machine")
        expected_map = {
            50: "mairom_phi_mai_rak",
            51: "mairom_phi_mai_rak_remix",
            52: "ksc_return_happiness",
            53: "ksc_return_happiness",
            54: "maha_chulalongkorn",
        }
        for chunk_idx, expected_id in expected_map.items():
            data = load_chunk_file(chunks_dir / f"chunk_{chunk_idx}.txt")
            raw_lines = tuple(
                f"({it['timestamp']}) {it.get('raw_text') or it.get('text', '')}"
                for it in data["items"]
            )
            inp = ChunkMediaInput(
                raw_lines=raw_lines,
                gameplay_keywords=("scap", "ดาบ", "nether", "วิลเลเจอร์", "way stone"),
            )
            active = identify_active_media(inp)
            active_ids = {c.media_id for c in active}
            self.assertIn(
                expected_id,
                active_ids,
                f"Chunk {chunk_idx} failed to detect expected media {expected_id}",
            )
            segs = separate_chunk_media(inp, active)
            has_media = any(s.label == "MEDIA_AUDIO" for s in segs)
            has_speech = any(s.label == "BOAT_SPEECH" for s in segs)
            self.assertTrue(has_media, f"Chunk {chunk_idx} has no MEDIA_AUDIO segments")
            self.assertTrue(has_speech, f"Chunk {chunk_idx} has no BOAT_SPEECH segments")





