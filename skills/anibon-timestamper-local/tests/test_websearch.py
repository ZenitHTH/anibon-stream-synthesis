import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import json

from anibon.websearch import (
    load_search_cache,
    save_search_cache,
    build_entity_query,
    format_search_context,
    search_entity_context,
)


class TestWebSearch(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.tmp_dir.name) / "websearch_cache.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cache_save_and_load(self):
        data = {"genshin": [{"title": "Genshin Impact", "snippet": "An action RPG"}]}
        save_search_cache(self.cache_file, data)
        loaded = load_search_cache(self.cache_file)
        self.assertEqual(loaded, data)

    def test_build_entity_query(self):
        q1 = build_entity_query("Yinlin", "gaming")
        self.assertIn("Yinlin", q1)
        self.assertIn("wiki", q1)

        q2 = build_entity_query("Gavv", "tokusatsu")
        self.assertIn("Gavv", q2)
        self.assertTrue("kamen rider" in q2.lower() or "tokusatsu" in q2.lower())

    def test_format_search_context(self):
        results = [
            {"title": "Yinlin - Wuthering Waves Wiki", "snippet": "Yinlin is a 5-star Resonator."}
        ]
        ctx = format_search_context("Yinlin", results)
        self.assertIn("VERIFIED WEB CONTEXT", ctx)
        self.assertIn("Yinlin", ctx)
        self.assertIn("5-star Resonator", ctx)

    @patch("anibon.websearch.search_duckduckgo")
    def test_search_entity_context_caching(self, mock_search):
        mock_search.return_value = [
            {"title": "Result 1", "snippet": "Snippet 1", "url": "https://example.com"}
        ]
        # First call: cache miss -> calls search
        ctx1 = search_entity_context("TestEntity", domain="gaming", cache_file=self.cache_file)
        self.assertEqual(mock_search.call_count, 1)
        self.assertIn("Snippet 1", ctx1)

        # Second call: cache hit -> no search called
        ctx2 = search_entity_context("TestEntity", domain="gaming", cache_file=self.cache_file)
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(ctx1, ctx2)


if __name__ == "__main__":
    unittest.main()
