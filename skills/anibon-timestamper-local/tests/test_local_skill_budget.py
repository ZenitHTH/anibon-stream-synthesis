from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"


class TestLocalSkillBudget(unittest.TestCase):
    """Guard size budgets, portable links, and preserved rules for anibon-timestamper-local."""

    def test_hardware_and_endpoints_coverage(self) -> None:
        path = REFS_DIR / "hardware-and-endpoints.md"
        self.assertTrue(path.is_file(), "Missing references/hardware-and-endpoints.md")
        text = path.read_text(encoding="utf-8")
        for token in (
            "gemma-4-12b-it-qat@q4_k_xl",
            "gemma-4-26b-a4b-it@q2_k_xl",
            '"parallel": 1',
            "16384",
            "24576",
            "api.tokenme.limited",
            "--max-chunk-frames 8",
            "--reaction-verify",
            "mean_mad >= 0.095",
            "--eval-batch-size",
            "launch_local.ps1",
            "launch_local.bat",
            "config.json",
            "control_chunks_local.py",
        ):
            self.assertIn(token, text, f"hardware-and-endpoints.md missing: {token}")
        self.assertNotIn("config default `4096`", text)
        self.assertNotIn("anibon/config.py", text)


if __name__ == "__main__":
    unittest.main()
