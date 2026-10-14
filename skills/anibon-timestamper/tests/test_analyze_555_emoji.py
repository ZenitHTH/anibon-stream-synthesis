import tempfile
import unittest
from pathlib import Path

from analyze_555 import (
    EMOJI_MARKER_RE,
    Config,
    ChatStats,
    classify,
    parse_chat,
)


class TestAnalyze555Emoji(unittest.TestCase):
    def _chunk(self, lines, tmp_dir):
        f = Path(tmp_dir) / "livechat_chunk_00.txt"
        f.write_text("\n".join(lines), encoding="utf-8")
        return f

    def test_unicode_emoji_flood_is_meme_pulse(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [f"[00:{i:02d}:03] 🤣🤣🤣🤣 msg" for i in range(20)]
            stats = parse_chat(self._chunk(lines, tmp))
            self.assertEqual(stats.n_messages, 20)
            self.assertGreaterEqual(stats.n_markers, 20, "unicode laugh emojis must count as markers")
            v = classify(stats, Config(pulse_threshold=12, bucket=90))
            self.assertEqual(v.verdict, "MEME_PULSE", "emoji flood must be a meme pulse")

    def test_anibon_custom_emote_flood_is_meme_pulse(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [f"[00:{i:02d}:03] :_MonkeyBoat: :_MonkeyBoat: msg" for i in range(15)]
            stats = parse_chat(self._chunk(lines, tmp))
            self.assertGreaterEqual(stats.n_markers, 15, "Anibon custom emotes must count as markers")
            v = classify(stats, Config(pulse_threshold=12))
            self.assertEqual(v.verdict, "MEME_PULSE")

    def test_global_header_emote_welcomes_not_pulse(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :hand-pink_waving: สวัสดีโบ๊ท"], tmp))
            self.assertEqual(stats.n_markers, 0, "single welcome emote is not a laugh marker")
            self.assertEqual(classify(stats, Config()).verdict, "QUIET")

    def test_flat_emote_is_not_a_laugh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :_Meh: มุขแป๊ก กริบ"], tmp))
            self.assertEqual(stats.n_markers, 0, "flat emote is not laughter")

    def test_afk_emote_is_not_a_laugh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :_noname: ไปห้องน้ำก่อน"], tmp))
            self.assertEqual(stats.n_markers, 0, "AFK emote is not laughter")

    def test_confusion_emote_is_not_a_laugh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :_What: ห๊ะ? อะไรวะเนี่ย"], tmp))
            self.assertEqual(stats.n_markers, 0, "confusion emote is not laughter")

    def test_nerd_explain_emote_is_not_a_laugh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :_Nerd: จริงๆแล้วระบบนี้..."], tmp))
            self.assertEqual(stats.n_markers, 0, "nerd explain emote is not laughter")

    def test_flat_emote_flood_is_quiet_not_pulse(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [f"[00:{i:02d}:03] :_Meh: :_Meh: มุขแป๊ก" for i in range(20)]
            stats = parse_chat(self._chunk(lines, tmp))
            v = classify(stats, Config(pulse_threshold=12, bucket=90))
            self.assertNotEqual(v.verdict, "MEME_PULSE", "flat emote flood must not be a meme pulse")

    def test_political_emote_is_not_a_laugh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[00:00:01] :_Slim: คิงเอริค META จริง"], tmp))
            self.assertEqual(stats.n_markers, 0, "political emote is not laughter")

    def test_death_skull_is_marker(self):
        self.assertTrue(EMOJI_MARKER_RE.search("lol ตาย 💀💀"))
        self.assertTrue(EMOJI_MARKER_RE.search("ช็อตฟีล ☠️"))


if __name__ == "__main__":
    unittest.main()