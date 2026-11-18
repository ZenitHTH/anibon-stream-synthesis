"""Unit tests for dynamic storyboard vs webcam allocation based on corner motion."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from video.dynamic_balance import (  # noqa: E402
    DynamicPlan,
    assess_storyboard_webcam_motion,
    plan_dynamic_allocation,
)
from video.motion_types import WEBCAM_BOX_PRESETS  # noqa: E402


def _make_tile(path: Path, bg_color: str, corner_color: str) -> None:
    """Render a 160x90 test tile with solid background and mid-right corner color."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # mid-right preset: x=0.75..1.0, y=0.33..0.65 -> on 160x90: x=120 w=40 y=30 h=29
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={bg_color}:s=160x90",
            "-vf", f"drawbox=x=120:y=30:w=40:h=29:color={corner_color}@1.0:t=fill",
            "-frames:v", "1", str(path),
        ],
        check=True,
        timeout=10,
    )


class TestDynamicBalance(unittest.TestCase):
    """Verify dynamic allocation shifts to webcam on high motion and screen on calm."""

    def test_plan_dynamic_allocation_tiers(self) -> None:
        low = plan_dynamic_allocation(mean_mad=0.065, has_emotion_cue=False, avail_slots=16)
        self.assertEqual(low.tier, "low")
        self.assertGreaterEqual(low.sb_keep, 12)
        self.assertEqual(low.wc_frames, 0)

        low_cue = plan_dynamic_allocation(mean_mad=0.065, has_emotion_cue=True, avail_slots=16)
        self.assertEqual(low_cue.tier, "low")
        self.assertGreaterEqual(low_cue.sb_keep, 10)
        self.assertEqual(low_cue.wc_frames, 4)

        med = plan_dynamic_allocation(mean_mad=0.11, has_emotion_cue=False, avail_slots=16)
        self.assertEqual(med.tier, "medium")
        self.assertEqual(med.wc_frames, 6)

        high = plan_dynamic_allocation(mean_mad=0.15, has_emotion_cue=False, avail_slots=16)
        self.assertEqual(high.tier, "high")
        self.assertLessEqual(high.sb_keep, 6)
        self.assertGreaterEqual(high.wc_frames, 12)

    def test_assess_storyboard_webcam_motion_detects_static_vs_expressive(self) -> None:
        box = WEBCAM_BOX_PRESETS["mid-right"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # 1. Static corner (only background changes slightly, corner identical red) -> low
            calm_tiles = []
            for i, bg in enumerate(("0x101010", "0x202020", "0x151515", "0x181818")):
                p = ws / f"calm_{i}.jpg"
                _make_tile(p, bg, "red")
                calm_tiles.append((f"00:01:{i*10:02d}", p, "AA=="))
            calm_res = assess_storyboard_webcam_motion(calm_tiles, box)
            self.assertEqual(calm_res.tier, "low")

            # 2. Highly active corner alternating bright colors -> high motion spikes
            active_tiles = []
            for i, cc in enumerate(("black", "white", "blue", "yellow")):
                p = ws / f"act_{i}.jpg"
                _make_tile(p, "0x181818", cc)
                active_tiles.append((f"00:02:{i*10:02d}", p, "BB=="))
            act_res = assess_storyboard_webcam_motion(active_tiles, box)
            self.assertEqual(act_res.tier, "high")
            self.assertGreater(len(act_res.spike_secs), 0)

    def test_balance_dynamic_chunk_frames_allocates_by_motion(self) -> None:
        from unittest.mock import patch
        from types import SimpleNamespace
        from process.runners import dynamic_chunk as dc
        box = WEBCAM_BOX_PRESETS["mid-right"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "v.mp4"
            vid.write_bytes(b"0")
            args = SimpleNamespace(webcam_corner="mid-right")
            items = [{"start": 100.0 + i * 10, "text": "คุยปกติ"} for i in range(10)]
            chunk = {"_idx": 1, "items": items}
            calm_tiles = []
            for i in range(10):
                p = ws / f"c_{i}.jpg"
                _make_tile(p, "0x101010", "red")
                calm_tiles.append((f"00:01:{40 + i*10:02d}", p, "AA=="))
            sb_calm, wc_calm, tier_calm = dc._balance_dynamic_chunk_frames(ws, chunk, calm_tiles, vid, args)
            self.assertEqual(len(sb_calm), 10)
            self.assertEqual(wc_calm, [])
            self.assertTrue(tier_calm.startswith("low("))

            hot_tiles = []
            for i, col in enumerate(("black", "white", "blue", "yellow", "black", "white", "green", "red", "white", "black")):
                p = ws / f"h_{i}.jpg"
                _make_tile(p, "0x101010", col)
                hot_tiles.append((f"00:01:{40 + i*10:02d}", p, "BB=="))
            captured: list[int] = []
            def fake_wc(req):
                captured.append(req.max_frames)
                return [("00:01:40", ws / "sheet.jpg", "CC==", "WEBCAM STORYBOARD")]
            with patch.object(dc, "sample_chunk_webcam_frames", side_effect=fake_wc):
                sb_hot, wc_hot, tier_hot = dc._balance_dynamic_chunk_frames(ws, chunk, hot_tiles, vid, args)
            self.assertLessEqual(len(sb_hot), 6)
            self.assertEqual(len(wc_hot), 1)
            self.assertEqual(captured, [12])
            self.assertTrue(tier_hot.startswith("high("))


if __name__ == "__main__":
    unittest.main()
