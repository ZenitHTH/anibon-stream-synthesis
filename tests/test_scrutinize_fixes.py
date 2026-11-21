from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))

try:
    from PIL import Image
except ImportError:
    Image = None

from process.chunk_enrichment import ChunkEnrichConfig, enrich_single_chunk
from process.prompts import build_chunk_entity_context, load_world_identity_context
from process.runners.dynamic_chunk import _load_cached_enrichment_webcam
from video.audio_webcam_cues import AudioWebcamCue
from video.webcam_storyboard import assemble_webcam_storyboard


class TestScrutinizeFixes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_finding1_jit_db_entities_never_blocked_by_wrong_allowed_sources(self) -> None:
        with patch("process.knowledge.domain_db.resolve_entities_for_chunk", return_value=["Sen no Rikyu (เซ็น โนะ ริคิว)"]) as m_jit:
            ctx = build_chunk_entity_context(
                "สุ่มได้ NP5 ยาย ริคิว Noble Phantasm",
                glossary={"Ellen Joe": {"en": "Ellen Joe", "th": "เอลเลน โจ", "sources": ["Zenless_Zone_Zero.md"]}},
                allowed_sources={"Zenless_Zone_Zero.md"},
            )
        m_jit.assert_called_once()
        self.assertIn("Sen no Rikyu (เซ็น โนะ ริคิว)", ctx)

    def test_finding1_low_confidence_wi_is_capped_not_40kb_dump(self) -> None:
        ref = self.ws / "Zenless_Zone_Zero.md"
        ref.write_text("Z" * 30000, encoding="utf-8")
        out_low = load_world_identity_context({"best_file": "Zenless_Zone_Zero.md", "confidence": 0.40}, self.ws)
        self.assertLess(len(out_low), 6000)
        out_high = load_world_identity_context({"best_file": "Zenless_Zone_Zero.md", "confidence": 0.85}, self.ws)
        self.assertGreater(len(out_high), 25000)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_finding3_webcam_storyboard_packs_mixed_aspect_frames(self) -> None:
        f1 = self.ws / "wc_000737.jpg"
        f2 = self.ws / "wc_000770.jpg"
        Image.new("RGB", (320, 320), (80, 100, 120)).save(f1)
        Image.new("RGB", (320, 220), (140, 90, 60)).save(f2)
        frames = [
            ("00:12:17", f1, "b64_1", "WEBCAM CLOSEUP"),
            ("00:12:50", f2, "b64_2", "WEBCAM CLOSEUP"),
        ]
        out_sheet = self.ws / "wc_sheet_05_0.jpg"
        sheet = assemble_webcam_storyboard(frames, out_sheet)
        self.assertIsNotNone(sheet)
        self.assertTrue(out_sheet.is_file())
        self.assertIn("2 panels:", sheet[3])

    def test_finding2_and_4_enrich_expands_webcam_cues_and_preserves_sheet_legend(self) -> None:
        (self.ws / "chunks").mkdir()
        cp = self.ws / "chunks" / "chunk_05.txt"
        cp.write_text(
            "CHUNK 05 | 00:11:15–00:13:45 | cutoff=00:13:30\n"
            "(00:11:20) สวัสดี\n"
            "(00:12:17) เฮ้ย ได้แล้ว\n"
            "(00:12:50) ดูกล้องนะ ดูนี่นะ\n",
            encoding="utf-8",
        )
        sheet_file = self.ws / "frames" / "webcam_chunk" / "wc_sheet_05_0.jpg"
        sheet_file.parent.mkdir(parents=True)
        sheet_file.write_bytes(b"fake-sheet")
        legend = "WEBCAM STORYBOARD (3x2 grid, left-to-right top-to-bottom; 6 panels: [1]=00:12:15 WEBCAM CLOSEUP)"
        fake_wc = [("00:12:15-00:12:52", sheet_file, "b64", legend)]
        captured_reqs = []

        def spy_sample(req):
            captured_reqs.append(req)
            return fake_wc

        cfg = ChunkEnrichConfig(workspace=self.ws, audio_source=Path("a.m4a"), video_source=Path("v.mp4"))
        cues = (AudioWebcamCue(737, "loud_peak", 3.5, "loud_peak"),)
        with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=cues), \
             patch("process.chunk_enrichment.sample_chunk_webcam_frames", side_effect=spy_sample), \
             patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=False):
            payload = enrich_single_chunk(cp, cfg)

        self.assertTrue(captured_reqs)
        # Finding 2: 1 audio cue + deictic speech must expand to multiple target seconds (>= 3)
        self.assertGreaterEqual(len(captured_reqs[0].target_secs), 3)
        # Finding 4: cached webcam_frames preserves sheet legend and timestamp span when reloaded
        loaded_wc = _load_cached_enrichment_webcam(self.ws, {"_idx": 5, "start_sec": 675})
        self.assertEqual(len(loaded_wc), 1)
        self.assertEqual(loaded_wc[0][0], "00:12:15-00:12:52")
        self.assertIn("6 panels:", loaded_wc[0][3])


if __name__ == "__main__":
    unittest.main()
