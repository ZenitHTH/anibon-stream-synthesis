import unittest
from pathlib import Path
import tempfile

from anibon.prompts import (
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



if __name__ == "__main__":
    unittest.main()
