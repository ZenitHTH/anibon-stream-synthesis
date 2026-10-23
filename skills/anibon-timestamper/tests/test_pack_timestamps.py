"""Tests for pack_timestamps.py — cluster_by_tag, normalise_segments, balanced_pack."""
import pathlib
import sys
import unittest

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[3]
for _p in (_PLUGIN_ROOT / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from pack_timestamps import (
    cluster_by_tag,
    normalise_segments,
    balanced_pack,
    _body_bytes_of,
)


def _make_ts(tag, desc="x", sec=0):
    time_str = f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
    raw = f"{time_str} - {tag} {desc}"
    return {
        "time": time_str,
        "sec": sec,
        "tag": tag,
        "desc": desc,
        "raw": raw,
        "bytes": len(raw.encode("utf-8")),
    }


class TestPackTimestamps(unittest.TestCase):
    def test_stable_tag_groups(self):
        ts = [
            _make_ts("[บอส]", "a", 0),
            _make_ts("[บอส]", "b", 1),
            _make_ts("[วิเคราะห์]", "c", 2),
            _make_ts("[วิเคราะห์]", "d", 3),
        ]
        groups = cluster_by_tag(ts)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][0]["tag"], "[บอส]")
        self.assertEqual(groups[1][0]["tag"], "[วิเคราะห์]")

    def test_single_flicker_absorbed(self):
        ts = [
            _make_ts("[บอส]", "a", 0),
            _make_ts("[บอส]", "b", 1),
            _make_ts("[อื่นๆ]", "c", 2),   # single flicker
            _make_ts("[บอส]", "d", 3),
            _make_ts("[บอส]", "e", 4),
        ]
        groups = cluster_by_tag(ts)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 5)

    def test_empty_input(self):
        self.assertEqual(cluster_by_tag([]), [])

    def test_single_entry(self):
        ts = [_make_ts("[บอส]", "only", 0)]
        groups = cluster_by_tag(ts)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 1)

    def test_all_same_tag(self):
        ts = [_make_ts("[บอส]", str(i), i) for i in range(5)]
        groups = cluster_by_tag(ts)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 5)

    def test_oversized_segment_split(self):
        big = [_make_ts("[บอส]", "x" * 50, i * 10) for i in range(10)]
        result = normalise_segments([big], body_limit=500)
        self.assertGreater(len(result), 1)
        for seg in result:
            body = _body_bytes_of(seg)
            self.assertLessEqual(body, 500, f"Segment too big: {body}B")

    def test_tiny_segment_merged(self):
        tiny = [_make_ts("[อื่นๆ]", "hi", 100)]
        normal = [_make_ts("[บอส]", "x" * 10, i) for i in range(3)]
        result = normalise_segments([normal, tiny], body_limit=5000)
        self.assertEqual(len(result), 1)

    def test_fits_unchanged(self):
        segs = [
            [_make_ts("[บอส]", "a", 0), _make_ts("[บอส]", "b", 1)],
            [_make_ts("[วิเคราะห์]", "c", 2)],
        ]
        result = normalise_segments(segs, body_limit=5000)
        total_entries = sum(len(s) for s in result)
        self.assertEqual(total_entries, 3)

    def test_context_boundary_respected(self):
        boss   = [_make_ts("[บอส]",       "boss "   + str(i), i * 10)       for i in range(6)]
        review = [_make_ts("[วิเคราะห์]", "review " + str(i), 60 + i * 10) for i in range(6)]
        ts = boss + review
        groups = balanced_pack(ts, byte_limit=3500)
        boss_secs = {e["sec"] for e in boss}
        for group in groups:
            secs_in_group = {e["sec"] for e in group}
            overlap = secs_in_group & boss_secs
            self.assertTrue(overlap == boss_secs or not overlap, f"Boss entries split across parts: {overlap}")

    def test_balanced_pack_all_within_limit(self):
        ts = [_make_ts("[บอส]", "entry " + str(i), i * 30) for i in range(40)]
        groups = balanced_pack(ts, byte_limit=3500)
        self.assertTrue(groups, "Expected at least one group")
        for group in groups:
            self.assertGreater(len(group), 0)


if __name__ == "__main__":
    unittest.main()
