"""Tests for align_live_chat.py — slice livechat events to transcript chunk windows."""
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from align_live_chat import load_events, load_chunk_windows, slice_events, align


# ─────────────────────────────────────────────────────────────
# slicing primitives
# ─────────────────────────────────────────────────────────────

def test_load_events_parses_seconds_and_skips_bad_lines(tmp_path):
    feed = tmp_path / "events.txt"
    feed.write_text(
        "0\t[00:00:00] a: hi\n"
        "145\t[00:02:25] a: mid\n"
        "460\t[00:07:40] b: late\n"
        "notanumber\tgarbage\n", encoding="utf-8")
    events = load_events(feed)
    assert events == [(0, "[00:00:00] a: hi"), (145, "[00:02:25] a: mid"), (460, "[00:07:40] b: late")]


def test_load_events_sorts_unsorted_feed():
    events = load_events_feed(["300\t[00:05:00] b: z", "10\t[00:00:10] a: y"])
    assert events == [(10, "[00:00:10] a: y"), (300, "[00:05:00] b: z")]


def load_events_feed(lines):
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp()) / "e.txt"
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_events(tmp)


def test_slice_events_half_open_window():
    events = [(0, "e0"), (145, "e145"), (300, "e300"), (599, "e599"), (600, "e600")]
    assert slice_events(events, 0, 300) == ["e0", "e145"]
    assert slice_events(events, 300, 600) == ["e300", "e599"]
    assert slice_events(events, 600, 900) == ["e600"]


def test_load_chunk_windows_from_xml(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "chunk_00.xml").write_text(
        '<chunk id="0" start_sec="0" end_sec="300"><item>t</item></chunk>', encoding="utf-8")
    (chunks / "chunk_01.xml").write_text(
        '<chunk id="1" start_sec="300" end_sec="600"><item>t</item></chunk>', encoding="utf-8")
    windows = load_chunk_windows(chunks)
    assert windows == [("chunk_00", 0, 300), ("chunk_01", 300, 600)]


# ─────────────────────────────────────────────────────────────
# end-to-end align
# ─────────────────────────────────────────────────────────────

def test_align_writes_per_chunk_logs_and_index(tmp_path):
    feed = tmp_path / "events.txt"
    feed.write_text(
        "0\t[00:00:00] a: intro\n"
        "145\t[00:02:25] a: still early\n"
        "300\t[00:05:00] b: chunk two\n"
        "9000\t[02:30:00] c: far later\n", encoding="utf-8")
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "chunk_00.xml").write_text(
        '<chunk id="0" start_sec="0" end_sec="300"><item>t</item></chunk>', encoding="utf-8")
    (chunks / "chunk_01.xml").write_text(
        '<chunk id="1" start_sec="300" end_sec="600"><item>t</item></chunk>', encoding="utf-8")
    out = tmp_path / "out"

    align(feed, chunks, out)

    assert (out / "livechat_chunk_00.txt").read_text(encoding="utf-8") == "[00:00:00] a: intro\n[00:02:25] a: still early\n"
    assert (out / "livechat_chunk_01.txt").read_text(encoding="utf-8") == "[00:05:00] b: chunk two\n"
    assert (out / "livechat_chunk_01.txt").read_text(encoding="utf-8") != "[02:30:00] c: far later\n"

    index = json_load(out / "livechat_index.json")
    assert index["chunk_00"]["count"] == 2
    assert index["chunk_01"]["count"] == 1


def json_load(p):
    import json
    return json.loads(p.read_text(encoding="utf-8"))