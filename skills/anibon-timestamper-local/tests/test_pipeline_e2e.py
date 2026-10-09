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

def test_sanitize_and_audit_timestamps_cleans_hallucinations_and_drift():
    from process_chunks_local import sanitize_and_audit_timestamps
    raw_md = (
        "═════════════════════════════════════════════════════════\n"
        " ส่วนที่ 1: เม้าท์มอยกับผู้ชม (⏱ เริ่ม: 00:00:00)\n"
        "═════════════════════════════════════════════════════════\n"
        "00:00:00 - [Talk] ปู่บอทกล่าวทักทายผู้ชม\n"
        "00:05:00 - [Talk] เม้าท์มอยเรื่องซีรีส์ Archen และตัวละคร Victor\n"
        "00:10:00 - [Gameplay] เล่นตัวละคร Uhlom สายต่อย\n"
    )
    glossary = {"Abrams": {"en": "Abrams", "th": "เอแบรห์มส์"}}
    garbled = [
        {"correct": "Arcane", "patterns": ["Archen"]},
        {"correct": "Viktor", "patterns": ["Victor"]},
    ]
    cleaned_md, stats = sanitize_and_audit_timestamps(raw_md, glossary=glossary, signals={}, garbled=garbled)
    assert "ปู่โบ๊ตกล่าวทักทายผู้ชม" in cleaned_md
    assert "ซีรีส์ Arcane และตัวละคร Viktor" in cleaned_md
    assert "Uhlom" in stats["suspected_hallucinations"]
    assert stats["corrections_applied"] > 0


def test_full_pipeline_simulation_with_stream_and_game_knowledge(tmp_path):
    """Simulate end-to-end knowledge loading, signal detection, and prompt injection."""
    from signal_detector import detect_signals_for_chunks
    from process_chunks_local import run_knowledge_discovery
    from anibon.prompts import load_world_identity_context, build_recursive_prompt
    import json

    # 1. Setup mock chunks in workspace
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_00.txt").write_text("(00:00:10) เล่นเกม Zelda ด้วย Joy-Con สนุกมาก", encoding="utf-8")
    (chunks_dir / "chunk_01.txt").write_text("(00:05:00) วิเคราะห์ตัวละคร Limbus Company และ Meursault Canto X", encoding="utf-8")

    # 2. Run signal detection
    signals_map = detect_signals_for_chunks(tmp_path)
    assert "chunk_00" in signals_map
    assert "chunk_01" in signals_map

    # 3. Run knowledge discovery
    glossary_path = run_knowledge_discovery(tmp_path, signals_map)
    assert glossary_path.exists()
    glossary = json.loads(glossary_path.read_text(encoding="utf-8"))

    # 4. Verify stream-type knowledge resolved in prompt for chunk_00
    sig_00 = signals_map["chunk_00"]
    ctx_00 = load_world_identity_context(sig_00)
    assert len(ctx_00) > 0

    # 5. Verify game-specific knowledge resolved in prompt for chunk_01
    sig_01 = signals_map["chunk_01"]
    ctx_01 = load_world_identity_context(sig_01)
    assert len(ctx_01) > 0
    assert "Limbus_Company" in ctx_01

    # 6. Verify prompt builds with injected knowledge context
    prompt = build_recursive_prompt(
        chunk={"_idx": 0, "items": [{"timestamp": "00:00:10", "start": 10.0, "text": "เล่นเกม Zelda"}]},
        current_topic="เล่นเกม",
        rolling_summary="สรุป",
        lang="th",
        world_identity_ref=ctx_00,
        glossary=glossary,
    )
    assert "WORLD IDENTITY REFERENCE" in prompt

