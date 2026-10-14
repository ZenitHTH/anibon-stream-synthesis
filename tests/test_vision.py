import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from anibon import vision as _vision


class TestVision(unittest.TestCase):
    def test_keywords_filter(self):
        test_items = [
            {"text": "สวัสดีครับวันนี้มาเล่นเกม", "start": 0, "timestamp": "00:00:00"},
            {"text": "คนนี้แหละที่เราจะพูดถึง", "start": 10, "timestamp": "00:00:10"},
            {"text": "who is this character on screen?", "start": 20, "timestamp": "00:00:20"},
            {"text": "ไม่มีคีย์เวิร์ดเลยนะ", "start": 30, "timestamp": "00:00:30"}
        ]

        patterns = [re.compile(p, re.I) for p in _vision.KEYWORDS]

        matched = []
        for item in test_items:
            if any(p.search(item["text"]) for p in patterns):
                matched.append(item)

        self.assertEqual(len(matched), 2)
        self.assertEqual(matched[0]["start"], 10)
        self.assertEqual(matched[1]["start"], 20)

    @patch("subprocess.run")
    def test_download_reference_video(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_run.return_value = mock_proc

            result = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
            self.assertEqual(result, tmp_path / "reference_video.mp4")
            mock_run.assert_called_once()

            (tmp_path / "reference_video.mp4").touch()
            mock_run.reset_mock()
            result_existing = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
            self.assertEqual(result_existing, tmp_path / "reference_video.mp4")
            mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_extract_frame_timeout(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15)

            video_path = tmp_path / "reference_video.mp4"
            out_path = tmp_path / "frame.jpg"

            result = _vision.extract_frame(video_path, 10.5, out_path)
            self.assertFalse(result)
            mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
