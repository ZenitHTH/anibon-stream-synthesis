"""Tests for live webcam corner classification and multimodal audio+chat peak selection."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from video.chunk_peak_select import (  # noqa: E402
    PeakSearchInput,
    detect_chunk_reaction_peaks,
    expand_peak_timestamps,
)
from video.live_corner_score import (  # noqa: E402
    CornerStats,
    is_live_webcam_stats,
    pick_best_live_corner,
    score_live_corner,
)
from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox  # noqa: E402


def _paint_box(buf: bytearray, size: int, box: FaceBox, rgb: tuple[int, int, int]) -> None:
    x0, x1 = int(box.x * size), int((box.x + box.w) * size)
    y0, y1 = int(box.y * size), int((box.y + box.h) * size)
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes(rgb)


def _fake_frame(size: int, rects: list[tuple[FaceBox, tuple[int, int, int]]]) -> bytes:
    buf = bytearray([15, 18, 28] * (size * size))
    for box, rgb in rects:
        _paint_box(buf, size, box, rgb)
    return bytes(buf)


class TestLiveCornerAndPeaks(unittest.TestCase):
    """Verify UI rejection, continuity preference, and audio+livechat peak selection."""

    def test_rejects_ui_and_accepts_quiet_live_webcam(self) -> None:
        shop_ui = CornerStats(WEBCAM_BOX_PRESETS["top-right"], mad=0.015, tone=0.089, green=0.0, bright=0.04, blue_ui=0.04)
        bright_banner = CornerStats(WEBCAM_BOX_PRESETS["mid-right"], mad=0.09, tone=0.41, green=0.04, bright=0.29, blue_ui=0.0)
        blue_hud = CornerStats(WEBCAM_BOX_PRESETS["top-left"], mad=0.02, tone=0.18, green=0.0, bright=0.05, blue_ui=0.25)
        quiet_boat = CornerStats(WEBCAM_BOX_PRESETS["lower-right"], mad=0.008, tone=0.29, green=0.0, bright=0.0, blue_ui=0.01)
        self.assertFalse(is_live_webcam_stats(shop_ui))
        self.assertFalse(is_live_webcam_stats(bright_banner))
        self.assertFalse(is_live_webcam_stats(blue_hud))
        self.assertTrue(is_live_webcam_stats(quiet_boat))

    def test_score_prefers_clean_lower_right_over_ui_clipped_mid_right(self) -> None:
        mid_right = CornerStats(WEBCAM_BOX_PRESETS["mid-right"], mad=0.069, tone=0.348, green=0.0, bright=0.0, blue_ui=0.11)
        lower_right = CornerStats(WEBCAM_BOX_PRESETS["lower-right"], mad=0.043, tone=0.304, green=0.0, bright=0.0, blue_ui=0.01)
        self.assertGreater(score_live_corner(lower_right), score_live_corner(mid_right))

    def test_pick_best_live_corner_keeps_preferred_when_live(self) -> None:
        tr = WEBCAM_BOX_PRESETS["top-right"]
        lr = WEBCAM_BOX_PRESETS["lower-right"]
        f1 = _fake_frame(48, [(tr, (180, 150, 130)), (lr, (190, 160, 140))])
        f2 = _fake_frame(48, [(tr, (192, 162, 142)), (lr, (210, 178, 156))])
        picked = pick_best_live_corner([f1, f2], preferred=tr)
        self.assertIsNotNone(picked)
        self.assertEqual(picked[2].name, "top-right")

    def test_detect_chunk_reaction_peaks_fuses_audio_and_livechat_and_promotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lc_dir = ws / "livechat"
            lc_dir.mkdir()
            lines = ["[04:14:42] 555\n", "[04:14:44] 5555\n", "[04:14:46] lol\n", "[04:14:48] OMG\n"]
            (lc_dir / "livechat_chunk_56.txt").write_text("".join(lines), encoding="utf-8")
            items = [{"start": 15120, "text": "intro"}, {"start": 15415, "text": "outro"}]
            fake_bins = [(15200, 0.5, 0.2), (15275, 3.1, 3.5), (15350, 2.2, 1.0)]
            with patch("video.chunk_peak_select.extract_chunk_rms_bins", return_value=fake_bins):
                peaks, max_z, promote = detect_chunk_reaction_peaks(PeakSearchInput(ws, items, "audio.m4a"))
            self.assertEqual(peaks[0], 15275)
            self.assertAlmostEqual(max_z, 3.1)
            self.assertTrue(promote)
            expanded = expand_peak_timestamps(peaks, items, max_frames=6)
            self.assertIn(15275, expanded)
            self.assertIn(15277, expanded)

    def test_grass_edge_webcam_accepted_while_livechat_rejected_and_islands_kept(self) -> None:
        from video.chunk_webcam_reprobe import _select_runs_to_check

        grass_cam = CornerStats(WEBCAM_BOX_PRESETS["lower-right"], mad=0.027, tone=0.28, green=0.19, bright=0.0, blue_ui=0.0)
        chat_bar = CornerStats(WEBCAM_BOX_PRESETS["bottom-right"], mad=0.02, tone=0.05, green=0.50, bright=0.0, blue_ui=0.05)
        self.assertTrue(is_live_webcam_stats(grass_cam))
        self.assertFalse(is_live_webcam_stats(chat_bar))
        skin = bytes([180, 150, 130] * (48 * 48))
        green = bytes([40, 200, 40] * (48 * 48))
        bufs = [green, green, skin, green, green]
        selected = _select_runs_to_check([(0, 2), (2, 3), (3, 5)], [0.0, 0.2, 0.2, 0.0], bufs)
        self.assertEqual(selected, [(0, 2), (2, 3), (3, 5)])


if __name__ == "__main__":
    unittest.main()
