"""Tests for detect_signals.py — rarity-weighted (IDF) topic detection."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from detect_signals import compute_idf_stats, _process_single_chunk


# ─────────────────────────────────────────────────────────────
# compute_idf_stats — rarity weighting
# ─────────────────────────────────────────────────────────────

def test_daily_word_zero_weight_rare_word_positive():
    # "common" appears in every chunk (df=2, ambient), "rare" only once (df=1).
    entries = {"common": {"kind": "topic", "file": "talk.md"}, "rare": {"kind": "game", "file": "game.md"}}
    corpus = ["common only here common", "common and rare"]
    stats = compute_idf_stats(corpus, entries)
    assert stats["common"]["df"] == 2
    assert stats["common"]["idf"] == 0.0
    assert stats["rare"]["df"] == 1
    assert stats["rare"]["idf"] > 0.0
    assert "absent" not in stats  # keyword never seen -> omitted


def test_process_chunk_picks_rare_best_file():
    entries = {k: {"kind": k, "file": f"{k}.md"} for k in ("ambient", "boss_rare")}
    corpus = ["ambient boss_rare ambient", "ambient"]
    stats = compute_idf_stats(corpus, entries)
    _, res, matched = _process_single_chunk(("c0", 0, "ambient boss_rare boss_rare"), entries, stats, 2)
    assert matched is True

    assert res["best_file"] == "boss_rare.md"
    assert res["primary_topic"] == "Boss Rare (boss_rare)"
    assert res["confidence"] == 1.0
    # back-compat fields preserved
    assert "signal_score" in res
    assert "matched_files" in res
    # ambient (df high, weight 0) scores 0 and never becomes best
    assert res["weighted_matched_files"][0]["file"] == "boss_rare.md"
    assert next(ent["weight"] for ent in res["matched_files"] if ent["file"] == "ambient.md") == 0.0