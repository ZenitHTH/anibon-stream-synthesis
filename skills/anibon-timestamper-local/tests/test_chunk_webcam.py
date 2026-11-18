"""Unit tests for Pass 1 per-chunk webcam closeup sampling."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames  # noqa: E402
from video.motion_types import FaceBox, LayoutSegment  # noqa: E402


class TestChunkWebcamSampling(unittest.TestCase):
    """Verify Pass 1 webcam sampling, caching, and graceful degradation."""

    def test_returns_empty_without_valid_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            req = ChunkWebcamRequest(
                workspace=Path(tmp),
                source=None,
                chunk={"_idx": 0, "items": [{"start": 10.0, "text": "เห้ย อะไรวะ"}]},
            )
            self.assertEqual(sample_chunk_webcam_frames(req), [])

    def test_samples_and_caches_labeled_webcam_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box = FaceBox(0.75, 0.33, 0.25, 0.32, "mid-right")
            layout = LayoutSegment("mid-right", box, box.derive_tight_face())
            rendered: list[int] = []

            def fake_render(src_vf: tuple, out_jpg: Path, sec: float) -> bool:
                rendered.append(int(sec))
                out_jpg.parent.mkdir(parents=True, exist_ok=True)
                out_jpg.write_bytes(b"fakejpg")
                return True

            items = [
                {"start": 100.0, "text": "คุยปกติ"},
                {"start": 135.0, "text": "เห้ย เชี่ย ตกใจจัด"},
                {"start": 210.0, "text": "โอ้โห ดูอันนี้ดิ"},
            ]
            req = ChunkWebcamRequest(
                workspace=ws,
                source=vid,
                chunk={"_idx": 2, "items": items},
                max_frames=3,
                layout_fn=lambda *a, **k: layout,
                render_fn=fake_render,
            )
            first = sample_chunk_webcam_frames(req)
            self.assertGreaterEqual(len(first), 2)
            self.assertLessEqual(len(first), 3)
            self.assertEqual(first[0][3], "WEBCAM CLOSEUP")
            self.assertTrue(first[0][1].is_file())
            count_after_first = len(rendered)

            second = sample_chunk_webcam_frames(req)
            self.assertEqual(len(second), len(first))
            self.assertEqual(len(rendered), count_after_first)

    def test_recursive_runner_logs_separate_storyboard_and_webcam_counts(self) -> None:
        from unittest.mock import patch
        from process.runners import recursive as rec
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:10] เฮ้ย เชี่ย อะไรวะ\n", encoding="utf-8")
            slides = ws / "frames" / "slides_clean"
            slides.mkdir(parents=True)
            (slides / "slide_0001.jpg").write_bytes(b"0")
            sb = [("00:00:10", ws / "t.jpg", "AA==")]
            wc = [("00:00:10", ws / "w.jpg", "BB==", "WEBCAM CLOSEUP")]
            out = io.StringIO()
            with patch.object(rec, "_init_multimodal_grounding", return_value=(True, slides, ws / "tiles")), \
                 patch.object(rec, "_init_webcam_source", return_value=ws / "v.mp4"), \
                 patch.object(rec, "_sample_chunk_multimodal_frames", return_value=sb), \
                 patch.object(rec, "_balance_dynamic_chunk_frames", return_value=(sb, wc, "high(mad=0.140)")), \
                 patch.object(rec, "_call_chunk_model", return_value='{"is_continuation": true, "chunk_summary": "ok"}'), \
                 patch.object(rec, "finalize_and_assemble_timestamps", return_value=(ws / "out.md", [])), \
                 redirect_stdout(out):
                rec.run_recursive_mode(
                    ws, [chunks_dir / "chunk_00.txt"], "http://localhost:1234", "m",
                    "th", 500, 0.1, {}, [], True, 1, True, 40,
                )
        text = out.getvalue()
        self.assertIn("storyboard=1 webcam=1 -> running", text)


if __name__ == "__main__":
    unittest.main()
