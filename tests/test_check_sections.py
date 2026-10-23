import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_sections.py"

VALID_MD = textwrap.dedent("""\
    ══════════════════════════
    📌 ส่วนที่ 1: บทนำการ
    (หัวข้อ: Intro | ⏱ เริ่ม: 00:00:00)
    ══════════════════════════
    00:00:00 - [Greeting] สวัสดี
    00:01:00 - [Talk] คุย
""")

# 1,700 Thai chars × 3 bytes = 5,100 bytes → over the 4,500-byte cap
OVER_LIMIT_MD = VALID_MD + ("00:02:00 - [Talk] " + "ก" * 1700 + "\n")


class TestCheckSections(unittest.TestCase):
    def _run(self, md: str, tmp_path: Path) -> int:
        f = tmp_path / "out.md"
        f.write_text(md, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(f)],
            capture_output=True,
            env=env,
        )
        return result.returncode

    def test_valid_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(VALID_MD, Path(tmp)), 0)

    def test_over_limit_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotEqual(self._run(OVER_LIMIT_MD, Path(tmp)), 0)

    def test_no_sections_exits_zero(self):
        """Non-timestamp .md files (no ═══ blocks) must not block the agent's write."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run("# Just a notes file\nNo sections here.", Path(tmp)), 0)

    def test_suggest_split_byte_midpoint(self):
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        from check_sections import suggest_split

        # Body with a large block of Thai characters (3 bytes each)
        # The midpoint in bytes will fall into the large block.
        # We expect the suggestion to find the closest timestamp line.
        body1 = "00:00:00 - start\n" + ("ก" * 1000) + "\n00:01:00 - middle\n00:02:00 - end\n"
        self.assertEqual(suggest_split(body1), "00:01:00")

        body2 = "00:00:00 - start\n00:01:00 - middle\n" + ("ก" * 1000) + "\n00:02:00 - end\n"
        self.assertEqual(suggest_split(body2), "00:01:00")


if __name__ == "__main__":
    unittest.main()
