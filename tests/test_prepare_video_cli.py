from __future__ import annotations
import re
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN_ROOT / "scripts" / "prepare_video.py"


class TestPrepareVideoCLI(unittest.TestCase):
    def test_cli_help(self):
        self.assertTrue(SCRIPT.is_file(), "scripts/prepare_video.py must exist as a real file")
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PLUGIN_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--no-storyboard", res.stdout)
        self.assertIn("--vision", res.stdout)
        self.assertIn("--format", res.stdout)

    def test_cli_help_includes_sub_langs(self):
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PLUGIN_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--sub-langs", res.stdout)
        normalized_stdout = re.sub(r"\s+", "", res.stdout)
        self.assertIn("th-orig,en-orig,th,en", normalized_stdout)

    def test_download_transcript_prefers_orig_and_supports_english_json3(self):
        import tempfile
        from unittest.mock import patch
        import sys as _sys
        _sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
        from download.ytdlp import download_transcript

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            def fake_run(cmd, **kwargs):
                (ws / "raw_transcript.en.json3").write_text('{"events": [{"segs": [{"utf8": "translated"}]}]}', encoding="utf-8")
                (ws / "raw_transcript.en-orig.json3").write_text('{"events": [{"segs": [{"utf8": "original"}]}]}', encoding="utf-8")

            with patch("subprocess.run", side_effect=fake_run):
                download_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                out = ws / "raw_transcript.json"
                self.assertTrue(out.is_file())
                self.assertIn("original", out.read_text(encoding="utf-8"))

    def test_save_metadata_writes_compact_info_json_and_handles_none(self):
        import json
        import tempfile
        from unittest.mock import patch
        import sys as _sys
        _sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
        from download.ytdlp import save_metadata

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            fake_meta = {
                "id": "dQw4w9WgXcQ",
                "title": "Test Meeting Video",
                "upload_date": "20261025",
                "release_timestamp": 1792944000,
                "duration": 1800,
                "channel": "Test Channel",
                "uploader": "Test Uploader",
                "formats": [{"huge": "ignored"}],
            }
            with patch("download.ytdlp.probe_metadata", return_value=fake_meta):
                info_path = save_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                self.assertEqual(info_path, ws / "info.json")
                saved = json.loads(info_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["upload_date"], "20261025")
                self.assertEqual(saved["title"], "Test Meeting Video")
                self.assertNotIn("formats", saved)

        with tempfile.TemporaryDirectory() as tmp2:
            ws2 = Path(tmp2)
            with patch("download.ytdlp.probe_metadata", return_value=None):
                self.assertIsNone(save_metadata("https://www.youtube.com/watch?v=bad", ws2))


if __name__ == "__main__":
    unittest.main()
