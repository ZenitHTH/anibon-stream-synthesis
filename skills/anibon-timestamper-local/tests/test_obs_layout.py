"""Tests for OBS layout detection, FaceBox derivation, and cut-boundary splitting."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from video.auto_tracker import track_webcam_any_position
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

    def test_offline_fallback_honors_preset(self) -> None:
        bounds = WindowBounds(start_sec=10.0, end_sec=30.0)
        with patch("video.obs_layout._probe_full_frames", return_value=[]) as mock_probe:
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="mid-right")
        mock_probe.assert_called_once()
        self.assertEqual(seg.layout, "mid-right")
        self.assertEqual(seg.webcam_box, WEBCAM_BOX_PRESETS["mid-right"])

    def test_auto_tracker_handles_wide_fullscreen_and_static_none(self) -> None:
        wide = [_paint_box(32, FaceBox(0.1, 0.1, 0.8, 0.8), ((i * 55) % 250, 80, 90)) for i in range(4)]
        label_w, box_w = track_webcam_any_position(wide, sample_size=32)
        self.assertEqual(label_w, "fullscreen")
        self.assertEqual(box_w, WEBCAM_BOX_PRESETS["fullscreen"])
        static = [_solid_frame(32, (20, 20, 20)) for _ in range(4)]
        self.assertEqual(track_webcam_any_position(static, sample_size=32), ("none", None))

    def test_mid_window_pip_teleport_to_custom_box_splits_subsegment(self) -> None:
        bounds = WindowBounds(start_sec=0.0, end_sec=12.0)
        tr_box = WEBCAM_BOX_PRESETS["top-right"]
        custom = FaceBox(0.35, 0.58, 0.22, 0.28)
        h1 = [_paint_box(48, tr_box, ((i * 55) % 250, 70, 90)) for i in range(6)]
        h2 = [_paint_box(48, custom, ((i * 55) % 250, 90, 70)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=h1 + h2):
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="auto")
        self.assertEqual(seg.layout, "auto-tracked")
        self.assertIsNotNone(seg.clean_start_sec)
        self.assertGreaterEqual(seg.clean_start_sec, 5.0)
        self.assertEqual(seg.clean_end_sec, 12.0)
        self.assertTrue(len(seg.cut_secs) >= 1)
        self.assertGreater(seg.webcam_box.y, 0.45)

    def test_mid_window_pip_teleport_to_mid_left_under_fixed_preset(self) -> None:
        bounds = WindowBounds(start_sec=10.0, end_sec=22.0)
        tr_box, ml_box = WEBCAM_BOX_PRESETS["top-right"], WEBCAM_BOX_PRESETS["mid-left"]
        h1 = [_paint_box(48, tr_box, ((i * 55) % 250, 70, 90)) for i in range(6)]
        h2 = [_paint_box(48, ml_box, ((i * 55) % 250, 90, 70)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=h1 + h2):
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="top-right")
        self.assertIn(seg.layout, ("mid-left", "auto-tracked"))
        self.assertLess(seg.webcam_box.x, 0.05)
        self.assertGreaterEqual(seg.clean_start_sec, 15.0)
        self.assertEqual(seg.clean_end_sec, 22.0)

    def test_fixed_valid_skips_auto_tracker(self) -> None:
        bounds = WindowBounds(start_sec=0.0, end_sec=10.0)
        tr_box = WEBCAM_BOX_PRESETS["top-right"]
        frames = [_paint_box(48, tr_box, ((i * 55) % 250, 50, 90)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=frames), \
             patch("video.obs_layout.track_webcam_any_position") as mock_auto:
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="top-right")
        mock_auto.assert_not_called()
        self.assertEqual(seg.layout, "top-right")

    def test_fixed_empty_triggers_auto_tracker_at_custom_box(self) -> None:
        bounds = WindowBounds(start_sec=0.0, end_sec=10.0)
        custom = FaceBox(0.38, 0.62, 0.22, 0.28)
        frames = [_paint_box(48, custom, ((i * 55) % 250, 90, 40)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=frames):
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="top-right")
        self.assertEqual(seg.layout, "auto-tracked")
        self.assertIsNotNone(seg.webcam_box)
        self.assertGreater(seg.webcam_box.x, 0.25)
        self.assertGreater(seg.webcam_box.y, 0.50)

    def test_auto_mode_falls_back_to_arbitrary_box(self) -> None:
        bounds = WindowBounds(start_sec=0.0, end_sec=10.0)
        custom = FaceBox(0.38, 0.62, 0.22, 0.28)
        frames = [_paint_box(48, custom, ((i * 60) % 250, 40, 110)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=frames):
            seg = detect_obs_layout(Path("dummy.mp4"), bounds, preferred="auto")
        self.assertEqual(seg.layout, "auto-tracked")
        self.assertIsNotNone(seg.face_box)


if __name__ == "__main__":
    unittest.main()
