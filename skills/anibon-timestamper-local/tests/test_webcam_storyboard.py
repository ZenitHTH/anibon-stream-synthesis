"""Unit tests for packing cropped webcam frames into storyboard grid sheets."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from video.webcam_storyboard import (  # noqa: E402
    assemble_webcam_storyboard,
    count_packed_panels,
    grid_dims,
)


def _make_color_jpg(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=256x256", "-frames:v", "1", str(path)],
        check=True,
        timeout=10,
    )


class TestWebcamStoryboard(unittest.TestCase):
    """Verify grid geometry, ffmpeg sheet assembly, and graceful dummy fallback."""

    def test_grid_dims_scales_cleanly(self) -> None:
        self.assertEqual(grid_dims(1), (1, 1))
        self.assertEqual(grid_dims(2), (2, 1))
        self.assertEqual(grid_dims(4), (2, 2))
        self.assertEqual(grid_dims(6), (3, 2))
        self.assertEqual(grid_dims(9), (3, 3))

    def test_assembles_real_jpegs_into_grid_sheet_with_panel_legend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            inputs = []
            for idx, (ts, role, color) in enumerate(
                [("00:07:10", "baseline", "red"), ("00:07:15", "onset", "green"),
                 ("00:07:20", "peak", "blue"), ("00:07:25", "post", "yellow")],
                start=1,
            ):
                p = ws / f"f_{idx}.jpg"
                _make_color_jpg(p, color)
                inputs.append((ts, p, "AA==", role))

            out_sheet = ws / "wc_sheet.jpg"
            sheet = assemble_webcam_storyboard(inputs, out_sheet)
            self.assertIsNotNone(sheet)
            assert sheet is not None
            self.assertTrue(out_sheet.is_file())
            self.assertGreater(out_sheet.stat().st_size, 500)
            self.assertIn("WEBCAM STORYBOARD (2x2", sheet[3])
            self.assertIn("[1]=00:07:10", sheet[3])
            self.assertIn("[4]=00:07:25", sheet[3])
            self.assertEqual(count_packed_panels([sheet]), 4)

    def test_falls_back_cleanly_on_invalid_dummy_jpegs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            p1, p2 = ws / "d1.jpg", ws / "d2.jpg"
            p1.write_bytes(b"fake")
            p2.write_bytes(b"fake")
            sheet = assemble_webcam_storyboard(
                [("00:01:00", p1, "AA==", "a"), ("00:01:05", p2, "BB==", "b")],
                ws / "sheet.jpg",
            )
            self.assertIsNone(sheet)


if __name__ == "__main__":
    unittest.main()
