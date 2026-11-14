import json
import sys
import tempfile
import unittest
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _p in (_PLUGIN_ROOT / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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

    def test_single_marker_in_low_message_chunk_is_quiet_not_meme_pulse(self):
        from analyze_555 import serialize
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                "[09:27:15] user1: หืม?",
                "[09:27:45] user2: จะได้ใส่เดี่ยวกับนโปเลียนมั้ย",
                "[09:28:30] user1: บอสกังหัน",
                "[09:30:31] user3: ลูกกระจ๊อกกลืนไปกับพื้นโคลนเลยมะกี้555",
            ]
            stats = parse_chat(self._chunk(lines, tmp))
            v = classify(stats, Config())
            self.assertEqual(v.verdict, "QUIET")
            rec = serialize(stats, v, Config())
            self.assertIn("tone", rec)
            self.assertTrue(rec["tone"].get("tone"))

    def test_speaker_rage_quit_overrides_meme_pulse_chat(self):
        from speaker_mood import parse_speaker_chunk
        with tempfile.TemporaryDirectory() as tmp:
            chat_lines = [f"[09:56:{i:02d}] user{i}: 555555" for i in range(15)]
            stats = parse_chat(self._chunk(chat_lines, tmp))
            sp_file = Path(tmp) / "chunk_128.txt"
            sp_file.write_text(
                "(09:56:30) เหี้ยไม่เล่นแล้วไอ้สัตว์ปัญญาอ่อน\n"
                "(09:56:58) อารมณ์เสียว่ะปิดไลฟ์แบบแย่ๆหน่อยวันนี้\n"
                "(09:57:03) Oh my god fucking hate this game ไม่ไหวว่ะ\n"
                "(09:58:01) ไม่เล่นต่อละช่างแม่งเหอะ\n",
                encoding="utf-8",
            )
            sp_stats = parse_speaker_chunk(sp_file)
            v = classify(stats, Config(), sp_stats)
            self.assertEqual(v.verdict, "RAGE_QUIT_PULSE")
            self.assertEqual(v.mood, "rage_quit")
            self.assertTrue(v.pulse)

    def test_speaker_angry_tilt_overrides_quiet_chat(self):
        from speaker_mood import parse_speaker_chunk
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[09:50:01] user1: ยากจัด"], tmp))
            sp_file = Path(tmp) / "chunk_127.txt"
            sp_file.write_text(
                "(09:50:10) ไอ้เหี้ยเอ้ย เสียอารมณ์ว่ะ\n"
                "(09:51:55) โคตรแย่เลยว่ะ feel bad เลย\n"
                "(09:52:03) ควยจัดบอสตัวนี้ ไอ้สัตว์ ขี้หมาเกิน\n",
                encoding="utf-8",
            )
            sp_stats = parse_speaker_chunk(sp_file)
            v = classify(stats, Config(), sp_stats)
            self.assertEqual(v.verdict, "ANGRY_TILT_PULSE")
            self.assertEqual(v.mood, "angry")
            self.assertTrue(v.pulse)

    def test_speaker_sick_afk_overrides_quiet_chat(self):
        from speaker_mood import parse_speaker_chunk
        with tempfile.TemporaryDirectory() as tmp:
            stats = parse_chat(self._chunk(["[06:52:55] user1: หายไวๆครับ"], tmp))
            sp_file = Path(tmp) / "chunk_91.txt"
            sp_file.write_text(
                "(06:52:55) โอ้คำสาปฟาโรห์แรงจริงๆฮะ ปวดท้องหนักมาก\n"
                "(08:35:57) หนีไปขี้ทั้ง 2 รอบ ท้องอืด\n",
                encoding="utf-8",
            )
            sp_stats = parse_speaker_chunk(sp_file)
            v = classify(stats, Config(), sp_stats)
            self.assertEqual(v.verdict, "SICK_AFK_PULSE")
            self.assertEqual(v.mood, "sick_afk")
            self.assertTrue(v.pulse)

    def test_speaker_panic_shock_hype_and_sleepy_pulses(self):
        from speaker_mood import parse_speaker_text
        stats = ChatStats()
        panic_sp = parse_speaker_text("อุ้ยไอ้เหี้ย ตกใจหมด หัวใจจะวาย โดนต้ม 40 หายวับไปกับตา")
        self.assertEqual(classify(stats, Config(), panic_sp).verdict, "PANIC_SHOCK_PULSE")
        hype_sp = parse_speaker_text("ได้แล้วไอ้เหี้ย รอดแล้ว ได้ของครบ โคตรดีเลยว่ะ")
        self.assertEqual(classify(stats, Config(), hype_sp).verdict, "HYPE_CLUTCH_PULSE")
        sleepy_sp = parse_speaker_text("ผมเริ่มง่วงแล้วว่ะ เมื่อคืนนอนไม่พอว่ะ")
        self.assertEqual(classify(stats, Config(), sleepy_sp).verdict, "SLEEPY_DRAIN_PULSE")

    def test_whisper_single_line_stutter_does_not_trigger_angry_tilt(self):
        from speaker_mood import parse_speaker_text
        stutter = "(01:00:01) เกลียดมาก เกลียดมาก เกลียดมาก เกลียดมาก เกลียดมาก\n"
        sp = parse_speaker_text(stutter)
        self.assertEqual(sp.n_frust, 1)
        self.assertEqual(classify(ChatStats(), Config(), sp).verdict, "QUIET")

    def test_whisper_consecutive_duplicate_lines_collapsed(self):
        from speaker_mood import parse_speaker_text
        loop_lines = "\n".join(
            f"(05:51:{i:02d}) ไอ้เหี้ย อารมณ์เสีย" for i in range(15)
        )
        sp = parse_speaker_text(loop_lines)
        self.assertEqual(sp.n_swears, 1)
        self.assertEqual(sp.n_frust, 1)

    def test_parse_speaker_chunk_supports_xml_and_json(self):
        from speaker_mood import parse_speaker_chunk, resolve_speaker_chunk_path
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            xml_p = tdir / "chunk_05.xml"
            xml_p.write_text(
                '<chunk><item timestamp="00:20:01">ไม่เล่นแล้ว ลบเกมทิ้ง</item>'
                '<item timestamp="00:20:05">อารมณ์เสีย หัวร้อน หงุดหงิด</item></chunk>',
                encoding="utf-8",
            )
            resolved = resolve_speaker_chunk_path(tdir, "chunk_05")
            self.assertEqual(resolved, xml_p)
            sp = parse_speaker_chunk(resolved)
            self.assertEqual(classify(ChatStats(), Config(), sp).verdict, "RAGE_QUIT_PULSE")

            jdir = tdir / "json_chunks"
            jdir.mkdir()
            json_p = jdir / "chunk_06.json"
            json_p.write_text(
                json.dumps({"items": [
                    {"text": "ไอ้เหี้ย เสียอารมณ์"},
                    {"text": "หัวร้อน หงุดหงิด โคตรแย่ เกมหมา"},
                ]}, ensure_ascii=False),
                encoding="utf-8",
            )
            jres = resolve_speaker_chunk_path(jdir, "chunk_06")
            self.assertEqual(jres, json_p)
            sp_j = parse_speaker_chunk(jres)
            self.assertEqual(classify(ChatStats(), Config(), sp_j).verdict, "ANGRY_TILT_PULSE")

    def test_analyze_runs_speaker_only_and_transcript_gz(self):
        import gzip
        from analyze_555 import analyze
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            cdir = ws / "chunks"
            cdir.mkdir()
            (cdir / "chunk_00.txt").write_text(
                "(00:01:00) ไอ้เหี้ย อารมณ์เสีย\n"
                "(00:01:05) หัวร้อน หงุดหงิด โคตรแย่\n"
                "(00:01:10) ไม่เล่นแล้ว ลบเกมทิ้ง\n",
                encoding="utf-8",
            )
            out = ws / "mood_555.json"
            res = analyze(str(ws / "livechat"), "", str(out), chunks_dir=str(cdir))
            self.assertEqual(res["chunk_00"]["verdict"], "RAGE_QUIT_PULSE")

            gz = ws / "transcript.jsonl.gz"
            with gzip.open(gz, "wt", encoding="utf-8") as gf:
                gf.write(json.dumps({"start": 10, "text": "อุ้ยไอ้เหี้ย ตกใจหมด"}) + "\n")
                gf.write(json.dumps({"start": 15, "text": "หัวใจจะวาย บรรลัยแล้ว"}) + "\n")
            gz_out = ws / "mood_gz.json"
            gz_res = analyze("", "", str(gz_out), transcript_gz=str(gz))
            self.assertEqual(gz_res["chunk_00"]["verdict"], "PANIC_SHOCK_PULSE")

    def test_ensure_mood_555_passes_chunks_without_livechat(self):
        from process.parity_gates import ensure_mood_555
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "chunks" / "chunk_00.txt").write_text(
                "(00:01:00) ไอ้เหี้ย อารมณ์เสีย\n"
                "(00:01:05) หัวร้อน หงุดหงิด โคตรแย่ ไม่เล่นแล้ว ลบเกมทิ้ง\n",
                encoding="utf-8",
            )
            ensure_mood_555(ws)
            mood_file = ws / "mood_555.json"
            self.assertTrue(mood_file.exists(), "ensure_mood_555 should generate mood_555.json from chunks alone")
            data = json.loads(mood_file.read_text(encoding="utf-8"))
            self.assertEqual(data["chunk_00"]["verdict"], "RAGE_QUIT_PULSE")

    def test_build_subagent_prompts_formats_nested_tone_and_cues(self):
        import importlib.util

        repo_root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "build_subagent_prompts",
            repo_root / "skills" / "anibon-timestamper" / "scripts" / "build_subagent_prompts.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        formatted = mod.format_chunk_mood_guidance({
            "verdict": "ANGRY_TILT_PULSE",
            "tone": {
                "tone": "frustrated, tilted",
                "verbs": ["หงุดหงิด", "อารมณ์เสีย"],
            },
            "speaker_cues": ["rage_profanity", "frustration"],
        })
        self.assertIn("verdict: ANGRY_TILT_PULSE", formatted)
        self.assertIn("tone: frustrated, tilted", formatted)
        self.assertIn("verbs: ['หงุดหงิด', 'อารมณ์เสีย']", formatted)
        self.assertIn("cues: ['rage_profanity', 'frustration']", formatted)
        self.assertNotIn("{'tone':", formatted)

    def test_skill_validate_mood_matches_root_mood_rules(self):
        import importlib.util

        repo_root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "skill_validate_mood",
            repo_root / "skills" / "anibon-timestamper" / "scripts" / "validate_mood.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        self.assertIn("ANGRY_TILT_PULSE", mod._OLD_FALLBACK)
        validator = mod.Validator(
            {"chunk_00": {"verdict": "QUIET"}},
            {"chunk_00": (0, 600)},
        )
        self.assertFalse(validator.in_mood_segment("chunk_00", 60))






if __name__ == "__main__":
    unittest.main()