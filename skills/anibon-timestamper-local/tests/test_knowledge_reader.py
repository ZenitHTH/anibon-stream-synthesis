import pytest
from pathlib import Path
from anibon.knowledge_reader import extract_entity_glossary, save_entity_glossary

def test_extract_entity_glossary_from_markdown(tmp_path):
    ref_dir = tmp_path / "references"
    ref_dir.mkdir()
    md_file = ref_dir / "Chaos_Zero_Nightmare.md"
    md_file.write_text(
        "# Chaos Zero Nightmare\n\n"
        "| ตัวละคร (Agent) | คลาส (Class) | ธาตุ (Attribute) |\n"
        "| :--- | :---: | :---: |\n"
        "| **Maribell (มาริเบล)** | Vanguard | Passion |\n"
        "| **Kayron (ไครอน)** | Psionic | Void |\n",
        encoding="utf-8"
    )
    signals_map = {
        "chunk_00": {
            "best_file": "Chaos_Zero_Nightmare.md",
            "weighted_files": [{"file": "Chaos_Zero_Nightmare.md", "score": 10.0}]
        }
    }
    glossary = extract_entity_glossary(signals_map, ref_dir)
    assert "Maribell" in glossary
    assert glossary["Maribell"]["th"] == "มาริเบล"
    assert glossary["Maribell"]["class"] == "Vanguard"
    assert "Kayron" in glossary
    assert glossary["Kayron"]["th"] == "ไครอน"

def test_save_entity_glossary(tmp_path):
    glossary = {"Maribell": {"th": "มาริเบล"}}
    out_file = save_entity_glossary(glossary, tmp_path)
    assert out_file.exists()
    assert "Maribell" in out_file.read_text(encoding="utf-8")
