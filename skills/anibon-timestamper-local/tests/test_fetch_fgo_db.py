import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "anibon-world-identity" / "scripts" / "fetch_fgo_db.py"
spec = importlib.util.spec_from_file_location("fetch_fgo_db", SCRIPT_PATH)
fetch_fgo_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_fgo_db)


class TestFetchFgoDbNp(unittest.TestCase):
    def test_extract_servant_np_rows_valid_and_edge_cases(self):
        sample = [
            {"id": 100100, "noblePhantasms": [{"name": "Excalibur", "card": "buster"}]},
            {"id": 100200, "noblePhantasms": []},
            {"id": 100300},
            {"id": 100400, "noblePhantasms": [{"name": None, "card": "arts"}]},
            {"id": 100500, "noblePhantasms": [{"name": "Garden of Avalon"}]},
            {"noblePhantasms": [{"name": "Missing Id", "card": "quick"}]},
        ]
        rows = fetch_fgo_db.extract_servant_np_rows(sample)
        self.assertEqual(
            rows,
            [
                {"servant_id": 100100, "np_name": "Excalibur", "np_card": "buster"},
                {"servant_id": 100400, "np_name": "", "np_card": "arts"},
                {"servant_id": 100500, "np_name": "Garden of Avalon", "np_card": ""},
            ],
        )

    def test_parse_args_with_np_flag(self):
        with mock.patch.object(sys, "argv", ["fetch_fgo_db.py", "--with-np"]):
            args = fetch_fgo_db._parse_args()
            self.assertTrue(args.with_np)

        with mock.patch.object(sys, "argv", ["fetch_fgo_db.py"]):
            args = fetch_fgo_db._parse_args()
            self.assertFalse(args.with_np)

    def test_has_table_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            self.assertFalse(fetch_fgo_db._has_table(db, "basic_servant"))
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE basic_servant (id INTEGER PRIMARY KEY)")
            con.close()
            self.assertTrue(fetch_fgo_db._has_table(db, "basic_servant"))
            self.assertFalse(fetch_fgo_db._has_table(db, "servant_np"))

    def test_build_db_default_skips_nice_servant_and_rebuilds_when_with_np_added(self):
        downloaded_urls = []

        def fake_download(url: str, **_kwargs):
            downloaded_urls.append(url)
            if url.endswith("nice_servant_lang_en.json"):
                return [
                    {"id": 100100, "noblePhantasms": [{"name": "Excalibur", "card": "buster"}]},
                    {"id": 100200, "noblePhantasms": []},
                ]
            if url.endswith("nice_trait.json") or url.endswith("nice_enums.json"):
                return {}
            return [{"id": 100100, "name": "Artoria"}]

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atlas_fgo.db"
            with mock.patch.object(fetch_fgo_db, "_get_remote_version", return_value="v1"), \
                 mock.patch.object(fetch_fgo_db, "_download_json", side_effect=fake_download):
                fetch_fgo_db.build_db(db)
                self.assertFalse(any("nice_servant_lang_en.json" in u for u in downloaded_urls))
                self.assertFalse(fetch_fgo_db._has_table(db, "servant_np"))

                downloaded_urls.clear()
                fetch_fgo_db.build_db(db, with_np=True)
                self.assertTrue(any("nice_servant_lang_en.json" in u for u in downloaded_urls))
                self.assertTrue(fetch_fgo_db._has_table(db, "servant_np"))

                con = sqlite3.connect(db)
                cols = con.execute("PRAGMA table_info(servant_np)").fetchall()
                rows = con.execute("SELECT servant_id, np_name, np_card FROM servant_np").fetchall()
                con.close()
                self.assertEqual([(c[1], c[2], c[5]) for c in cols], [
                    ("servant_id", "INTEGER", 1),
                    ("np_name", "TEXT", 0),
                    ("np_card", "TEXT", 0),
                ])
                self.assertEqual(rows, [(100100, "Excalibur", "buster")])

                downloaded_urls.clear()
                fetch_fgo_db.build_db(db, with_np=True)
                self.assertEqual(downloaded_urls, [])
