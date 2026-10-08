from pathlib import Path
from signal_detector import detect_signals_for_chunks

def test_detect_signals_preserves_specific_game(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_00.txt").write_text("ปู่บอทเล่น Chaos Zero Nightmare เล่นเกม สนุกมาก", encoding="utf-8")
    signals = detect_signals_for_chunks(tmp_path)
    assert "chunk_00" in signals
    files = [w["file"] for w in signals["chunk_00"]["weighted_files"]]
    assert any("chaos_zero_nightmare" in f.lower() for f in files)

def test_detect_signals_prioritizes_specific_game_over_stream_type(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    # High frequency of generic stream words ("เล่นเกม"), but explicit mention of specific game ("Chaos Zero Nightmare")
    (chunks_dir / "chunk_00.txt").write_text("เล่นเกม เล่นเกม เล่นเกม เล่นเกม Chaos Zero Nightmare", encoding="utf-8")
    signals = detect_signals_for_chunks(tmp_path)
    assert "chunk_00" in signals
    best = signals["chunk_00"]["best_file"]
    assert best is not None
    assert "chaos_zero_nightmare" in best.lower()

def test_extract_metadata_signals_from_info_json(tmp_path):
    import json
    from signal_detector import extract_metadata_signals
    info_file = tmp_path / "info.json"
    info_file.write_text(json.dumps({
        "title": "สตรีมเล่น Deadlock กับเพื่อนๆ และเปิดตู้ CZN",
        "description": "วันนี้มาลุย Deadlock ยาวๆ และรีวิว Chaos Zero Nightmare",
        "tags": ["Deadlock", "CZN", "Gaming"]
    }, ensure_ascii=False), encoding="utf-8")
    
    signals = extract_metadata_signals(tmp_path)
    assert "deadlock" in signals
    assert "czn" in signals

def test_discover_reference_games_from_markdown_files(tmp_path):
    from signal_detector import discover_reference_games
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "Deadlock.md").write_text("# Deadlock\n", encoding="utf-8")
    (refs / "Sekiro_Shadows_Die_Twice.md").write_text("# Sekiro\n", encoding="utf-8")
    
    discovered = discover_reference_games(refs)
    assert "deadlock" in discovered
    assert "sekiro" in discovered

