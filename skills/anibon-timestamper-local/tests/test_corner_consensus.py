"""Unit tests for fullscreen center fallback and blank/livechat reprobing."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from process.runners.corner_consensus import _maybe_center_fallback  # noqa: E402
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames  # noqa: E402
from video.motion_types import FaceBox, LayoutSegment  # noqa: E402


def _frame_with_center_skin(delta: int = 0) -> bytes:
    """Build a 48x48 RGB frame with blue curtain corners and warm active skin center."""
    buf = bytearray([20, 40, 120] * (48 * 48))
    r, g, b = min(240, 200 + delta), min(230, 165 + delta), min(210, 145 + delta)
    skin = bytes([r, g, b])
    for y in range(6, 40):
        for x in range(10, 38):
            idx = (y * 48 + x) * 3
            buf[idx : idx + 3] = skin
    return bytes(buf)


class TestCornerConsensusFallback(unittest.TestCase):
    """Verify fullscreen center promotion and blank/livechat reprobe triggers."""

    def test_maybe_center_fallback_promotes_fullscreen_skin_over_curtain(self) -> None:
        clean = [_frame_with_center_skin(0), _frame_with_center_skin(25), _frame_with_center_skin(0)]
        curtain_corner = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
        chosen_box, chosen_score = _maybe_center_fallback(clean, (curtain_corner, 0.10))
        self.assertEqual(chosen_box.name, "fullscreen")
        self.assertGreaterEqual(chosen_score, 0.25)

    def test_reprobe_triggers_on_moving_but_blank_face_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box_bad = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
            box_good = FaceBox(0.77, 0.55, 0.23, 0.23, "lower-right")

            def fake_render(src_vf: tuple, out_jpg: Path, sec: float) -> bool:
                out_jpg.parent.mkdir(parents=True, exist_ok=True)
                out_jpg.write_bytes(src_vf[1].encode("utf-8"))
                return True

            blue_frames = [bytes([20, 40, 120] * 6912), bytes([40, 60, 160] * 6912)]
            req = ChunkWebcamRequest(
                workspace=ws, source=vid, chunk={"_idx": 9, "items": []},
                target_secs=(100, 120), preferred="auto", max_frames=2, webcam_box=box_bad,
                layout_fn=lambda *a, **k: LayoutSegment("lower-right", box_good, box_good.derive_tight_face()),
                render_fn=fake_render,
            )
            with patch("video.chunk_webcam_reprobe.decode_tile_box", side_effect=blue_frames):
                sample_chunk_webcam_frames(req)
            self.assertIn("0.5500", (ws / "frames/webcam_chunk/wc_000120.jpg").read_text())

    def test_reprobe_triggers_on_green_livechat_overlay_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box_chat = FaceBox(0.75, 0.70, 0.25, 0.30, "bottom-right")
            box_good = FaceBox(0.77, 0.55, 0.23, 0.23, "lower-right")

            def fake_render(src_vf: tuple, out_jpg: Path, sec: float) -> bool:
                out_jpg.parent.mkdir(parents=True, exist_ok=True)
                out_jpg.write_bytes(src_vf[1].encode("utf-8"))
                return True

            # Scrolling green chat + warm avatars (passes face_tone & MAD, fails green_chat!)
            px_a = bytes(([30, 160, 60] * 1000) + ([200, 165, 145] * 200) + ([20, 20, 20] * 1104))
            px_b = bytes(([20, 20, 20] * 300) + ([30, 160, 60] * 1000) + ([200, 165, 145] * 200) + ([20, 20, 20] * 804))
            req = ChunkWebcamRequest(
                workspace=ws, source=vid, chunk={"_idx": 10, "items": []},
                target_secs=(100, 120), preferred="auto", max_frames=2, webcam_box=box_chat,
                layout_fn=lambda *a, **k: LayoutSegment("lower-right", box_good, box_good.derive_tight_face()),
                render_fn=fake_render,
            )
            with patch("video.chunk_webcam_reprobe.decode_tile_box", side_effect=[px_a, px_b]):
                sample_chunk_webcam_frames(req)
            self.assertIn("0.5500", (ws / "frames/webcam_chunk/wc_000120.jpg").read_text())


if __name__ == "__main__":
    unittest.main()
