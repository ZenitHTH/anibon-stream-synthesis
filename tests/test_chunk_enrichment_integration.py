from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))
_CLOUD_SCRIPTS = str(_ROOT / "skills" / "anibon-timestamper" / "scripts")
if _CLOUD_SCRIPTS not in sys.path:
    sys.path.insert(0, _CLOUD_SCRIPTS)

import build_subagent_prompts
from chunk.state import load_chunk_enrichment
from process.prompts import build_group_prompt, build_recursive_prompt
from process.runners.common import _compute_chunk_time_window
from process.runners.dynamic_chunk import _balance_dynamic_chunk_frames


class TestChunkEnrichmentIntegration(unittest.TestCase):
    def test_silent_chunk_time_window_uses_chunk_bounds(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 450, "items": []}
        self.assertEqual(_compute_chunk_time_window(chunk, 1), (300, 450))

    def test_recursive_and_group_prompts_inject_song_and_recovered_speech(self) -> None:
        enrichment = {
            "audio_cues": [{"sec": 310, "event_type": "silence_drop", "note": "silence_drop"}],
            "song": {"title": "Unravel", "artist": "TK"},
            "recovered_items": [{"start": 315.0, "timestamp": "00:05:15", "text": "อึ้งเลยฉากนี้"}],
        }
        chunk = {"_idx": 1, "start_sec": 300, "end_sec": 450, "items": []}
        rec = build_recursive_prompt(chunk, "Gaming", "summary", enrichment=enrichment)
        self.assertIn("00:05:00 - 00:07:30", rec)
        self.assertIn("Unravel - TK", rec)
        self.assertIn("(00:05:15) อึ้งเลยฉากนี้", rec)
        self.assertIn("silence_drop", rec)

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "enrichment").mkdir()
            (ws / "enrichment" / "chunk_01.json").write_text(json.dumps(enrichment, ensure_ascii=False), encoding="utf-8")
            grp = build_group_prompt(
                [chunk], 0, "", "th", {}, ws, enrichment_loader=load_chunk_enrichment
            )
            self.assertIn("00:05:00 - 00:07:30", grp)
            self.assertIn("Unravel - TK", grp)
            self.assertIn("(00:05:15) อึ้งเลยฉากนี้", grp)

    def test_dynamic_chunk_loads_cached_enrichment_webcam_frames_without_source(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            img = ws / "frames" / "webcam_chunk" / "wc_sheet_00_0.jpg"
            img.parent.mkdir(parents=True)
            img.write_bytes(b"\xff\xd8\xff\xd9")
            (ws / "enrichment").mkdir()
            (ws / "enrichment" / "chunk_00.json").write_text(
                json.dumps({
                    "audio_cues": [{"sec": 45, "event_type": "silence_drop", "note": "silence_drop"}],
                    "webcam_frames": [str(img)],
                }),
                encoding="utf-8",
            )
            sb_frames, wc_frames, tier = _balance_dynamic_chunk_frames(
                ws, {"_idx": 0, "items": []}, [("00:00:10", img, base64.b64encode(b"x").decode(), "SCREEN")], None, None
            )
            self.assertEqual(len(wc_frames), 1)
            self.assertEqual(wc_frames[0][0], "00:00:45")
            self.assertIn("silence_drop", wc_frames[0][3])
            self.assertEqual(tier, "cached-enrichment")
            self.assertEqual(len(sb_frames), 1)

            with patch("process.runners.dynamic_chunk._enrich_plan_with_peaks", side_effect=AssertionError("should skip peak scan")):
                _, wc2, _ = _balance_dynamic_chunk_frames(
                    ws, {"_idx": 0, "items": []}, [("00:00:10", img, base64.b64encode(b"x").decode(), "SCREEN")], Path("v.mp4"), None
                )
                self.assertEqual(len(wc2), 1)

    def test_peak_search_and_webcam_box_use_chunk_bounds_when_items_empty(self) -> None:
        from unittest.mock import patch
        from video.chunk_peak_select import PeakSearchInput, detect_chunk_reaction_peaks
        from process.runners.dynamic_chunk import _resolve_chunk_webcam_box

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            raw_bins = [(300 + i, 0.08) for i in range(5)] + [(305 + i, 0.002) for i in range(8)]
            with patch("video.chunk_peak_select.extract_raw_rms_bins", return_value=raw_bins):
                peaks, _, promote = detect_chunk_reaction_peaks(
                    PeakSearchInput(ws, [], "audio.m4a", chunk_bounds=(300, 450))
                )
            self.assertTrue(promote)
            self.assertTrue(any(300 <= p <= 450 for p in peaks))

            seen = {}
            def fake_probe(_src, lo, hi, _key):
                seen["bounds"] = (lo, hi)
                return None
            with patch("process.runners.dynamic_chunk._probe_chunk_layout_box", side_effect=fake_probe):
                _resolve_chunk_webcam_box(ws, Path("v.mp4"), [], None, chunk_bounds=(300, 450))
            self.assertEqual(seen["bounds"], (300, 450))

    def test_cloud_build_subagent_prompts_injects_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "enrichment").mkdir()
            (ws / "signals.json").write_text(json.dumps({"chunks": {"chunk_00": {"primary_topic": "Music"}}}), encoding="utf-8")
            (ws / "chunks" / "chunk_00.xml").write_text('<chunk id="0" start_sec="0" end_sec="150"></chunk>', encoding="utf-8")
            (ws / "enrichment" / "chunk_00.json").write_text(
                json.dumps({"song": {"title": "Idol", "artist": "YOASOBI"}, "recovered_items": [{"timestamp": "00:00:30", "text": "เพลงดีมาก"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            build_subagent_prompts.build_prompts(str(ws))
            out = (ws / "prompts_by_chunk" / "chunk_00.txt").read_text(encoding="utf-8")
            self.assertIn("Idol - YOASOBI", out)
            self.assertIn("(00:00:30) เพลงดีมาก", out)

            (ws / "enrichment" / "chunk_00.json").write_text("{bad json", encoding="utf-8")
            build_subagent_prompts.build_prompts(str(ws))


if __name__ == "__main__":
    unittest.main()
