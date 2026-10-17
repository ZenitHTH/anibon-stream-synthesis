import json
import tempfile
import unittest
from pathlib import Path


class TestPipelineE2E(unittest.TestCase):
    def test_pipeline_generates_entity_glossary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("ทักทายผู้ชม", encoding="utf-8")
            (tmp_path / "signals.json").write_text("{}", encoding="utf-8")

            from process_chunks_local import run_knowledge_discovery
            glossary_path = run_knowledge_discovery(tmp_path)
            self.assertTrue(glossary_path.exists())

    def test_audit_timestamps_replaces_known_variants(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            from process_chunks_local import audit_timestamps_against_glossary
            ts_file = tmp_path / "anibon_timestamps.md"
            ts_file.write_text("00:05:00 - [Game] เล่น นครโตะ กำลังฟาร์ม", encoding="utf-8")
            glossary = {
                "Naucrate": {"en": "Naucrate", "th": "นอคราเต้", "alias_th": "นครโตะ"}
            }
            count = audit_timestamps_against_glossary(ts_file, glossary)
            self.assertGreater(count, 0)
            content = ts_file.read_text(encoding="utf-8")
            self.assertIn("นอคราเต้", content)

    def test_sanitize_and_audit_timestamps_cleans_hallucinations_and_drift(self):
        from process_chunks_local import sanitize_and_audit_timestamps
        raw_md = (
            "═════════════════════════════════════════════════════════\n"
            " ส่วนที่ 1: เม้าท์มอยกับผู้ชม (⏱ เริ่ม: 00:00:00)\n"
            "═════════════════════════════════════════════════════════\n"
            "00:00:00 - [Talk] ปู่บอทกล่าวทักทายผู้ชม\n"
            "00:05:00 - [Talk] เม้าท์มอยเรื่องซีรีส์ Archen และตัวละคร Victor\n"
            "00:10:00 - [Gameplay] เล่นตัวละคร Uhlom สายต่อย\n"
        )
        glossary = {"Abrams": {"en": "Abrams", "th": "เอแบรห์มส์"}}
        garbled = [
            {"correct": "Arcane", "patterns": ["Archen"]},
            {"correct": "Viktor", "patterns": ["Victor"]},
        ]
        cleaned_md, stats = sanitize_and_audit_timestamps(raw_md, glossary=glossary, signals={}, garbled=garbled)
        self.assertIn("ปู่โบ๊ตกล่าวทักทายผู้ชม", cleaned_md)
        self.assertIn("ซีรีส์ Arcane และตัวละคร Viktor", cleaned_md)
        self.assertIn("Uhlom", stats["suspected_hallucinations"])
        self.assertGreater(stats["corrections_applied"], 0)

    def test_full_pipeline_simulation_with_stream_and_game_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            from signal_detector import detect_signals_for_chunks
            from process_chunks_local import run_knowledge_discovery
            from anibon.prompts import load_world_identity_context, build_recursive_prompt

            # 1. Setup mock chunks in workspace
            chunks_dir = tmp_path / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("(00:00:10) เล่นเกม Zelda ด้วย Joy-Con สนุกมาก", encoding="utf-8")
            (chunks_dir / "chunk_01.txt").write_text("(00:05:00) วิเคราะห์ตัวละคร Limbus Company และ Meursault Canto X", encoding="utf-8")

            # 2. Run signal detection
            signals_map = detect_signals_for_chunks(tmp_path)
            self.assertIn("chunk_00", signals_map)
            self.assertIn("chunk_01", signals_map)

            # 3. Run knowledge discovery
            glossary_path = run_knowledge_discovery(tmp_path, signals_map)
            self.assertTrue(glossary_path.exists())
            glossary = json.loads(glossary_path.read_text(encoding="utf-8"))

            # 4. Verify stream-type knowledge resolved in prompt for chunk_00
            sig_00 = signals_map["chunk_00"]
            ctx_00 = load_world_identity_context(sig_00)
            self.assertGreater(len(ctx_00), 0)

            # 5. Verify game-specific knowledge resolved in prompt for chunk_01
            sig_01 = signals_map["chunk_01"]
            ctx_01 = load_world_identity_context(sig_01)
            self.assertGreater(len(ctx_01), 0)
            self.assertIn("Limbus_Company", ctx_01)

            # 6. Verify prompt builds with injected knowledge context
            prompt = build_recursive_prompt(
                chunk={"_idx": 0, "items": [{"timestamp": "00:00:10", "start": 10.0, "text": "เล่นเกม Zelda"}]},
                current_topic="เล่นเกม",
                rolling_summary="สรุป",
                lang="th",
                world_identity_ref=ctx_00,
                glossary=glossary,
            )
            self.assertIn("WORLD IDENTITY REFERENCE", prompt)

    def test_finalize_and_assemble_timestamps_helper_exists(self):
        from process_chunks_local import finalize_and_assemble_timestamps
        self.assertTrue(callable(finalize_and_assemble_timestamps))

    def test_finalize_does_not_split_by_default(self):
        import tempfile
        from pathlib import Path
        from process_chunks_local import finalize_and_assemble_timestamps

        stamps = [f"00:{i:02d}:00 - [Talk] " + ("ข" * 120) for i in range(30)]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            out_md, _ = finalize_and_assemble_timestamps(
                workspace=ws,
                all_timestamps=stamps,
                endpoint="http://127.0.0.1:1234",
                model="test-model",
                temperature=0.1,
                block_size=2400,
                no_summarizer_pass=True,
            )
            content = out_md.read_text(encoding="utf-8")
            blocks = [b for b in content.split("\n\n") if b.strip()]
            self.assertTrue(any(len(b.encode("utf-8")) > 3500 for b in blocks))

    def test_finalize_byte_cap_opt_in(self):
        import tempfile
        from pathlib import Path
        from process_chunks_local import finalize_and_assemble_timestamps

        stamps = [f"00:{i:02d}:00 - [Talk] " + ("ข" * 120) for i in range(30)]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            out_md, _ = finalize_and_assemble_timestamps(
                workspace=ws,
                all_timestamps=stamps,
                endpoint="http://127.0.0.1:1234",
                model="test-model",
                temperature=0.1,
                block_size=2400,
                no_summarizer_pass=True,
                byte_cap=True,
            )
            content = out_md.read_text(encoding="utf-8")
            for block in content.split("\n\n"):
                if block.strip():
                    self.assertLessEqual(len(block.encode("utf-8")), 3500)



if __name__ == "__main__":
    unittest.main()

