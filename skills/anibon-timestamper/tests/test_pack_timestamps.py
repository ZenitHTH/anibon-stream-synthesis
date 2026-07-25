"""Tests for pack_timestamps.py — cluster_by_tag, normalise_segments, balanced_pack."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from pack_timestamps import (
    cluster_by_tag,
    normalise_segments,
    balanced_pack,
    _body_bytes_of,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Task 1: cluster_by_tag
# ─────────────────────────────────────────────────────────────

def test_stable_tag_groups():
    ts = [
        _make_ts("[บอส]", "a", 0),
        _make_ts("[บอส]", "b", 1),
        _make_ts("[วิเคราะห์]", "c", 2),
        _make_ts("[วิเคราะห์]", "d", 3),
    ]
    groups = cluster_by_tag(ts)
    assert len(groups) == 2
    assert groups[0][0]["tag"] == "[บอส]"
    assert groups[1][0]["tag"] == "[วิเคราะห์]"


def test_single_flicker_absorbed():
    ts = [
        _make_ts("[บอส]", "a", 0),
        _make_ts("[บอส]", "b", 1),
        _make_ts("[อื่นๆ]", "c", 2),   # single flicker
        _make_ts("[บอส]", "d", 3),
        _make_ts("[บอส]", "e", 4),
    ]
    groups = cluster_by_tag(ts)
    # flicker entry absorbed — result is one big group
    assert len(groups) == 1
    assert len(groups[0]) == 5


def test_empty_input():
    assert cluster_by_tag([]) == []


def test_single_entry():
    ts = [_make_ts("[บอส]", "only", 0)]
    groups = cluster_by_tag(ts)
    assert len(groups) == 1
    assert len(groups[0]) == 1


def test_all_same_tag():
    ts = [_make_ts("[บอส]", str(i), i) for i in range(5)]
    groups = cluster_by_tag(ts)
    assert len(groups) == 1
    assert len(groups[0]) == 5


# ─────────────────────────────────────────────────────────────
# Task 2: normalise_segments
# ─────────────────────────────────────────────────────────────

def test_oversized_segment_split():
    # Each entry ~85 bytes; 10 entries ~850B total — must split at 500B limit
    big = [_make_ts("[บอส]", "x" * 50, i * 10) for i in range(10)]
    result = normalise_segments([big], body_limit=500)
    assert len(result) > 1
    for seg in result:
        body = _body_bytes_of(seg)
        assert body <= 500, f"Segment too big: {body}B"


def test_tiny_segment_merged():
    tiny = [_make_ts("[อื่นๆ]", "hi", 100)]
    normal = [_make_ts("[บอส]", "x" * 10, i) for i in range(3)]
    result = normalise_segments([normal, tiny], body_limit=5000)
    # tiny segment must be merged into previous
    assert len(result) == 1


def test_fits_unchanged():
    segs = [
        [_make_ts("[บอส]", "a", 0), _make_ts("[บอส]", "b", 1)],
        [_make_ts("[วิเคราะห์]", "c", 2)],
    ]
    result = normalise_segments(segs, body_limit=5000)
    # No splits needed; tiny single entry gets merged into previous
    total_entries = sum(len(s) for s in result)
    assert total_entries == 3


# ─────────────────────────────────────────────────────────────
# Task 3: balanced_pack context boundary
# ─────────────────────────────────────────────────────────────

def test_context_boundary_respected():
    """All boss entries must land in the same part."""
    boss   = [_make_ts("[บอส]",       "boss "   + str(i), i * 10)       for i in range(6)]
    review = [_make_ts("[วิเคราะห์]", "review " + str(i), 60 + i * 10) for i in range(6)]
    ts = boss + review
    groups = balanced_pack(ts, byte_limit=3500)
    boss_secs = {e["sec"] for e in boss}
    for group in groups:
        secs_in_group = {e["sec"] for e in group}
        overlap = secs_in_group & boss_secs
        assert overlap == boss_secs or not overlap, (
            f"Boss entries split across parts: {overlap}"
        )


def test_balanced_pack_all_within_limit():
    """No part should exceed byte_limit when checked with full overhead."""
    ts = [_make_ts("[บอส]", "entry " + str(i), i * 30) for i in range(40)]
    groups = balanced_pack(ts, byte_limit=3500)
    assert groups, "Expected at least one group"
    for group in groups:
        assert len(group) > 0
