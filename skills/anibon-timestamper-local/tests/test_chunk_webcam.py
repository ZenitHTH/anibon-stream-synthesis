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

    def test_reprobe_splits_and_rerenders_mid_chunk_corner_switch(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box_a = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
            box_b = FaceBox(0.77, 0.55, 0.23, 0.23, "lower-right")
            renders: list[tuple[int, str]] = []

            def fake_render(src_vf: tuple, out_jpg: Path, sec: float) -> bool:
                renders.append((int(sec), src_vf[1]))
                out_jpg.parent.mkdir(parents=True, exist_ok=True)
                out_jpg.write_bytes(src_vf[1].encode("utf-8"))
                return True

            def fake_decode(path: Path, _box: FaceBox) -> bytes:
                sec = int(path.stem[3:])
                val = 10 if (sec < 200 or "0.5500" in path.read_text()) else 240
                return bytes([val] * (48 * 48 * 3))

            def fake_layout(_src: Path, bounds: object, preferred: str = "auto") -> LayoutSegment:
                chosen = box_b if bounds.start_sec >= 200 else box_a
                return LayoutSegment(chosen.name, chosen, chosen.derive_tight_face())

            req = ChunkWebcamRequest(
                workspace=ws, source=vid, chunk={"_idx": 5, "items": []},
                target_secs=(100, 120, 220, 240), preferred="auto", max_frames=4,
                webcam_box=box_a, layout_fn=fake_layout, render_fn=fake_render,
            )
            with patch("video.chunk_webcam_reprobe.decode_tile_box", side_effect=fake_decode):
                sample_chunk_webcam_frames(req)
            rerenders_b = [s for s, vf in renders if s >= 220 and "0.5500" in vf]
            self.assertEqual(rerenders_b, [220, 240])
            self.assertIn("0.5500", (ws / "frames/webcam_chunk/wc_000240.jpg").read_text())

    def test_reprobe_recovers_dead_crop_and_respects_manual_corner(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box_dead = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
            box_live = FaceBox(0.77, 0.55, 0.23, 0.23, "lower-right")
            renders: list[tuple[int, str]] = []

            def fake_render(src_vf: tuple, out_jpg: Path, sec: float) -> bool:
                renders.append((int(sec), src_vf[1]))
                out_jpg.parent.mkdir(parents=True, exist_ok=True)
                out_jpg.write_bytes(src_vf[1].encode("utf-8"))
                return True

            req_auto = ChunkWebcamRequest(
                workspace=ws, source=vid, chunk={"_idx": 6, "items": []},
                target_secs=(300, 320), preferred="auto", max_frames=2, webcam_box=box_dead,
                layout_fn=lambda *a, **k: LayoutSegment("lower-right", box_live, box_live.derive_tight_face()),
                render_fn=fake_render,
            )
            with patch("video.chunk_webcam_reprobe.decode_tile_box", return_value=bytes([50] * 6912)):
                sample_chunk_webcam_frames(req_auto)
            self.assertIn("0.5500", (ws / "frames/webcam_chunk/wc_000320.jpg").read_text())

            renders.clear()
            req_manual = ChunkWebcamRequest(
                workspace=ws, source=vid, chunk={"_idx": 7, "items": []},
                target_secs=(400, 420), preferred="top-right", max_frames=2, webcam_box=box_dead,
                layout_fn=lambda *a, **k: LayoutSegment("lower-right", box_live, box_live.derive_tight_face()),
                render_fn=fake_render,
            )
            with patch("video.chunk_webcam_reprobe.decode_tile_box", return_value=bytes([50] * 6912)):
                sample_chunk_webcam_frames(req_manual)
            self.assertEqual(len(renders), 2)

    def test_consensus_picker_queries_quarter_anchors_on_weak_midpoint(self) -> None:
        from unittest.mock import patch
        from process.runners.corner_consensus import pick_consensus_corner
        b_flash = FaceBox(0.0, 0.7, 0.25, 0.3, "bottom-left")
        b_real = FaceBox(0.77, 0.55, 0.23, 0.23, "lower-right")
        probed_centers: list[int] = []

        def fake_probe(_src: Path, bounds: object) -> list[bytes]:
            center = int(bounds.start_sec) + 2
            probed_centers.append(center)
            return [bytes([center % 250] * 6912)] * 3

        def fake_rank(clean: list[bytes], _sb: object) -> list[tuple[bool, float, FaceBox]]:
            tag = clean[0][0]
            if tag == (1127 % 250):  # midpoint of [990..1264]
                return [(True, 0.11, b_flash)]
            return [(True, 0.42, b_real), (True, 0.10, b_flash)]

        with patch("process.runners.corner_consensus._probe_full_frames", side_effect=fake_probe):
            picked = pick_consensus_corner(Path("v.mp4"), (990, 1264), [(), ()], fake_rank)
        self.assertEqual(picked.name, "lower-right")
        self.assertGreaterEqual(len(probed_centers), 3)


if __name__ == "__main__":
    unittest.main()
