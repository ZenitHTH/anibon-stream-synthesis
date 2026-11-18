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

    def test_prompts_enforce_topic_start_anchor_and_short_headline(self):
        chunks = [
            {"_idx": 0, "items": [{"start": 0, "timestamp": "00:00:00", "text": "เดี๋ยวพูดเรื่องเกมใหม่"}]}
        ]
        rec_prompt = build_recursive_prompt(
            chunk=chunks[0],
            current_topic="เริ่มสตรีม",
            rolling_summary="",
            lang="th",
        )
        self.assertIn("TOPIC START ANCHOR (LEAD-IN RULE - CRITICAL)", rec_prompt)
        self.assertIn("8-16 words (50-95 Thai characters)", rec_prompt)
        self.assertIn("NEVER prepend 'เฝ้า <Game/Action> พร้อม...'", rec_prompt)

        grp_prompt = build_group_prompt(
            chunks=chunks,
            group_idx=0,
            prev_tail="",
            lang="th",
            signals_map={},
            workspace=Path(self.tmp_dir.name),
        )
        self.assertIn("TOPIC START ANCHOR (LEAD-IN RULE - CRITICAL)", grp_prompt)
        self.assertIn("8-16 words (50-95 Thai characters)", grp_prompt)

    def test_build_recursive_prompt_injects_gap_predicate_when_elapsed_over_threshold(self):
        chunk = {
            "_idx": 45,
            "items": [{"timestamp": "03:22:40", "start": 12160.0, "text": "ผมไม่รีบรัดดาเมจแล้วกันเพราะไม่รู้เฟสสองทำอะไรได้"}]
        }
        recent = ["03:12:35 - [Gameplay] ปรับกลยุทธ์เน้นทำดาเมจใส่บอสแทนการตั้งรับ"]
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="ปะทะบอสด่านน้ำแข็ง",
            rolling_summary="สู้บอสต่อเนื่อง",
            lang="th",
            recent_timestamps=recent,
        )
        self.assertIn("GAP PREDICATE:", prompt)
        self.assertIn("10 minutes elapsed since last timestamp (03:12:35)", prompt)

    def test_build_recursive_prompt_omits_gap_predicate_when_recent(self):
        chunk = {
            "_idx": 45,
            "items": [{"timestamp": "03:22:40", "start": 12160.0, "text": "ตีบอสต่อ"}]
        }
        recent = ["03:18:00 - [Gameplay] ปรับกลยุทธ์เน้นทำดาเมจใส่บอสแทนการตั้งรับ"]
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="ปะทะบอสด่านน้ำแข็ง",
            rolling_summary="สู้บอสต่อเนื่อง",
            lang="th",
            recent_timestamps=recent,
        )
        self.assertNotIn("GAP PREDICATE:", prompt)

    def test_prompts_use_positive_three_slot_headline_recipe(self):
        chunks = [
            {"_idx": 0, "items": [{"start": 0, "timestamp": "00:00:00", "text": "ทดสอบพัดขนนกยูง"}]}
        ]
        rec_prompt = build_recursive_prompt(
            chunk=chunks[0],
            current_topic="เริ่มสตรีม",
            rolling_summary="",
            lang="th",
        )
        self.assertIn("HEADLINE RECIPE (3 REQUIRED SLOTS", rec_prompt)
        self.assertIn("STRICT VERB DIVERSITY", rec_prompt)
        self.assertIn("NO HALLUCINATED SUBTITLES CONSTRAINT", rec_prompt)
        self.assertIn("Rise of a Legend", rec_prompt)

    def test_build_recursive_prompt_injects_preroll_and_watchparty_guards(self):
        chunk = {
            "_idx": 0,
            "items": [{"timestamp": "00:00:00", "start": 0.0, "text": "เฮ ป อา"}],
        }
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="",
            rolling_summary="",
            lang="th",
        )
        self.assertIn("PRE-ROLL STANDBY / OPENING RULE", prompt)
        self.assertIn("00:00:00 - [Intro]", prompt)
        self.assertIn("ACTIVE GAME & WATCHPARTY GROUND TRUTH", prompt)
        self.assertIn("BROADCAST HIATUS VS. STREAMER SCHEDULE GUARD", prompt)

    def test_build_recursive_prompt_guards_visual_hud_and_premature_victory(self):
        chunk = {
            "_idx": 1,
            "items": [{"timestamp": "01:00:00", "start": 3600.0, "text": "ตีบอสต่อ"}],
        }
        kf = [("01:01:00", "dummy_b64", "frame")]
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="สู้บอส",
            rolling_summary="",
            lang="th",
            keyframes=kf,
        )
        self.assertIn("STRICT VISUAL HUD & BOSS NAME GROUNDING", prompt)
        self.assertIn("VICTORY GUARD (STRICT)", prompt)
        self.assertIn("จนจบการต่อสู้", prompt)
        self.assertIn("EMOTIONAL TONE MATCHING (CRITICAL)", prompt)
        self.assertIn("ฟิวส์ขาด", prompt)

    def test_prompts_instruct_splitting_distinct_reaction_onsets(self):
        chunk = {"_idx": 1, "items": [{"timestamp": "03:04:10", "start": 11050.0, "text": "test"}]}
        rec = build_recursive_prompt(chunk=chunk, current_topic="Gaming", rolling_summary="ok")
        grp = build_group_prompt(
            chunks=[chunk],
            group_idx=0,
            prev_tail="",
            lang="th",
            signals_map={},
            workspace=Path(self.tmp_dir.name),
        )
        self.assertIn("REACTION VISUAL ONSET", rec)
        self.assertIn("REACTION VISUAL ONSET", grp)

    def test_coalesce_chunk_items_reduces_line_count_without_dropping_words(self):
        from process.prompts import coalesce_chunk_items
        items = [
            {"start": i * 2, "timestamp": f"00:{(i*2)//60:02d}:{(i*2)%60:02d}", "text": f"คำที่{i}"}
            for i in range(120)
        ]
        lines = coalesce_chunk_items(items, max_lines=65)
        self.assertLessEqual(len(lines), 65)
        joined = "\n".join(lines)
        for i in range(120):
            self.assertIn(f"คำที่{i}", joined)
        self.assertTrue(lines[0].startswith("(00:00:00)"))


if __name__ == "__main__":
    unittest.main()


