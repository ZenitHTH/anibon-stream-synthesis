"""Tests for calibrated 2.0 fps Dual-Box kinematics, posture_act, and keyframe export."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video.face_motion import FrameExportSpec, export_vlm_keyframes, extract_dual_motion_series
from video.face_motion_metrics import classify_dual_regime, score_motion_series
from video.motion_types import FaceBox, KeyframePick, LayoutSegment, RegimeThresholds, WindowBounds


def _pattern_frame(size: int, shift: int, colors: tuple[int, int] = (25, 210)) -> bytes:
    bg, fg = colors
    buf = bytearray([bg] * (size * size * 3))
    for y in range(2, size - 2):
        for x in range(2, size - 2):
            val = fg if ((x + shift) % 4 < 2 and (y + shift) % 4 < 2) else bg
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes((val, val // 2, 40))
    return bytes(buf)


def _rect_frame(size: int, rect: tuple[int, int, int, int], fg: int = 220) -> bytes:
    buf = bytearray([20] * (size * size * 3))
    x0, y0, x1, y1 = rect
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes((fg, fg, 60))
    return bytes(buf)


class TestFaceMotion(unittest.TestCase):
    def test_calm_news_talking_on_f_suppresses_vlm(self) -> None:
        f_frames = [_rect_frame(16, (4 + (i % 2), 4, 11, 11), fg=150) for i in range(50)]
        w_frames = [_rect_frame(16, (3 + (i % 3), 3, 12, 12), fg=160) for i in range(50)]
        f_samples, _ = score_motion_series(f_frames, fps=2.0)
        w_samples, _ = score_motion_series(w_frames, fps=2.0)
        res = classify_dual_regime(f_samples, w_samples, RegimeThresholds())
        self.assertEqual(res.regime, "calm_news")
        self.assertFalse(res.trigger_vlm)

    def test_stunned_freeze_holds_plateau_and_keeps_15s_local_anchor(self) -> None:
        pre = [_rect_frame(16, (2, 2, 6, 6), fg=180) for _ in range(36)]
        burst = [_rect_frame(16, (8, 8, 13, 13), fg=240), _rect_frame(16, (9, 9, 14, 14), fg=240)]
        freeze = [_rect_frame(16, (9, 9, 14, 14), fg=240) for _ in range(10)]
        f_samples, _ = score_motion_series(pre + burst + freeze, fps=2.0)
        w_samples, _ = score_motion_series(pre + burst + freeze, fps=2.0)
        res = classify_dual_regime(f_samples, w_samples, RegimeThresholds())
        self.assertEqual(res.regime, "stunned_freeze")
        self.assertTrue(res.trigger_vlm)
        self.assertEqual(len(res.keyframes), 4)
        self.assertLessEqual(res.keyframes[1].rel_sec - res.keyframes[0].rel_sec, 15.0)

    def test_chair_vacated_bed_retreat_routes_to_posture_act_not_freeze(self) -> None:
        f_pre = [_rect_frame(16, (4, 4, 10, 10), fg=200) for _ in range(12)]
        f_empty = [_rect_frame(16, (0, 0, 1, 1), fg=20) for _ in range(28)]
        w_pre = [_rect_frame(16, (5, 5, 10, 10), fg=210) for _ in range(12)]
        w_walk = [_rect_frame(16, (1 + i, 2, 7 + i, 12), fg=220) for i in range(6)]
        w_bed = [_rect_frame(16, (10, 1, 15, 6), fg=220) for _ in range(22)]
        f_samples, _ = score_motion_series(f_pre + f_empty, fps=2.0)
        w_samples, _ = score_motion_series(w_pre + w_walk + w_bed, fps=2.0)
        res = classify_dual_regime(f_samples, w_samples, RegimeThresholds())
        self.assertEqual(res.regime, "posture_act")
        self.assertNotEqual(res.regime, "stunned_freeze")
        post_kf = [k for k in res.keyframes if k.role == "post_peak_state"][0]
        self.assertGreaterEqual(post_kf.rel_sec - res.peak_rel_sec, 2.5)

    def test_sustained_angry_triggers_on_high_mean_and_rms_vel(self) -> None:
        frames = [_pattern_frame(16, i % 4, (20, 240)) for i in range(24)]
        f_samples, _ = score_motion_series(frames, fps=2.0)
        w_samples, _ = score_motion_series(frames, fps=2.0)
        res = classify_dual_regime(f_samples, w_samples, RegimeThresholds())
        self.assertEqual(res.regime, "angry")
        self.assertTrue(res.trigger_vlm)

    def test_shock_burst_from_w_spike_and_earliest_onset_precedes_peak(self) -> None:
        calm = [_rect_frame(16, (4, 4, 9, 9), fg=150) for _ in range(16)]
        f_frames = calm + [_rect_frame(16, (4 + (i % 2), 4, 10, 10), fg=165) for i in range(6)] + calm[:12]
        w_burst = [_rect_frame(16, (1, 1, 14, 14), fg=250), _rect_frame(16, (0, 0, 16, 16), fg=255)]
        w_frames = calm + w_burst + calm[:16]
        f_samples, _ = score_motion_series(f_frames, fps=2.0)
        w_samples, _ = score_motion_series(w_frames, fps=2.0)
        res = classify_dual_regime(f_samples, w_samples, RegimeThresholds())
        self.assertEqual(res.regime, "shock_burst")
        self.assertLessEqual(res.onset_rel_sec, res.peak_rel_sec)

    def test_extract_dual_motion_series_splits_around_layout_cut(self) -> None:
        pre = [_pattern_frame(16, 0, (15, 30)) for _ in range(16)]
        post = [_pattern_frame(16, 2, (220, 240)) for _ in range(24)]
        seg = LayoutSegment("fullscreen", FaceBox(0, 0, 1, 1), FaceBox(0.3, 0.0, 0.4, 0.6))
        bounds = WindowBounds(start_sec=0.0, end_sec=20.0, fps=2.0, sample_size=16)
        with patch("video.face_motion.extract_raw_rgb_frames", side_effect=[(pre + post, []), (pre + post, [])]):
            f_s, w_s, cuts = extract_dual_motion_series(Path("dummy.mp4"), bounds, seg)
        self.assertEqual(cuts, (8.0,))
        self.assertLess(len(w_s), 40)
        self.assertGreaterEqual(w_s[0].abs_sec, 9.5)
        self.assertTrue(all(s.z_score < 2.0 for s in f_s))

    def test_export_vlm_keyframes_writes_w_strip_without_drawtext(self) -> None:
        kfs = (KeyframePick("pre_onset_baseline", 0, 0.0, 10.0, "00:00:10", 0.0, 0.0, 0.0),
               KeyframePick("peak_delta", 4, 2.0, 12.0, "00:00:12", 0.1, 0.2, 4.0))
        with tempfile.TemporaryDirectory() as tmp:
            spec = FrameExportSpec(kfs, FaceBox(0, 0, 1, 1), Path(tmp))
            def _fake_run(cmd: list[str], **_kw: object) -> object:
                self.assertNotIn("drawtext", " ".join(cmd))
                Path(cmd[-1]).write_bytes(b"jpg")
                return type("R", (), {"returncode": 0})()
            with patch("video.face_motion.subprocess.run", side_effect=_fake_run):
                out = export_vlm_keyframes(Path("vid.mp4"), spec)
        self.assertEqual(len(out["frames"]), 2)
        self.assertIsNotNone(out["strip_path"])


if __name__ == "__main__":
    unittest.main()
