from __future__ import annotations
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


if __name__ == "__main__":
    unittest.main()
