"""Unit tests for standardized aligned pipeline logger (common.log)."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from common import log as alog  # noqa: E402
from process.reaction_verify import VerifyOptions, verify_reaction_stamps  # noqa: E402
from video.motion_types import FaceBox, FaceMotionSample, LayoutSegment  # noqa: E402


class TestCommonLog(unittest.TestCase):
    """Verify fixed-column alignment, progress formatting, and stream routing."""

    def setUp(self) -> None:
        alog.set_clock(lambda: datetime(2026, 11, 18, 10, 15, 3))

    def tearDown(self) -> None:
        alog.set_clock(None)

    def test_column_alignment_across_levels_and_continuation(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            alog.log_info("init", "starting run")
            alog.log_ok("chunk", "done chunk_00")
            alog.log_cont("00:01:59 - [Intro] เปิดไลฟ์")
            alog.log_warn("multimodal", "fallback text-only")
            alog.log_error("network", "timeout reached")

        lines = out.getvalue().splitlines() + err.getvalue().splitlines()
        self.assertEqual(len(lines), 5)
        pipes = [[i for i, ch in enumerate(ln) if ch == "|"] for ln in lines]
        self.assertTrue(all(p == [9, 17, 30] for p in pipes), f"Misaligned pipes: {lines}")
        self.assertTrue(lines[0].startswith("10:15:03 | INFO  | init       | "))
        self.assertTrue(lines[1].startswith("10:15:03 | OK    | chunk      | "))
        self.assertTrue(lines[2].startswith("         |       |            | "))
        self.assertTrue(lines[3].startswith("10:15:03 | WARN  | multimodal | "))
        self.assertTrue(lines[4].startswith("10:15:03 | ERROR | network    | "))

    def test_kv_progress_duration_and_block(self) -> None:
        self.assertEqual(alog.format_progress(1, 95), "[01/95   1%]")
        self.assertEqual(alog.format_progress(95, 95), "[95/95 100%]")
        self.assertEqual(alog.format_duration(28.44), "28.4s")
        self.assertEqual(alog.format_duration(358.2), "5m58s")
        self.assertEqual(alog.format_duration(3905.0), "1h05m")

        out = io.StringIO()
        with redirect_stdout(out):
            alog.log_kv("init", "workspace", "/tmp/ws")
            alog.log_kv("init", "model", "gemma4")
            alog.log_block("gate", "INFO", "line one\nline two\n")

        lines = out.getvalue().splitlines()
        self.assertIn("workspace       : /tmp/ws", lines[0])
        self.assertIn("model           : gemma4", lines[1])
        self.assertTrue(lines[2].endswith("| line one"))
        self.assertEqual(lines[3], "         |       |            | line two")

    def test_banner_and_stage_widths(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            alog.log_banner("ANIBON TIMESTAMPER")
            alog.log_stage("PASS 1")

        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "=" * 78)
        self.assertEqual(lines[1], "  ANIBON TIMESTAMPER")
        self.assertEqual(lines[2], "=" * 78)
        self.assertEqual(lines[3], "-" * 78)
        self.assertEqual(lines[4], "  PASS 1")
        self.assertEqual(lines[5], "-" * 78)

    def test_reaction_verify_emits_aligned_stage_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"0")
            box = FaceBox(0.75, 0.33, 0.25, 0.32, "mid-right")
            layout = LayoutSegment("mid-right", box, box.derive_tight_face())
            samples = tuple(
                FaceMotionSample(i, float(i), float(18 + i), f"00:00:{18 + i:02d}", 0.01, 0.01 if i < 4 else 0.28, 0.01, 0.01, 0.01, 0.5 if i < 4 else 6.0, 0.01)
                for i in range(7)
            )
            opts = VerifyOptions(
                source=vid, endpoint="http://localhost:1234", model="test",
                context_fn=lambda _: "ตกใจสุดขีด",
                layout_fn=lambda *a, **k: layout,
                motion_fn=lambda *a, **k: (samples, samples, 0.01),
                export_fn=lambda *a, **k: {"frames": [{"ts": "00:00:22", "path": str(vid), "b64": "AA=="}]},
                call_fn=lambda *a, **k: '{"snapped_ts": "00:00:22", "emotion_class": "shock", "confidence": 0.91}',
            )
            out = io.StringIO()
            with redirect_stdout(out):
                res = verify_reaction_stamps(["00:00:20 - [Reaction] เหวอ"], ws, opts)

        self.assertEqual(res, ["00:00:22 - [Reaction] เหวอ"])
        text = out.getvalue()
        self.assertIn("PASS 2 :: WEBCAM REACTION VERIFY", text)
        self.assertIn("10:15:03 | INFO  | reaction   | [01] 00:00:20 | layout=mid-right", text)
        self.assertIn("10:15:03 | OK    | reaction   | [01] 00:00:20 -> 00:00:22 (+2s) | shock (conf=0.91)", text)
        self.assertIn("10:15:03 | OK    | reaction   | summary: checked=1, snapped=1", text)


if __name__ == "__main__":
    unittest.main()
