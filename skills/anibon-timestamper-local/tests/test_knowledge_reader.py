import sqlite3
import tempfile
import unittest
from pathlib import Path
from process.knowledge.reader import extract_entity_glossary, save_entity_glossary, enrich_with_sqlite_databases


class TestKnowledgeReader(unittest.TestCase):
    def test_extract_entity_glossary_from_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_dir = tmp_path / "references"
            ref_dir.mkdir()
            md_file = ref_dir / "Chaos_Zero_Nightmare.md"
            md_file.write_text(
                "# Chaos Zero Nightmare\n\n"
                "| ตัวละคร (Agent) | คลาส (Class) | ธาตุ (Attribute) |\n"
                "| :--- | :---: | :---: |\n"
                "| **Maribell (มาริเบล)** | Vanguard | Passion |\n"
                "| **Kayron (ไครอน)** | Psionic | Void |\n",
                encoding="utf-8"
            )
            signals_map = {
                "chunk_00": {
                    "best_file": "Chaos_Zero_Nightmare.md",
                    "weighted_files": [{"file": "Chaos_Zero_Nightmare.md", "score": 10.0}]
                }
            }
            glossary = extract_entity_glossary(signals_map, ref_dir)
            self.assertIn("Maribell", glossary)
            self.assertEqual(glossary["Maribell"]["th"], "มาริเบล")
            self.assertEqual(glossary["Maribell"]["class"], "Vanguard")
            self.assertIn("Kayron", glossary)
            self.assertEqual(glossary["Kayron"]["th"], "ไครอน")

    def test_save_entity_glossary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            glossary = {"Maribell": {"th": "มาริเบล"}}
            out_file = save_entity_glossary(glossary, tmp_path)
            self.assertTrue(out_file.exists())
            self.assertIn("Maribell", out_file.read_text(encoding="utf-8"))

    def test_enrich_with_fgo_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "atlas_fgo.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE basic_servant (name TEXT, className TEXT, rarity INTEGER)")
            conn.execute("INSERT INTO basic_servant VALUES ('Ashiya Douman', 'alterEgo', 5)")
            conn.commit()
            conn.close()

            signals_map = {
                "chunk_01": {
                    "best_file": "fgo-knowledge.md",
                    "matched_keywords": {"fgo": {"count": 2}}
                }
            }
            glossary = {}
            enriched = enrich_with_sqlite_databases(glossary, signals_map, fgo_db=db_path)
            self.assertIn("Ashiya Douman", enriched)
            self.assertEqual(enriched["Ashiya Douman"]["class"], "alterEgo")

    def test_enrich_with_pokemon_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "pokemon.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE pokemon (id INTEGER, name_en TEXT, name_ja TEXT, name_th_official TEXT, name_th_english_sound TEXT)")
            conn.execute("INSERT INTO pokemon VALUES (25, 'Pikachu', 'ピカチュウ', 'พิคาชู', 'ปิกาจู')")
            conn.commit()
            conn.close()

            signals_map = {
                "chunk_01": {
                    "best_file": "Pokemon_PvP.md",
                    "weighted_files": [{"file": "Pokemon_PvP.md", "score": 8.0}]
                }
            }
            glossary = {}
            enriched = enrich_with_sqlite_databases(glossary, signals_map, pokemon_db=db_path)
            self.assertIn("Pikachu", enriched)
            self.assertEqual(enriched["Pikachu"]["th"], "พิคาชู")

    def test_extract_entity_glossary_with_version_and_canto_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_dir = tmp_path / "references"
            ref_dir.mkdir()
            md_file = ref_dir / "Honkai_Star_Rail.md"
            md_file.write_text(
                "# Honkai: Star Rail\n\n"
                "| เวอร์ชัน | ตัวละคร | พาธ (Path) | ธาตุ |\n"
                "| :---: | :--- | :---: | :---: |\n"
                "| **4.3** | **Phainon (ไฟนอน)** | ล่าสังหาร (The Hunt) | ไฟ |\n"
                "| **Canto X** | **Meursault** | Vanguard | Ice |\n",
                encoding="utf-8"
            )
            signals_map = {
                "chunk_00": {
                    "best_file": "Honkai_Star_Rail.md",
                    "weighted_files": [{"file": "Honkai_Star_Rail.md", "score": 10.0}]
                }
            }
            glossary = extract_entity_glossary(signals_map, ref_dir)
            self.assertNotIn("4.3", glossary)
            self.assertNotIn("Canto X", glossary)
            self.assertIn("Phainon", glossary)
            self.assertEqual(glossary["Phainon"]["th"], "ไฟนอน")
            self.assertEqual(glossary["Phainon"]["role"], "ล่าสังหาร (The Hunt)")
            self.assertIn("Meursault", glossary)

    def test_extract_entity_glossary_resolves_stream_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_dir = tmp_path / "anibon-world-identity" / "references"
            ref_dir.mkdir(parents=True)
            stream_dir = tmp_path / "anibon-timestamper-local" / "references" / "stream"
            stream_dir.mkdir(parents=True)
            (stream_dir / "gaming-knowledge.md").write_text(
                "# Gaming Knowledge\n\n"
                "| คำศัพท์ | ความหมาย |\n"
                "| :--- | :--- |\n"
                "| **Joy-Con** | จอยสติ๊ก Switch |\n",
                encoding="utf-8"
            )

            signals_map = {
                "chunk_01": {
                    "best_file": "references/stream/gaming-knowledge.md",
                    "weighted_files": [{"file": "references/stream/gaming-knowledge.md", "score": 10.0}]
                }
            }
            glossary = extract_entity_glossary(signals_map, ref_dir, extra_ref_dirs=[stream_dir])
            self.assertIn("Joy-Con", glossary)

    def test_rule_docs_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stream_dir = tmp_path / "stream"
            stream_dir.mkdir()
            (stream_dir / "talk-stream.md").write_text(
                "- **Core Strategy**: Identify which topics the speaker flows into.\n\n"
                "| Guideline | Details | Action |\n"
                "| :--- | :--- | :--- |\n"
                "| **Direct royal naming** | โบ๊ทพูดถึง ร.10 | Mask immediately |\n",
                encoding="utf-8"
            )
            signals_map = {
                "chunk_00": {
                    "best_file": "talk-stream.md",
                    "weighted_files": [{"file": "talk-stream.md", "score": 10.0}]
                }
            }
            g = extract_entity_glossary(signals_map, ref_dir=stream_dir)
            self.assertNotIn("Core Strategy", g)
            self.assertNotIn("Direct royal naming", g)

    def test_stream_knowledge_files_still_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stream_dir = tmp_path / "stream"
            stream_dir.mkdir()
            (stream_dir / "fgo-knowledge.md").write_text(
                "# FGO Knowledge\n\n"
                "- **Ashiya Douman (อาชิยะ โดมัน)**: Caster / Alter Ego servant\n",
                encoding="utf-8"
            )
            signals_map = {
                "chunk_00": {
                    "best_file": "fgo-knowledge.md",
                    "weighted_files": [{"file": "fgo-knowledge.md", "score": 10.0}]
                }
            }
            g = extract_entity_glossary(signals_map, ref_dir=stream_dir)
            self.assertIn("Ashiya Douman", g)

    def test_parse_markdown_entities_excludes_generic_standing_words_but_keeps_characters_for_stage2(self):
        from process.knowledge.reader import parse_markdown_entities
        md = (
            "- **สมาชิก**: Maribell + Diana\n"
            "- **กลไก**: ใช้โล่สะท้อนดาเมจ\n"
            "- **เกลือ**: สุ่มไม่ติดหน้าตู้\n"
            "- **Parry (ปัดป้อง)**: กดกันจังหวะศัตรูตี\n"
            "- **Normal Mode**: โหมดปกติ\n"
            "- **E1**: ปลดล็อคขั้น 1\n"
            "- **Yuki (ยูกิ)**: ตัวละครสายโจมตี\n"
            "- **Rossweisse (รอสไวส์)**: ตัวละครใหม่\n"
        )
        ents = parse_markdown_entities(md)
        for generic in ("สมาชิก", "กลไก", "เกลือ", "Parry", "Normal Mode", "E1"):
            self.assertNotIn(generic, ents)
        self.assertIn("Yuki", ents)
        self.assertIn("Rossweisse", ents)

    def test_extract_entity_glossary_supports_multi_source_entities_and_scoping(self):
        from process.knowledge.reader import extract_entity_glossary
        from process.prompts import build_chunk_entity_context
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_dir = tmp_path / "references"
            ref_dir.mkdir()
            (ref_dir / "Blue_Archive.md").write_text("- **Mika (มิกะ)**: นักเรียนคิโวทอส\n", encoding="utf-8")
            (ref_dir / "Chaos_Zero_Nightmare.md").write_text("- **Mika (มิกะ)**: ตัวละคร CZN ซัพพอร์ต AP\n", encoding="utf-8")

            signals_map = {
                "chunk_00": {
                    "best_file": "Chaos_Zero_Nightmare.md",
                    "candidates": [{"file": "Chaos_Zero_Nightmare.md", "prob": 0.95}],
                    "weighted_files": [{"file": "Chaos_Zero_Nightmare.md", "score": 10.0}]
                }
            }
            glossary = extract_entity_glossary(signals_map, ref_dir)
            ctx = build_chunk_entity_context("มิกะ ใช้การ์ด AP", glossary, allowed_sources={"Chaos_Zero_Nightmare.md"})
            self.assertIn("Mika", ctx)
            self.assertIn("CZN", ctx)




if __name__ == "__main__":
    unittest.main()
