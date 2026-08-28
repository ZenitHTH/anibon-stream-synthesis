import os
import re
import pytest

PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(PLUGIN_ROOT, "skills")

def get_skill_files():
    files = []
    for root, dirs, f_list in os.walk(SKILLS_DIR):
        if "SKILL.md" in f_list:
            files.append(os.path.join(root, "SKILL.md"))
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

@pytest.mark.parametrize("skill_path", get_skill_files())
def test_skill_frontmatter_and_structure(skill_path):
    rel_path = os.path.relpath(skill_path, PLUGIN_ROOT)
    dir_name = os.path.basename(os.path.dirname(skill_path))
    
    with open(skill_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    # 1. Check YAML Frontmatter
    frontmatter = parse_simple_yaml_frontmatter(text)
    assert frontmatter is not None, f"{rel_path}: Missing or invalid YAML frontmatter delimiters ('---')"
    assert frontmatter.get("name") == dir_name, f"{rel_path}: Frontmatter name '{frontmatter.get('name')}' != folder '{dir_name}'"
    assert "description" in frontmatter and len(frontmatter["description"]) > 10, f"{rel_path}: Missing or brief description"

    # 2. Check essential headers
    assert re.search(r"^#\s+.+", text, re.MULTILINE), f"{rel_path}: Missing H1 title"
    assert re.search(r"^##\s+(Overview|When to Use)", text, re.MULTILINE), f"{rel_path}: Missing Overview/When to Use section"


def test_orchestrator_subagent_contracts():
    orchestrators = ['anibon-timestamper', 'youtube-minutes-synthesis', 'creating-highlight-video']
    for orch in orchestrators:
        path = os.path.join(SKILLS_DIR, orch, 'SKILL.md')
        with open(path, 'r', encoding='utf-8') as f:
            t = f.read()
        assert 'Subagent' in t or 'invoke_subagent' in t, f'{orch}/SKILL.md missing Subagent section'
        assert 'ask_permission' in t or 'Permissions' in t or 'permission' in t, f'{orch}/SKILL.md missing permission requirement'


def test_subskill_routing_matrix():
    orchestrator_path = os.path.join(SKILLS_DIR, 'anibon-timestamper', 'SKILL.md')
    with open(orchestrator_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    expected_subskills = [
        'preparing-tools',
        'anibon-world-identity',
        'anibon-local-transcription',
        'whisper-corruption-recovery'
    ]
    for sub in expected_subskills:
        assert sub in text, f'anibon-timestamper/SKILL.md missing routing entry for {sub}'


def test_reference_knowledge_readme_exists():
    ref_readme = os.path.join(SKILLS_DIR, 'reference', 'README.md')
    assert os.path.exists(ref_readme), 'skills/reference/README.md missing'
    with open(ref_readme, 'r', encoding='utf-8') as f:
        text = f.read()
    assert 'FGO' in text and 'Yu-Gi-Oh' in text, 'Reference README missing database indexes'


def test_all_20_skills_in_sitemap():
    sitemap = os.path.join(PLUGIN_ROOT, 'docs', 'SKILLS.md')
    with open(sitemap, 'r', encoding='utf-8') as f:
        text = f.read()
    
    skill_dirs = [d for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d)) and d != 'reference']
    assert len(skill_dirs) == 20, f'Expected 20 skill directories, found {len(skill_dirs)}'
    for d in skill_dirs:
        assert d in text, f'docs/SKILLS.md missing entry for {d}'
