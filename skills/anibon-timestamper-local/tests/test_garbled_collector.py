import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _setup_rejection_workspace(tmp: str) -> tuple[Path, Path]:
    ws = Path(tmp)
    raw_tx = {"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "สตรีม ON และ โยA"}]}]}
    (ws / "raw_transcript.th-orig.json3").write_text(json.dumps(raw_tx, ensure_ascii=False), encoding="utf-8")
    notes_path = ws / "garbled_notes.json"
    notes_payload = {
        "version": 1,
        "notes": [
            {"garbled": "ON", "google_sentence": "สตรีม ON", "whisper_segment": "สตรีม Nexon", "correct": None},
            {"garbled": "โยA", "google_sentence": "ค่าย โยA สตรีม", "whisper_segment": "ค่ายอนิเมะสตรีม", "correct": None},
        ],
    }
    notes_path.write_text(json.dumps(notes_payload, ensure_ascii=False), encoding="utf-8")
    return ws, notes_path


class TestGarbledCollector(unittest.TestCase):
    def test_format_garbled_line_preserves_arrow_mapping(self):
        from process.runners.recursive import _format_garbled_line
        line = _format_garbled_line("neกon -> Nexon @ 03:05:14", "chunk_41")
        self.assertEqual(line, '- "neกon" -> Nexon @ 03:05:14 (chunk_41)')

    def test_resolve_garbled_notes_populates_correct_and_filters_unsafe(self):
        from process.garbled_collector import resolve_garbled_notes

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            raw_tx = {
                "events": [
                    {"tStartMs": 431000, "dDurationMs": 3000, "segs": [{"utf8": "ตัวของมาเป็น Blue Arvึ นะครับ"}]},
                    {"tStartMs": 1996000, "dDurationMs": 3000, "segs": [{"utf8": "เรื่องของ บีด ในอนาคต"}]},
                    {"tStartMs": 11114000, "dDurationMs": 3000, "segs": [{"utf8": "ค่าย neกon จัดจำหน่าย"}]},
                ]
            }
            (ws / "raw_transcript.th-orig.json3").write_text(
                json.dumps(raw_tx, ensure_ascii=False), encoding="utf-8"
            )
            notes_path = ws / "garbled_notes.json"
            notes_payload = {
                "version": 1,
                "notes": [
                    {
                        "garbled": "Blue Arvึ",
                        "google_sentence": "ตัวของมาเป็น Blue Arvึ นะครับ",
                        "whisper_segment": "ตัวว่าเป็น Blue Archive นะครับ",
                        "correct": None,
                        "chunk": "chunk_01",
                        "ts": "00:07:11",
                    },
                    {
                        "garbled": "บีด",
                        "google_sentence": "เรื่องของ บีด ในอนาคต",
                        "whisper_segment": "เรื่องของบรีชในอนาคต",
                        "correct": None,
                        "chunk": "chunk_07",
                        "ts": "00:33:16",
                    },
                    {
                        "garbled": "neกon",
                        "google_sentence": "ค่าย neกon จัดจำหน่าย",
                        "whisper_segment": "ค่าย Nexon จัดจำหน่าย",
                        "correct": None,
                        "chunk": "chunk_41",
                        "ts": "03:05:14",
                    },
                ],
            }
            notes_path.write_text(json.dumps(notes_payload, ensure_ascii=False), encoding="utf-8")

            mock_llm_json = json.dumps({
                "Blue Arvึ": "Blue Archive",
                "บีด": "Bleach",
                "neกon": "Nexon",
            }, ensure_ascii=False)

            with patch("process.garbled_collector.call_local", return_value=mock_llm_json):
                resolved_count = resolve_garbled_notes(ws, notes_path, endpoint="http://127.0.0.1:1234", model="test")

            self.assertEqual(resolved_count, 2)
            updated = json.loads(notes_path.read_text(encoding="utf-8"))
            by_garbled = {n["garbled"]: n["correct"] for n in updated["notes"]}
            self.assertEqual(by_garbled["Blue Arvึ"], "Blue Archive")
            self.assertEqual(by_garbled["neกon"], "Nexon")
            self.assertIsNone(by_garbled["บีด"])

    def test_clean_garbled_english_supports_txt_chunks(self):
        import sys
        plugin_root = Path(__file__).resolve().parents[3]
        script_dir = str(plugin_root / "skills" / "cleaning-auto-transcripts" / "scripts")
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        import clean_garbled_english

        with tempfile.TemporaryDirectory() as tmp:
            chunks_dir = Path(tmp)
            txt_chunk = chunks_dir / "chunk_00.txt"
            txt_chunk.write_text("(00:05:00) เล่นเกม Archen สนุกมาก\n", encoding="utf-8")
            count = clean_garbled_english.process_dir(chunks_dir, dry_run=False)
            self.assertGreater(count, 0)
            self.assertIn("Arcane", txt_chunk.read_text(encoding="utf-8"))

    def test_short_ascii_token_and_substring_replacement_rejected(self):
        from process.garbled_rules import is_safe_replacement, is_valid_candidate_token

        self.assertFalse(is_valid_candidate_token("ON"))
        self.assertFalse(is_valid_candidate_token("anp"))
        self.assertFalse(is_valid_candidate_token("MDB"))
        self.assertFalse(is_safe_replacement("ON", "Nexon"))
        self.assertFalse(is_safe_replacement("Blue", "Blue Archive"))
        self.assertTrue(is_valid_candidate_token("neกon"))
        self.assertTrue(is_safe_replacement("neกon", "Nexon"))

    def test_unverified_hallucinated_target_rejected_by_grounding(self):
        from process.garbled_grounding import GroundingContext, is_grounded_target

        context = GroundingContext(
            known_canonical_terms=frozenset({"nexon", "blue archive"}),
            stream_title="Live Stream Discussion",
        )
        self.assertFalse(is_grounded_target("Toyosa", "เรื่องของโยดาสตรีม", context))
        self.assertFalse(is_grounded_target("Sora", "เรื่องของขบวนการเซ็นไต", context))
        self.assertTrue(is_grounded_target("Nexon", "เรื่องของค่าย Nexon", context))
        self.assertTrue(is_grounded_target("Blue Archive", "ไม่กล่าวถึง", context))

    def test_resolve_garbled_notes_rejects_hallucinated_and_unsafe_targets(self):
        from process.garbled_collector import resolve_garbled_notes

        with tempfile.TemporaryDirectory() as tmp:
            ws, notes_path = _setup_rejection_workspace(tmp)
            mock_llm = json.dumps({"ON": "Nexon", "โยA": "Toyosa"}, ensure_ascii=False)
            with patch("process.garbled_collector.call_local", return_value=mock_llm):
                count = resolve_garbled_notes(ws, notes_path, endpoint="http://127.0.0.1:1234", model="test")

            self.assertEqual(count, 0)
            updated = json.loads(notes_path.read_text(encoding="utf-8"))
            self.assertTrue(all(n.get("correct") is None for n in updated["notes"]))


if __name__ == "__main__":
    unittest.main()
