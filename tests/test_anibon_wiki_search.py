"""Regression tests for anibon_wiki multi-term search and CLI integration."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "anibon_wiki" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wiki_search import SearchSpec, hms_to_seconds, search_wiki, spec_from_json  # noqa: E402


def _seed_wiki(root: Path) -> None:
    """Create minimal synthetic anibon_wiki layout inside tmp dir."""
    (root / "wiki" / "games").mkdir(parents=True)
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "wiki" / "_templates").mkdir(parents=True)
    (root / "raw" / "streams").mkdir(parents=True)

    (root / "wiki" / "index.md").write_text("# Index\n- [[roblox]]\n", encoding="utf-8")
    (root / "wiki" / "_templates" / "tpl.md").write_text("Roblox template\n", encoding="utf-8")
    (root / "wiki" / "games" / "roblox.md").write_text(
        '---\ntitle: "Roblox"\ncategory: "game"\ntags: ["game", "roblox"]\n---\n\n'
        "## Overview\n- เล่น Roblox RP 5 ชั่วโมง (`02:44:32`)\n",
        encoding="utf-8",
    )
    (root / "wiki" / "sources" / "stream-abc12345678.md").write_text(
        '---\ntitle: "Stream abc12345678 — Roblox & FGO"\ncategory: "source"\n'
        'video_id: "abc12345678"\nupload_date: "2026-09-15"\ntags: ["stream", "roblox", "fgo"]\n---\n\n'
        "## Curated Timeline\n- `01:02:03` — [Game] ปู่โบ๊ตเล่น Roblox สภาไทย\n",
        encoding="utf-8",
    )
    (root / "wiki" / "sources" / "stream-old99999999.md").write_text(
        '---\ntitle: "Stream old99999999 — Old FGO"\ncategory: "source"\n'
        'video_id: "old99999999"\nupload_date: "2025-01-10"\ntags: ["stream", "fgo"]\n---\n\n'
        "## Curated Timeline\n- `00:10:00` — [FGO] สุ่มกาชา FGO\n",
        encoding="utf-8",
    )
    (root / "raw" / "streams" / "stream-abc12345678.md").write_text(
        "# Raw Stream Snapshot: abc12345678\n- 00:05:00 - ปู่บอทพูดเรื่อง มาตรา 112 และ Trees Hate You\n",
        encoding="utf-8",
    )


class TestAnibonWikiSearch(unittest.TestCase):
    def test_hms_to_seconds(self) -> None:
        self.assertEqual(hms_to_seconds("01:02:03"), 3723)
        self.assertEqual(hms_to_seconds("00:00:45"), 45)

    def test_synthesis_ranks_above_stream_and_skips_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_wiki(root)
            res = search_wiki(root, SearchSpec(terms=("Roblox", "NonExistent")))
            self.assertEqual(res["total_hits"], 2)
            self.assertEqual(res["results"][0]["tier"], "synthesis")
            self.assertEqual(res["results"][1]["tier"], "stream")
            self.assertEqual(
                res["results"][1]["matches"][0]["youtube_url"],
                "https://www.youtube.com/watch?v=abc12345678&t=3723",
            )

    def test_date_and_tag_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_wiki(root)
            spec = spec_from_json(json.dumps({
                "terms": ["FGO"],
                "tags": ["fgo"],
                "date": {"from": "2026-01-01", "to": "2026-12-31"},
            }))
            res = search_wiki(root, spec)
            self.assertEqual([r["video_id"] for r in res["results"]], ["abc12345678"])

    def test_raw_fallback_and_masking_sanitization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_wiki(root)
            off = search_wiki(root, SearchSpec(terms=("Trees Hate You",), include_raw=False))
            self.assertEqual(off["total_hits"], 0)
            on = search_wiki(root, SearchSpec(terms=("Trees Hate You",), include_raw=True))
            self.assertEqual(on["total_hits"], 1)
            snippet = on["results"][0]["matches"][0]["text"]
            self.assertIn("ปู่โบ๊ต", snippet)
            self.assertIn("กฎหมายแมรี่จัวส์", snippet)
            self.assertNotIn("ปู่บอท", snippet)
            self.assertNotIn("มาตรา 112", snippet)

    def test_cli_json_search_against_real_wiki(self) -> None:
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "wiki_tool.py"),
            "search",
            "--terms",
            "Roblox",
            "โรบล็อก",
            "--limit",
            "5",
            "--json",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(proc.stdout)
        self.assertGreater(payload["coverage"]["total_streams"], 100)
        self.assertGreaterEqual(payload["total_hits"], 1)
        self.assertEqual(payload["results"][0]["slug"], "roblox")


if __name__ == "__main__":
    unittest.main()
