import os
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"


def get_skill_files():
    files = []
    for root, dirs, f_list in os.walk(SKILLS_DIR):
        if "SKILL.md" in f_list:
            files.append(Path(root) / "SKILL.md")
    return files


def parse_simple_yaml_frontmatter(text):
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    data = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data


class TestSkillStructure(unittest.TestCase):
    def test_skill_frontmatter_and_structure(self):
        for skill_path in get_skill_files():
            rel_path = skill_path.relative_to(PLUGIN_ROOT)
            dir_name = skill_path.parent.name

            text = skill_path.read_text(encoding="utf-8")

            # 1. Check YAML Frontmatter
            frontmatter = parse_simple_yaml_frontmatter(text)
            self.assertIsNotNone(
                frontmatter,
                f"{rel_path}: Missing or invalid YAML frontmatter delimiters ('---')",
            )
            self.assertEqual(
                frontmatter.get("name"),
                dir_name,
                f"{rel_path}: Frontmatter name '{frontmatter.get('name')}' != folder '{dir_name}'",
            )
            self.assertIn("description", frontmatter, f"{rel_path}: Missing description")
            self.assertGreater(
                len(frontmatter["description"]),
                10,
                f"{rel_path}: Missing or brief description",
            )

            # 2. Check essential headers
            self.assertTrue(
                re.search(r"^#\s+.+", text, re.MULTILINE),
                f"{rel_path}: Missing H1 title",
            )
            self.assertTrue(
                re.search(r"^##\s+(Overview|When to Use)", text, re.MULTILINE),
                f"{rel_path}: Missing Overview/When to Use section",
            )

    def test_orchestrator_subagent_contracts(self):
        orchestrators = [
            "anibon-timestamper",
            "youtube-minutes-synthesis",
            "creating-highlight-video",
        ]
        for orch in orchestrators:
            path = SKILLS_DIR / orch / "SKILL.md"
            t = path.read_text(encoding="utf-8")
            self.assertTrue(
                "Subagent" in t or "invoke_subagent" in t,
                f"{orch}/SKILL.md missing Subagent section",
            )
            self.assertTrue(
                "ask_permission" in t or "Permissions" in t or "permission" in t,
                f"{orch}/SKILL.md missing permission requirement",
            )

    def test_subskill_routing_matrix(self):
        orchestrator_path = SKILLS_DIR / "anibon-timestamper" / "SKILL.md"
        text = orchestrator_path.read_text(encoding="utf-8")
        expected_subskills = [
            "preparing-tools",
            "anibon-world-identity",
            "anibon-local-transcription",
            "whisper-corruption-recovery",
        ]
        for sub in expected_subskills:
            self.assertIn(
                sub,
                text,
                f"anibon-timestamper/SKILL.md missing routing entry for {sub}",
            )

    def test_reference_knowledge_readme_exists(self):
        ref_readme = SKILLS_DIR / "reference" / "README.md"
        self.assertTrue(ref_readme.exists(), "skills/reference/README.md missing")
        text = ref_readme.read_text(encoding="utf-8")
        self.assertTrue(
            "FGO" in text and "Yu-Gi-Oh" in text,
            "Reference README missing database indexes",
        )

    def test_all_skills_in_sitemap(self):
        sitemap = PLUGIN_ROOT / "docs" / "SKILLS.md"
        text = sitemap.read_text(encoding="utf-8")
        skill_dirs = [
            d
            for d in os.listdir(SKILLS_DIR)
            if (SKILLS_DIR / d).is_dir() and not d.startswith(".") and d != "reference"
        ]
        self.assertEqual(
            len(skill_dirs), 23, f"Expected 23 skill directories, found {len(skill_dirs)}"
        )
        for d in skill_dirs:
            self.assertIn(d, text, f"docs/SKILLS.md missing entry for {d}")

    def test_no_vendored_core_anibon_duplicates(self):
        core_mods = {
            "analyzer.py",
            "chunk_io.py",
            "cleaner.py",
            "corruption.py",
            "markdown.py",
            "parsers.py",
            "resources.py",
            "time.py",
            "ytdlp.py",
        }
        dups = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/scripts/anibon/*.py")
            if p.name in core_mods and not p.is_symlink()
        ]
        vision_dups = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/scripts/_vision.py")
            if not p.is_symlink()
        ]
        self.assertEqual(dups, [], f"Duplicate core anibon modules found: {dups}")
        self.assertEqual(vision_dups, [], f"Duplicate _vision.py modules found: {vision_dups}")

    def test_no_duplicate_skill_resources_or_opencode_agents(self):
        skill_jsons = [
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.glob("skills/*/resources/*.json")
            if not p.is_symlink()
        ]
        self.assertEqual(skill_jsons, [], f"Duplicate skill resource JSONs found: {skill_jsons}")
        self.assertFalse((PLUGIN_ROOT / ".opencode" / "agents").exists())
        for required in ("garbled_replacements.json", "default_mappings.json", "knowledge.json", "signal_config.json"):
            self.assertTrue((PLUGIN_ROOT / "resources" / required).is_file(), f"Missing root resource: {required}")

    def test_no_dead_or_divergent_script_copies(self):
        dead_paths = [
            "skills/cleaning-auto-transcripts/scripts/whisper_dispatcher.py",
            "skills/anibon-timestamper-local/scripts/anibon/websearch.py",
            "skills/anibon-local-transcription/scripts/benchmark_check.py",
            "skills/anibon-local-transcription/scripts/detect_hallucinations.py",
            "skills/cleaning-auto-transcripts/scripts/clean_garbled_dictionary.py",
            "scripts/subagent-prompt-builder.py",
            "skills/anibon-timestamper/scripts/test_analyze_555_emoji.py",
        ]
        for rel in dead_paths:
            self.assertFalse((PLUGIN_ROOT / rel).exists(), f"Dead/divergent file still exists: {rel}")

        symlinked = [
            "skills/anibon-timestamper/scripts/process_chunks_local.py",
            "skills/anibon-timestamper/scripts/pack_timestamps.py",
            "skills/anibon-timestamper/scripts/check_sections.py",
            "skills/anibon-timestamper/scripts/whisper_dispatcher.py",
            "skills/anibon-timestamper-local/scripts/fetch_fgo_db.py",
            "skills/anibon-timestamper-local/scripts/fetch_ygo_db.py",
        ]
        for rel in symlinked:
            self.assertTrue((PLUGIN_ROOT / rel).is_symlink(), f"Expected symlink at {rel}")


if __name__ == "__main__":
    unittest.main()
