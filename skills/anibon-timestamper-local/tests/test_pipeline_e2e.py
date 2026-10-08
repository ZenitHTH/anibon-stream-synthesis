from pathlib import Path

def test_pipeline_generates_entity_glossary(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_00.txt").write_text("ทักทายผู้ชม", encoding="utf-8")
    (tmp_path / "signals.json").write_text("{}", encoding="utf-8")

    from process_chunks_local import run_knowledge_discovery
    glossary_path = run_knowledge_discovery(tmp_path)
    assert glossary_path.exists()

def test_audit_timestamps_replaces_known_variants(tmp_path):
    from process_chunks_local import audit_timestamps_against_glossary
    ts_file = tmp_path / "anibon_timestamps.md"
    ts_file.write_text("00:05:00 - [Game] เล่น นครโตะ กำลังฟาร์ม", encoding="utf-8")
    glossary = {
        "Naucrate": {"en": "Naucrate", "th": "นอคราเต้", "alias_th": "นครโตะ"}
    }
    count = audit_timestamps_against_glossary(ts_file, glossary)
    assert count > 0
    content = ts_file.read_text(encoding="utf-8")
    assert "นอคราเต้" in content
