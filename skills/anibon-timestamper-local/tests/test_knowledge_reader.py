import sqlite3
import tempfile
import unittest
from pathlib import Path
from anibon.knowledge_reader import extract_entity_glossary, save_entity_glossary, enrich_with_sqlite_databases


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
            (stream_dir / "gaming-stream.md").write_text(
                "# Gaming Stream\n\n"
                "| คำศัพท์ | ความหมาย |\n"
                "| :--- | :--- |\n"
                "| **Joy-Con** | จอยสติ๊ก Switch |\n",
                encoding="utf-8"
            )

            signals_map = {
                "chunk_01": {
                    "best_file": "references/stream/gaming-stream.md",
                    "weighted_files": [{"file": "references/stream/gaming-stream.md", "score": 10.0}]
                }
            }
            glossary = extract_entity_glossary(signals_map, ref_dir, extra_ref_dirs=[stream_dir])
            self.assertIn("Joy-Con", glossary)


if __name__ == "__main__":
    unittest.main()
