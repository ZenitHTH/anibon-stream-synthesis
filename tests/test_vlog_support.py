import os
import json
import pytest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
TIMESTAMPER_DIR = SKILLS_DIR / "anibon-timestamper"
WORLD_ID_DIR = SKILLS_DIR / "anibon-world-identity"
ACTIVITY_DIR = SKILLS_DIR / "anibon-stream-activity"

# Import validate_tags functions
import sys
sys.path.insert(0, str(TIMESTAMPER_DIR / "scripts"))
from validate_tags import suggest_retag, parse_line
from validate_part_coherence import check_tag_diversity


def test_tag_macros_vlog_entries():
    """Verify tag_macros.json contains all expected VLOG tags."""
    for path in [
        PLUGIN_ROOT / "resources" / "tag_macros.json",
        TIMESTAMPER_DIR / "resources" / "tag_macros.json",
    ]:
        data = json.loads(path.read_text(encoding="utf-8"))
        mapping = data.get("mapping", {})
        expected_vlog_tags = [
            "Vlog", "Tour", "Booth", "Food", "Stage",
            "Cosplay", "Interview", "FanMeet", "Merch",
            "Shopping", "Work", "IRL", "Showcase", "Activity"
        ]
        for tag in expected_vlog_tags:
            assert tag in mapping, f"{path.name} missing tag {tag}"
            assert mapping[tag] == "VLOG", f"{path.name} tag {tag} should map to VLOG"


def test_validate_tags_vlog_keywords():
    """Verify validate_tags correctly identifies VLOG keyword patterns."""
    cases = [
        ("ชิมทาโกยากิร้อนๆ ในงานนิปปอนฮาคุ", "[Talk]", "[Food]"),
        ("สั่งราเมนชามพิเศษและมัตฉะเย็น", "[Talk]", "[Food]"),
        ("ทักทายเลเยอร์คอสเพลย์ตัวละคร FGO", "[Talk]", "[Cosplay]"),
        ("ชมการแสดง Cover Dance บนเวทีใหญ่ Main Stage", "[Talk]", "[Stage]"),
        ("ถ่ายรูปกับแฟนคลับและแฟนรายการที่เข้ามาทัก", "[Talk]", "[FanMeet]"),
        ("สัมภาษณ์ทีมงานบูธเรียนต่อประเทศญี่ปุ่น", "[Talk]", "[Interview]"),
        ("เดินชมบูธ Kadokawa และดูฟิกเกอร์ Good Smile", "[Talk]", "[Booth]"),
        ("เดินเที่ยวชมบรรยากาศงาน NIPPON HAKU 2026", "[Talk]", "[Tour]"),
        ("สาธิตงานเชื่อมท่อเหล็กหน้างานก่อสร้าง", "[Talk]", "[Work]"),
        ("ทัวร์งานหนังสือสัปดาห์หนังสือแห่งชาติ ครั้งที่ 54", "[Talk]", "[Tour]"),
        ("แวะบูธ Phoenix Next เลือกซื้อนิยายและมังงะมาดอง", "[Talk]", "[Booth]"),
        ("เดินดูหนังสือในบูธ First Page Pro", "[Talk]", "[Booth]"),
    ]
    for desc, current_tag, expected_tag in cases:
        new_tag, _ = suggest_retag(desc, current_tag)
        assert new_tag == expected_tag, f"Expected {expected_tag} for '{desc}', got {new_tag}"


def test_validate_tags_vlog_false_positives():
    """Verify false positive protection for VLOG keywords in non-VLOG contexts."""
    # Combat "กินยา" / "กินดาเมจ" should not trigger [Food]
    new_tag, _ = suggest_retag("สู้บอสตัวนี้กินดาเมจหนักมาก", "[Gameplay]")
    assert new_tag != "[Food]"

    # Metaphorical "เวทีการเมือง" should not trigger [Stage]
    new_tag, _ = suggest_retag("วิเคราะห์ความเคลื่อนไหวบนเวทีการเมือง", "[News]")
    assert new_tag != "[Stage]"


def test_validate_part_coherence_vlog_plus_talk():
    """Verify validate_part_coherence allows TALK + VLOG macro combination in one part."""
    part = {
        "timestamps": [
            {"tag": "[Tour]", "desc": "เดินเข้างานนิปปอนฮาคุ"},
            {"tag": "[Booth]", "desc": "แวะดูบูธ Good Smile"},
            {"tag": "[Food]", "desc": "ชิมทาโกยากิ"},
            {"tag": "[Talk]", "desc": "เม้าท์มอยเรื่องอนิเมะขณะเดินงาน"},
        ]
    }
    flags = check_tag_diversity(part)
    assert flags == [], f"Expected no flags for TALK + VLOG, got: {flags}"


def test_knowledge_vlog_mappings():
    """Verify knowledge.json correctly routes vlog and event keywords."""
    path = TIMESTAMPER_DIR / "resources" / "knowledge.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", {})

    assert "vlog" in entries
    assert entries["vlog"]["file"] == "references/stream/vlog-stream.md"

    assert "nippon haku" in entries
    assert entries["nippon haku"]["file"] == "../anibon-world-identity/references/Japan_Event_Convention.md"

    assert "japan expo" in entries
    assert entries["japan expo"]["file"] == "../anibon-world-identity/references/Japan_Event_Convention.md"

    assert "งานญี่ปุ่น" in entries
    assert entries["งานญี่ปุ่น"]["file"] == "../anibon-world-identity/references/Japan_Event_Convention.md"

    assert "สัปดาห์หนังสือแห่งชาติ" in entries
    assert entries["สัปดาห์หนังสือแห่งชาติ"]["file"] == "../anibon-world-identity/references/Thai_Book_Fair_Convention.md"

    assert "มหกรรมหนังสือแห่งชาติ" in entries
    assert entries["มหกรรมหนังสือแห่งชาติ"]["file"] == "../anibon-world-identity/references/Thai_Book_Fair_Convention.md"

    assert "ซื้อมาดอง" in entries
    assert entries["ซื้อมาดอง"]["file"] == "references/stream/vlog-stream.md"


def test_vlog_reference_files_exist():
    """Verify new reference files exist and have valid structure."""
    vlog_stream = TIMESTAMPER_DIR / "references" / "stream" / "vlog-stream.md"
    assert vlog_stream.exists()
    vlog_text = vlog_stream.read_text(encoding="utf-8")
    assert "name: anibon-vlog-stream" in vlog_text
    assert "NIPPON HAKU" in vlog_text
    assert "Book Fair" in vlog_text

    japan_event = WORLD_ID_DIR / "references" / "Japan_Event_Convention.md"
    assert japan_event.exists()
    event_text = japan_event.read_text(encoding="utf-8")
    assert "name: Japan_Event_Convention" in event_text
    assert "Takoyaki" in event_text

    book_fair = WORLD_ID_DIR / "references" / "Thai_Book_Fair_Convention.md"
    assert book_fair.exists()
    bf_text = book_fair.read_text(encoding="utf-8")
    assert "name: Thai_Book_Fair_Convention" in bf_text
    assert "Phoenix Next" in bf_text
    assert "Tsundoku" in bf_text
