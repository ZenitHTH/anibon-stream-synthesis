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

    def test_skill_md_size_and_line_budget(self) -> None:
        raw = SKILL_MD.read_bytes()
        lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(raw), 12_500, f"SKILL.md too large: {len(raw)} bytes")
        self.assertLessEqual(len(lines), 180, f"SKILL.md too long: {len(lines)} lines")

    def test_frontmatter_sdo_constraints(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        self.assertGreaterEqual(len(parts), 3)
        fm = dict(line.split(":", 1) for line in parts[1].strip().splitlines() if ":" in line)
        desc = fm["description"].strip()
        self.assertEqual(fm["name"].strip(), "anibon-timestamper-local")
        self.assertTrue(desc.startswith("Use when "), f"Description must start with 'Use when ': {desc}")
        self.assertLessEqual(len(desc), 500, f"Description too long: {len(desc)} chars")

    def test_all_reference_links_resolve_and_are_portable(self) -> None:
        managed = [
            SKILL_MD,
            REFS_DIR / "hardware-and-endpoints.md",
            REFS_DIR / "stage5-audit-checklist.md",
            REFS_DIR / "troubleshooting.md",
        ]
        link_re = re.compile(r"\]\((references/[^)#]+)\)")
        for md in managed:
            text = md.read_text(encoding="utf-8")
            self.assertNotIn("file:///", text, f"Non-portable file:/// link in {md.name}")
            self.assertNotIn("/Users/", text, f"Machine-specific /Users/ path in {md.name}")
            for rel in link_re.findall(text):
                self.assertTrue((SKILL_DIR / rel).exists(), f"Broken link {rel} in {md.name}")

    def test_skill_md_core_coverage_and_no_stale_paths(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        for required in (
            "anibon-world-identity",
            "scripts/prepare_video.py",
            "skills/anibon-timestamper-local/scripts/process_chunks_local.py",
            "bash skills/anibon-timestamper-local/scripts/launch_local.sh",
            "skills/anibon-timestamper-local/scripts/control_chunks_local.py",
            "/api/v1/models",
            "*:cloud",
            "scripts/audit_gaps.py",
            "scripts/check_sections.py",
            "NEVER TIME-LOCK",
            "references/hardware-and-endpoints.md",
            "references/stage5-audit-checklist.md",
            "references/troubleshooting.md",
            "references/anibon_emoji_dictionary.md",
            "references/timestamper-handoff.md",
        ):
            self.assertIn(required, text, f"SKILL.md missing required token: {required}")
        all_text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in (
                SKILL_MD,
                REFS_DIR / "hardware-and-endpoints.md",
                REFS_DIR / "stage5-audit-checklist.md",
                REFS_DIR / "troubleshooting.md",
            )
        )
        for stale in (
            "lib/process/lmstudio.py",
            "lib/process/state.py",
            "lib/process/timestamps.py",
            "lib/process/knowledge_reader.py",
            "lib/anibon/signal_detector.py",
            "anibon/multimodal.py",
            "anibon/config.py",
            "../cleaning-auto-transcripts/",
        ):
            self.assertNotIn(stale, all_text, f"Stale path still present: {stale}")

    def test_reviewer_critical_and_important_guards(self) -> None:
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        self.assertNotIn('"~/', skill_text, "Quoted tilde path disables shell ~ expansion")
        self.assertNotIn("Post-Pass 2", skill_text)
        self.assertNotIn("automatically after assembly", skill_text)
        self.assertIn("before Pass 2 summarization", skill_text)
        checklist = (REFS_DIR / "stage5-audit-checklist.md").read_text(encoding="utf-8")
        for token in ("prune_essential", "โชว์ฟิกเกอร์", "Lostbelt"):
            self.assertIn(token, checklist, f"stage5-audit-checklist.md missing: {token}")


if __name__ == "__main__":
    unittest.main()
