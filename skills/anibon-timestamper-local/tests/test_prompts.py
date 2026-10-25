import unittest
from pathlib import Path
import tempfile

from process.prompts import (
    load_world_identity_context,
    build_recursive_prompt,
    build_group_prompt,
    build_chunk_entity_context,
)



class TestPrompts(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ref_dir = Path(self.tmp_dir.name)
        # Create a mock reference file
        (self.ref_dir / "Honkai_Star_Rail.md").write_text("# Honkai Star Rail lore snippet", encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_load_world_identity_context(self):
        signal = {"best_file": "Honkai_Star_Rail.md", "confidence": 0.8}
        ctx = load_world_identity_context(signal, self.ref_dir)
        self.assertIn("WORLD IDENTITY REFERENCE", ctx)
        self.assertIn("Honkai Star Rail lore snippet", ctx)

    def test_load_world_identity_context_from_stream_references(self):
        signal = {"best_file": "references/stream/gaming-stream.md", "confidence": 1.0}
        ctx = load_world_identity_context(signal, self.ref_dir)
        self.assertIn("WORLD IDENTITY REFERENCE", ctx)
        self.assertIn("gaming-stream", ctx.lower())

    def test_build_recursive_prompt(self):
        chunk = {
            "_idx": 1,
            "items": [{"timestamp": "00:00:10", "start": 10.0, "text": "สวัสดีครับทุกคน"}]
        }
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="เริ่มต้นสตรีม",
            rolling_summary="ทักทายคนดู",
            lang="th",
            web_context="- Verified entity context",
        )
        self.assertIn('"timestamps": [', prompt)
        self.assertIn("VERIFIED EXTERNAL CONTEXT", prompt)
        self.assertIn("สวัสดีครับทุกคน", prompt)

    def test_build_group_prompt(self):
        chunks = [
            {"_idx": 0, "items": [{"start": 0, "duration": 300, "text": "Chunk 0"}]},
            {"_idx": 1, "items": [{"start": 300, "duration": 300, "text": "Chunk 1"}]},
        ]
        prompt = build_group_prompt(
            chunks=chunks,
            group_idx=0,
            prev_tail="",
            lang="th",
            signals_map={},
            workspace=Path(self.tmp_dir.name),
        )
        self.assertIn("Group 0", prompt)
        self.assertIn("00:00:00 - 00:10:00", prompt)

    def test_build_chunk_entity_context_filters_relevant_entities(self):
        glossary = {
            "Maribell": {"th": "มาริเบล", "role": "Vanguard"},
            "Kayron": {"th": "ไครอน", "role": "Psionic"},
            "Ashiya Douman": {"th": "อาชิยะ โดมัน", "class": "alterEgo"},
        }
        chunk_text = "ตอนนี้มาริเบลใช้สกิลเกราะหนามากครับ"
        context = build_chunk_entity_context(chunk_text, glossary)
        self.assertIn("Maribell (มาริเบล)", context)
        self.assertNotIn("Ashiya Douman", context)

    def test_prompts_contain_anti_guessing_and_streamer_invariants(self):
        chunks = [
            {"_idx": 0, "start_sec": 0, "end_sec": 300, "items": [{"start": 0, "timestamp": "00:00:00", "text": "hello"}]}
        ]
        group_prompt = build_group_prompt(
            chunks=chunks,
            group_idx=0,
            prev_tail="",
            lang="th",
            signals_map={},
            workspace=Path(self.tmp_dir.name),
        )
        self.assertIn("ปู่โบ๊ต", group_prompt)
        self.assertIn("ห้ามสะกดว่า 'ปู่บอท'", group_prompt)
        self.assertIn("ห้ามแปลคำทับศัพท์ภาษาไทยเป็นภาษาอังกฤษโดยพลการ", group_prompt)

        rec_prompt = build_recursive_prompt(
            chunk=chunks[0],
            current_topic="Test",
            rolling_summary="",
            lang="th",
        )
        self.assertIn("ปู่โบ๊ต", rec_prompt)
        self.assertIn("ห้ามสะกดว่า 'ปู่บอท'", rec_prompt)
        self.assertIn("ห้ามแปลคำทับศัพท์ภาษาไทยเป็นภาษาอังกฤษโดยพลการ", rec_prompt)

    def test_build_recursive_prompt_injects_candidate_weights_and_standing_word_guard(self):
        chunk = {
            "_idx": 17,
            "items": [{"timestamp": "01:16:36", "start": 4596.0, "text": "ตัวใหม่ C5 เปิดพเนอร์ รอซึวสึ E2"}]
        }
        signal = {
            "best_file": "../anibon-world-identity/references/Chaos_Zero_Nightmare.md",
            "primary_topic": "Chaos Zero Nightmare",
            "confidence": 0.91,
            "special_keywords": ["พเนอร์", "รอซึวสึ"],
            "standing_keywords": ["c5", "e2"],
            "candidates": [
                {"file": "Chaos_Zero_Nightmare.md", "topic": "Chaos Zero Nightmare", "weight": 34.2, "prob": 0.91, "keywords": ["พเนอร์", "รอซึวสึ"]},
            ],
        }
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="เล่น Chaos Zero Nightmare",
            rolling_summary="ปู่โบ๊ตเปิดกาชา",
            lang="th",
            signal=signal,
        )
        self.assertIn("CANDIDATE DOMAIN WEIGHTS", prompt)
        self.assertIn("Chaos Zero Nightmare: weight=34.2 (91%)", prompt)
        self.assertIn("พเนอร์, รอซึวสึ", prompt)
        self.assertIn("GENERIC GAMING STANDING WORDS", prompt)
        self.assertNotIn("e.g. Wuthering Waves", prompt)

    def test_build_chunk_entity_context_filters_by_allowed_sources(self):
        glossary = {
            "Yuki": {"th": "ยูกิ", "role": "Striker", "source_file": "Chaos_Zero_Nightmare.md"},
            "Hoshino": {"th": "โฮชิโนะ", "role": "Tank", "source_file": "Blue_Archive.md"},
        }
        ctx = build_chunk_entity_context("ยูกิ กับ โฮชิโนะ", glossary, allowed_sources={"Chaos_Zero_Nightmare.md"})
        self.assertIn("Yuki", ctx)
        self.assertNotIn("Hoshino", ctx)

    def test_build_chunk_entity_context_filters_db_sources_with_source_attribute(self):
        glossary = {
            "Ashiya Douman": {"th": "อาชิยะ โดมัน", "class": "alterEgo", "source": "atlas_fgo.db"},
            "Maribell": {"th": "มาริเบล", "role": "Vanguard", "source_file": "Chaos_Zero_Nightmare.md"},
        }
        ctx = build_chunk_entity_context("มาริเบล กับ อาชิยะ โดมัน", glossary, allowed_sources={"Chaos_Zero_Nightmare.md"})
        self.assertIn("Maribell", ctx)
        self.assertNotIn("Ashiya Douman", ctx)

    def test_build_recursive_prompt_thresholds_allowed_sources(self):
        chunk = {
            "_idx": 17,
            "items": [{"timestamp": "01:16:36", "start": 4596.0, "text": "ตัวใหม่ มาริเบล C5 โฮชิโนะ"}]
        }
        signal = {
            "best_file": "Chaos_Zero_Nightmare.md",
            "candidates": [
                {"file": "Chaos_Zero_Nightmare.md", "prob": 0.95},
                {"file": "Blue_Archive.md", "prob": 0.05},
            ],
        }
        glossary = {
            "Maribell": {"th": "มาริเบล", "role": "Vanguard", "source_file": "Chaos_Zero_Nightmare.md"},
            "Hoshino": {"th": "โฮชิโนะ", "role": "Tank", "source_file": "Blue_Archive.md"},
        }
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="Test",
            rolling_summary="",
            lang="th",
            signal=signal,
            glossary=glossary,
        )
        self.assertIn("Maribell", prompt)
        self.assertNotIn("Hoshino", prompt)

    def test_build_recursive_prompt_includes_recent_timestamps_and_mid_chunk_shift_rule(self):
        chunk = {
            "_idx": 5,
            "items": [{"timestamp": "00:20:00", "start": 1200.0, "text": "เปลี่ยนมาดูเกมใหม่กันครับ"}]
        }
        recent = [
            "00:12:00 - [WatchParty] ส่องตัวอย่างเกมแรก",
            "00:16:30 - [Talk] วิเคราะห์ระบบกาชา",
        ]
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="วิเคราะห์ระบบกาชา",
            rolling_summary="คุยเรื่องเรทกาชา -> เปรียบเทียบราคาสกิน",
            lang="th",
            recent_timestamps=recent,
        )
        self.assertIn("Recent Emitted Timestamps", prompt)
        self.assertIn("00:16:30 - [Talk] วิเคราะห์ระบบกาชา", prompt)
        self.assertIn("mid-chunk", prompt.lower())


if __name__ == "__main__":
    unittest.main()

