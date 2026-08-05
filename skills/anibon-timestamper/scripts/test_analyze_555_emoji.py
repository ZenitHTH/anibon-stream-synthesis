#!/usr/bin/env python3
"""Emoji / custom-emote pulse detection tests (analyze_555.py Stage 2.5-2.7).

RED phase for the emoji-table upgrade: a chat log that floods emojis / Anibon
custom emotes / YouTube global emotes (with NO 5 5 5 laugh text) must still be
recognised as a meme pulse, mirroring the "Dual-Side Thai Stream & Chat Mood
Detection" design doc Stages 2.5-2.7.

Before this change a log of pure "🤣🤣🤣" produced zero markers -> QUIET.
After: the emoji/emote weighted score feeds the same peak/burst logic.
"""
import tempfile
from pathlib import Path

from analyze_555 import (EMOJI_MARKER_RE, Config, ChatStats, classify,
                         parse_chat)


def _chunk(lines):
    d = Path(tempfile.mkdtemp())
    f = d / "livechat_chunk_00.txt"
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


def test_unicode_emoji_flood_is_meme_pulse():
    lines = []
    for i in range(20):
        lines.append(f"[00:{i:02d}:03] 🤣🤣🤣🤣 msg")
    stats = parse_chat(_chunk(lines))
    assert stats.n_messages == 20
    assert stats.n_markers >= 20, "unicode laugh emojis must count as markers"
    v = classify(stats, Config(pulse_threshold=12, bucket=90))
    assert v.verdict == "MEME_PULSE", "emoji flood must be a meme pulse"


def test_anibon_custom_emote_flood_is_meme_pulse():
    lines = [f"[00:{i:02d}:03] :_MonkeyBoat: :_MonkeyBoat: msg" for i in range(15)]
    stats = parse_chat(_chunk(lines))
    assert stats.n_markers >= 15, "Anibon custom emotes must count as markers"
    v = classify(stats, Config(pulse_threshold=12))
    assert v.verdict == "MEME_PULSE"


def test_global_header_emote_welcomes_not_pulse():
    """A one-off global emote line should not trip a pulse by itself."""
    stats = parse_chat(_chunk(["[00:00:01] :hand-pink_waving: สวัสดีโบ๊ท"]))
    assert stats.n_markers == 0, "single welcome emote is not a laugh marker"
    assert classify(stats, Config()).verdict == "QUIET"


def test_death_skull_is_marker():
    assert EMOJI_MARKER_RE.search("lol ตาย 💀💀")
    assert EMOJI_MARKER_RE.search("ช็อตฟีล ☠️")


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)