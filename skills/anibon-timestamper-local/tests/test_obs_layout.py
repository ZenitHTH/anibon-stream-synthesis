"""Tests for OBS layout detection, FaceBox derivation, and cut-boundary splitting."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox, WindowBounds
from video.obs_layout import (
    classify_layout_from_frames,
    detect_layout_cuts,
    detect_obs_layout,
    resolve_webcam_and_face_boxes,
    split_around_cuts,
)


def _solid_frame(size: int, rgb: tuple[int, int, int]) -> bytes:
    return bytes(rgb) * (size * size)


def _paint_box(size: int, box: FaceBox, rgb: tuple[int, int, int]) -> bytes:
    buf = bytearray(_solid_frame(size, (15, 15, 15)))
    x0, x1 = int(box.x * size), int((box.x + box.w) * size)
    y0, y1 = int(box.y * size), int((box.y + box.h) * size)
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes(rgb)
    return bytes(buf)


class TestObsLayout(unittest.TestCase):
    def test_corner_presets_and_tight_face_within_unit_bounds(self) -> None:
        for name in ("top-right", "mid-right", "mid-left", "bottom-right", "bottom-left", "top-left"):
            wb = WEBCAM_BOX_PRESETS[name]
            self.assertIsNotNone(wb)
            fb = wb.derive_tight_face()
            self.assertGreaterEqual(fb.x, wb.x)
            self.assertGreaterEqual(fb.y, wb.y)
            self.assertLessEqual(fb.x + fb.w, wb.x + wb.w + 1e-6)
            self.assertLessEqual(fb.y + fb.h, wb.y + wb.h + 1e-6)

    def test_fullscreen_keeps_full_room_and_no_crop(self) -> None:
        wb, fb = resolve_webcam_and_face_boxes("fullscreen")
        self.assertEqual((wb.x, wb.y, wb.w, wb.h), (0.0, 0.0, 1.0, 1.0))
        self.assertIsNone(wb.to_ffmpeg_crop())
        self.assertIsNotNone(fb)
        self.assertIsNotNone(fb.to_ffmpeg_crop())

    def test_layout_cut_mid_window_splits_and_suppresses_zone(self) -> None:
        pre = [_solid_frame(16, (20, 20, 20)) for _ in range(16)]
        post = [_solid_frame(16, (230, 230, 230)) for _ in range(24)]
        frames = pre + post
        cuts = detect_layout_cuts(frames, fps=2.0, cut_mad_floor=0.22)
        self.assertEqual(cuts, [16])
        lo, hi = split_around_cuts(len(frames), cuts, fps=2.0)
        self.assertGreaterEqual(lo, 20)
        self.assertEqual(hi, 40)

    def test_classify_layout_detects_mid_left_and_fullscreen(self) -> None:
        ml_box = WEBCAM_BOX_PRESETS["mid-left"]
        ml_frames = [_paint_box(32, ml_box, ((i * 55) % 250, 40, 80)) for i in range(6)]
        self.assertEqual(classify_layout_from_frames(ml_frames, sample_size=32, fps=2.0).layout, "mid-left")

        center = FaceBox(0.32, 0.15, 0.36, 0.55)
        fs_frames = [_paint_box(32, center, ((i * 55) % 250, 90, 40)) for i in range(6)]
        self.assertEqual(classify_layout_from_frames(fs_frames, sample_size=32, fps=2.0).layout, "fullscreen")

    def test_detect_obs_layout_honors_manual_preset_without_probe(self) -> None:
        bounds = WindowBounds(start_sec=10.0, end_sec=30.0)
        with patch("video.obs_layout._probe_full_frames") as mock_probe:
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="mid-right")
        mock_probe.assert_not_called()
        self.assertEqual(seg.layout, "mid-right")
        self.assertEqual(seg.webcam_box, WEBCAM_BOX_PRESETS["mid-right"])


if __name__ == "__main__":
    unittest.main()
