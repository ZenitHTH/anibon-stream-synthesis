import sqlite3
import tempfile
import unittest
from pathlib import Path
from process.knowledge.domain_db import DEFAULT_YGO_DB, DEFAULT_FGO_DB, DEFAULT_POKE_DB


def _make_fgo_db(tmp_dir: str, with_np: bool = False) -> Path:
    db = Path(tmp_dir) / "atlas_fgo.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE basic_servant "
            "(id INTEGER PRIMARY KEY, name TEXT, className TEXT, rarity INTEGER)"
        )
        conn.execute(
            "INSERT INTO basic_servant (id, name, className, rarity) "
            "VALUES (1, 'Oberon', 'pretender', 5)"
        )
        conn.execute(
            "INSERT INTO basic_servant (id, name, className, rarity) "
            "VALUES (2, 'Mash Kyrielight', 'shielder', 4)"
        )
        if with_np:
            conn.execute(
                "CREATE TABLE servant_np "
                "(servant_id INTEGER PRIMARY KEY, np_name TEXT, np_card TEXT)"
            )
            conn.execute(
                "INSERT INTO servant_np (servant_id, np_name, np_card) "
                "VALUES (1, 'Lie Like Vortigern', 'buster')"
            )
    return db


class TestDomainDB(unittest.TestCase):
    def test_query_ygo_by_archetype(self):
        if not DEFAULT_YGO_DB.is_file():
            self.skipTest("SQLite DB not present")
        from process.knowledge.domain_db import query_ygo_by_archetype
        cards = query_ygo_by_archetype("Raidraptor", limit=5)
        self.assertGreater(len(cards), 0)
        self.assertTrue(all("Raidraptor" in c for c in cards))

    def test_query_fgo_servants(self):
        if not DEFAULT_FGO_DB.is_file():
            self.skipTest("SQLite DB not present")
        from process.knowledge.domain_db import query_fgo_servants
        servants = query_fgo_servants(["Oberon", "Morgan"])
        self.assertGreater(len(servants), 0)
        names = [s["name"] for s in servants]
        self.assertTrue("Oberon" in names or "Morgan" in names)
        for s in servants:
            self.assertIn("className", s)

    def test_query_fgo_servants_with_np_table(self):
        from process.knowledge.domain_db import query_fgo_servants
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_fgo_db(tmp, with_np=True)
            result = query_fgo_servants(["oberon"], db_path=db)
            self.assertEqual(
                result,
                [{
                    "name": "Oberon",
                    "className": "pretender",
                    "rarity": 5,
                    "np_name": "Lie Like Vortigern",
                    "np_card": "buster",
                }],
            )

    def test_query_fgo_servants_with_np_table_missing_np_row(self):
        from process.knowledge.domain_db import query_fgo_servants
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_fgo_db(tmp, with_np=True)
            result = query_fgo_servants(["mash kyrielight"], db_path=db)
            self.assertEqual(
                result,
                [{
                    "name": "Mash Kyrielight",
                    "className": "shielder",
                    "rarity": 4,
                    "np_name": "",
                    "np_card": "",
                }],
            )

    def test_query_fgo_servants_without_np_table(self):
        from process.knowledge.domain_db import query_fgo_servants
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_fgo_db(tmp, with_np=False)
            result = query_fgo_servants(["oberon"], db_path=db)
            self.assertEqual(
                result,
                [{"name": "Oberon", "className": "pretender", "rarity": 5}],
            )

    def test_query_pokemon(self):
        if not DEFAULT_POKE_DB.is_file():
            self.skipTest("SQLite DB not present")
        from process.knowledge.domain_db import query_pokemon
        p = query_pokemon("Garchomp")
        self.assertIsNotNone(p)
        self.assertEqual(p["name_en"], "Garchomp")
        self.assertIn("กาเบรียส", p["name_th_official"])

    def test_resolve_entities_for_chunk(self):
        if not DEFAULT_YGO_DB.is_file():
            self.skipTest("SQLite DB not present")
        from process.knowledge.domain_db import resolve_entities_for_chunk
        chunk_text = "ปู่โบ๊ตวิเคราะห์เด็ค เรดแรปเตอร์ เจอขัดด้วย แม็กซ์ ซี แต่ยังกาง อัลทิเมตฟอลคอน ได้"
        entities = resolve_entities_for_chunk(chunk_text, max_entities=12)
        self.assertGreater(len(entities), 0)
        self.assertTrue(any("Raidraptor" in e for e in entities))
        self.assertLessEqual(len(entities), 12)


if __name__ == "__main__":
    unittest.main()
