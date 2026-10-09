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

def test_enrich_with_fgo_db(tmp_path):
    import sqlite3
    from anibon.knowledge_reader import enrich_with_sqlite_databases

    db_path = tmp_path / "atlas_fgo.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE basic_servant (name TEXT, className TEXT, rarity INTEGER)")
    conn.execute("INSERT INTO basic_servant VALUES ('Ashiya Douman', 'alterEgo', 5)")
    conn.commit()
    conn.close()

    signals_map = {
        "chunk_01": {
            "best_file": "fgo-knowledge.md",
            "matched_keywords": {"fgo": {"count": 2}}
        }
    }
    glossary = {}
    enriched = enrich_with_sqlite_databases(glossary, signals_map, fgo_db=db_path)
    assert "Ashiya Douman" in enriched
    assert enriched["Ashiya Douman"]["class"] == "alterEgo"

def test_enrich_with_pokemon_db(tmp_path):
    import sqlite3
    from anibon.knowledge_reader import enrich_with_sqlite_databases

    db_path = tmp_path / "pokemon.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE pokemon (id INTEGER, name_en TEXT, name_ja TEXT, name_th_official TEXT, name_th_english_sound TEXT)")
    conn.execute("INSERT INTO pokemon VALUES (25, 'Pikachu', 'ピカチュウ', 'พิคาชู', 'ปิกาจู')")
    conn.commit()
    conn.close()

    signals_map = {
        "chunk_01": {
            "best_file": "Pokemon_PvP.md",
            "weighted_files": [{"file": "Pokemon_PvP.md", "score": 8.0}]
        }
    }
    glossary = {}
    enriched = enrich_with_sqlite_databases(glossary, signals_map, pokemon_db=db_path)
    assert "Pikachu" in enriched
    assert enriched["Pikachu"]["th"] == "พิคาชู"


def test_extract_entity_glossary_with_version_and_canto_columns(tmp_path):
    ref_dir = tmp_path / "references"
    ref_dir.mkdir()
    md_file = ref_dir / "Honkai_Star_Rail.md"
    md_file.write_text(
        "# Honkai: Star Rail\n\n"
        "| เวอร์ชัน | ตัวละคร | พาธ (Path) | ธาตุ |\n"
        "| :---: | :--- | :---: | :---: |\n"
        "| **4.3** | **Phainon (ไฟนอน)** | ล่าสังหาร (The Hunt) | ไฟ |\n"
        "| **Canto X** | **Meursault** | Vanguard | Ice |\n",
        encoding="utf-8"
    )
    signals_map = {
        "chunk_00": {
            "best_file": "Honkai_Star_Rail.md",
            "weighted_files": [{"file": "Honkai_Star_Rail.md", "score": 10.0}]
        }
    }
    glossary = extract_entity_glossary(signals_map, ref_dir)
    assert "4.3" not in glossary
    assert "Canto X" not in glossary
    assert "Phainon" in glossary
    assert glossary["Phainon"]["th"] == "ไฟนอน"
    assert glossary["Phainon"]["role"] == "ล่าสังหาร (The Hunt)"
    assert "Meursault" in glossary


def test_extract_entity_glossary_resolves_stream_references(tmp_path):
    # Base ref_dir without gaming-stream.md
    ref_dir = tmp_path / "anibon-world-identity" / "references"
    ref_dir.mkdir(parents=True)
    
    # Stream references directory in sibling timestamper
    stream_dir = tmp_path / "anibon-timestamper-local" / "references" / "stream"
    stream_dir.mkdir(parents=True)
    (stream_dir / "gaming-stream.md").write_text(
        "# Gaming Stream\n\n"
        "| คำศัพท์ | ความหมาย |\n"
        "| :--- | :--- |\n"
        "| **Joy-Con** | จอยสติ๊ก Switch |\n",
        encoding="utf-8"
    )

    signals_map = {
        "chunk_01": {
            "best_file": "references/stream/gaming-stream.md",
            "weighted_files": [{"file": "references/stream/gaming-stream.md", "score": 10.0}]
        }
    }
    glossary = extract_entity_glossary(signals_map, ref_dir, extra_ref_dirs=[stream_dir])
    assert "Joy-Con" in glossary

