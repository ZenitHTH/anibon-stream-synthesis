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

    def test_stage5_audit_checklist_coverage(self) -> None:
        path = REFS_DIR / "stage5-audit-checklist.md"
        text = path.read_text(encoding="utf-8")
        for token in (
            "livechat_events.txt",
            "t+90s",
            "atlas_fgo.db",
            "pokemon.db",
            "Dual-Track Desync",
            "cutoff=",
            "slide_",
            "Discord",
            "วิพากษ์",
            "[Victory]",
            "[Ending]",
            "[Donation]",
            "Rage-Quit",
            "Tokusatsu",
            "Kamen Rider Shinobi",
            "Strategy of Lily",
            "reaction_verify_log.json",
            "Stream Chronology & Play History",
            "scripts/audit_gaps.py",
            "scripts/check_sections.py",
            "update_garbled_dictionary.py",
        ):
            self.assertIn(token, text, f"stage5-audit-checklist.md missing: {token}")

    def test_troubleshooting_coverage(self) -> None:
        path = REFS_DIR / "troubleshooting.md"
        self.assertTrue(path.is_file(), "Missing references/troubleshooting.md")
        text = path.read_text(encoding="utf-8")
        for token in (
            "parse_live_chat.py",
            "extract_visual_livechat.py",
            "whisper_dispatcher.py",
            "skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py",
            "recursive_outputs_text_only",
            "-f 160",
            "mmproj",
            "--no-resume",
            "image/webp",
            "--skip-download",
            "call_multimodal",
            "call_local",
            "88.94",
            "Tailscale.app",
            "wc_sheet_",
            "lib/process/multimodal.py",
        ):
            self.assertIn(token, text, f"troubleshooting.md missing: {token}")
        self.assertNotIn("../cleaning-auto-transcripts/", text)
        self.assertNotIn("anibon/multimodal.py", text)


if __name__ == "__main__":
    unittest.main()
