from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))

from common.lm_think_log import summarize_lm_trace
from common.timestamps import sanitize_timestamp_line
from process.byte_cap import generate_part_summary
from process.prompts import _build_game_switch_hint, _extract_donor_mentions
from process.runners.recursive import (
    _estimate_prompt_tokens,
    _is_non_thai_bgm_chunk,
    _short_circuit_bgm_chunk,
)
from process.summarizer_prompt import _normalize_summary_connectors


class TestStage5PipelineGuards(unittest.TestCase):
    def test_thai_non_whitelisted_tags_remap_and_never_leak_into_headers(self) -> None:
        s1 = sanitize_timestamp_line("07:13:36 - [บ่นยับ] ถกประเด็นความยากของ Loop Hero")
        s2 = sanitize_timestamp_line("06:33:46 - [โวยวาย] เดือดจัดเมื่อเจอแวมไพร์")
        self.assertEqual(s1, "07:13:36 - [Talk] ถกประเด็นความยากของ Loop Hero")
        self.assertEqual(s2, "06:33:46 - [Reaction] เดือดจัดเมื่อเจอแวมไพร์")

        header = generate_part_summary([
            "06:10:48 - [Talk] ตีแผ่ระบบการเล่นของ Loop Hero",
            "06:38:43 - [Gameplay] วางแผนสร้างฐาน",
            "07:13:36 - [บ่นยับ] ถกประเด็นความยากของ Loop Hero",
        ])
        self.assertNotIn("07:13:36", header)
        self.assertNotIn("[บ่นยับ]", header)

        norm = _normalize_summary_connectors("วิพากษ์ระบบ Loop + วางแผนสร้างฐาน + 07:13:36 - [บ่นยับ]")
        self.assertNotIn("07:13:36", norm)
        self.assertNotIn("[บ่นยับ]", norm)

    def test_non_thai_bgm_chunk_short_circuits_preroll_and_afk_breaks(self) -> None:
        bgm_chunk = {"items": [{"text": "世界諦めてやる何せ呼吸"}, {"text": "마다 도 빵빵"}]}
        thai_chunk = {"items": [{"text": "สวัสดีทุกคนนะครับ ยินดีต้อนรับ"}]}
        recovered_thai = {"recovered_items": [{"text": "เดี๋ยวผมขอไปห้องน้ำแป๊บนึงนะครับ"}]}

        self.assertTrue(_is_non_thai_bgm_chunk(bgm_chunk, None))
        self.assertFalse(_is_non_thai_bgm_chunk(thai_chunk, None))
        self.assertFalse(_is_non_thai_bgm_chunk(bgm_chunk, recovered_thai))

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            all_ts: list[str] = []
            t0, s0 = _short_circuit_bgm_chunk(0, "chunk_00", "[001/242]", ws / "chunk_00.json", all_ts, "", "")
            self.assertEqual(len(all_ts), 1)
            self.assertTrue(all_ts[0].startswith("00:00:00 - [Intro]"))

            t1, s1 = _short_circuit_bgm_chunk(
                112, "chunk_112", "[113/242]", ws / "chunk_112.json", all_ts, "เล่น Master Duel", "กำลังดวลเด็ค D/D/D"
            )
            self.assertEqual(len(all_ts), 1)
            self.assertEqual(t1, "เล่น Master Duel")
            self.assertEqual(s1, "กำลังดวลเด็ค D/D/D")

    def test_donor_mention_extraction_flags_english_handles(self) -> None:
        transcript = "(01:58:27) ขอบคุณมากนะ Donate นะฮะ เดี๋ยวนะ นั่นแหละครับผมคุณ The Foundation เมื่อก่อนก็เป็นพรรคเดียวกัน"
        hint = _extract_donor_mentions(transcript)
        self.assertIn("The Foundation", hint)
        self.assertIn("DO NOT treat as game characters", hint)

    def test_game_switch_hint_fires_on_new_high_confidence_domain(self) -> None:
        sig = {"primary_topic": "Arknights: Endfield", "confidence": 0.92}
        hint = _build_game_switch_hint(sig, "พูดคุยเนื้อเรื่อง Wuthering Waves", "วิจารณ์บทตัวละครใน Wuthering Waves")
        self.assertIn("DOMAIN SWITCH CHECK", hint)
        self.assertIn("Arknights: Endfield", hint)
        # Same game -> no hint
        self.assertEqual(_build_game_switch_hint(sig, "เล่น Arknights: Endfield", "สำรวจโรงงาน"), "")

    def test_estimate_prompt_tokens_and_trace_summary(self) -> None:
        prompt = ("ก" * 6000) + ("a" * 10924)
        keyframes = [("00:01:00", Path("a.jpg"), "b64", "SB")] * 9
        est = _estimate_prompt_tokens(prompt, keyframes)
        self.assertGreater(est, 7500)
        self.assertLess(est, 9000)

        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "lm_think_trace.jsonl"
            tp.write_text(
                json.dumps({"elapsed_s": 50.0, "prompt_tokens": 8000, "completion_tokens": 200, "reasoning_tokens": 0, "errors": []}) + "\n",
                encoding="utf-8",
            )
            stats = summarize_lm_trace(tp)
            self.assertEqual(stats["prompt_tokens"], 8000)
            self.assertEqual(stats["completion_tokens"], 200)
            self.assertEqual(stats["tok_per_sec"], 4.0)
            self.assertEqual(stats["total_tok_per_sec"], 164.0)


if __name__ == "__main__":
    unittest.main()
