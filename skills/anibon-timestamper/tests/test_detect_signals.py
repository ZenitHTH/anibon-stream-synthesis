"""Tests for detect_signals.py — rarity-weighted (IDF) topic detection."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from detect_signals import compute_idf_stats, _process_single_chunk


class TestDetectSignals(unittest.TestCase):
    def test_daily_word_zero_weight_rare_word_positive(self):
        # "common" appears in every chunk (df=2, ambient), "rare" only once (df=1).
        entries = {"common": {"kind": "topic", "file": "talk.md"}, "rare": {"kind": "game", "file": "game.md"}}
        corpus = ["common only here common", "common and rare"]
        stats = compute_idf_stats(corpus, entries)
        self.assertEqual(stats["common"]["df"], 2)
        self.assertEqual(stats["common"]["idf"], 0.0)
        self.assertEqual(stats["rare"]["df"], 1)
        self.assertGreater(stats["rare"]["idf"], 0.0)
        self.assertNotIn("absent", stats)

    def test_process_chunk_picks_rare_best_file(self):
        entries = {k: {"kind": k, "file": f"{k}.md"} for k in ("ambient", "boss_rare")}
        corpus = ["ambient boss_rare ambient", "ambient"]
        stats = compute_idf_stats(corpus, entries)
        _, res, matched = _process_single_chunk(("c0", 0, "ambient boss_rare boss_rare"), entries, stats, 2)
        self.assertTrue(matched)

        self.assertEqual(res["best_file"], "boss_rare.md")
        self.assertEqual(res["primary_topic"], "Boss Rare (boss_rare)")
        self.assertEqual(res["confidence"], 1.0)
        # back-compat fields preserved
        self.assertIn("signal_score", res)
        self.assertIn("matched_files", res)
        # ambient (df high, weight 0) scores 0 and never becomes best
        self.assertEqual(res["weighted_matched_files"][0]["file"], "boss_rare.md")
        self.assertEqual(next(ent["weight"] for ent in res["matched_files"] if ent["file"] == "ambient.md"), 0.0)


if __name__ == "__main__":
    unittest.main()