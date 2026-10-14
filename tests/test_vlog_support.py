import json
import os
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
TIMESTAMPER_DIR = SKILLS_DIR / "anibon-timestamper"
WORLD_ID_DIR = SKILLS_DIR / "anibon-world-identity"
ACTIVITY_DIR = SKILLS_DIR / "anibon-stream-activity"

# Import validate_tags functions
sys.path.insert(0, str(TIMESTAMPER_DIR / "scripts"))
from validate_tags import parse_line, suggest_retag
from validate_part_coherence import check_tag_diversity


class TestVlogSupport(unittest.TestCase):
    def test_tag_macros_vlog_entries(self):
        """Verify tag_macros.json contains all expected VLOG tags."""
        path = PLUGIN_ROOT / "resources" / "tag_macros.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mapping = data.get("mapping", {})
        expected_vlog_tags = [
            "Vlog", "Tour", "Booth", "Food", "Stage",
            "Cosplay", "Interview", "FanMeet", "Merch",
            "Shopping", "Work", "IRL", "Showcase", "Activity"
        ]
        for tag in expected_vlog_tags:
            self.assertIn(tag, mapping, f"{path.name} missing tag {tag}")
            self.assertEqual(mapping[tag], "VLOG", f"{path.name} tag {tag} should map to VLOG")

    def test_validate_tags_vlog_keywords(self):
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
            self.assertEqual(new_tag, expected_tag, f"Expected {expected_tag} for '{desc}', got {new_tag}")

    def test_validate_tags_vlog_false_positives(self):
        """Verify false positive protection for VLOG keywords in non-VLOG contexts."""
        # Combat "กินยา" / "กินดาเมจ" should not trigger [Food]
        new_tag, _ = suggest_retag("สู้บอสตัวนี้กินดาเมจหนักมาก", "[Gameplay]")
        self.assertNotEqual(new_tag, "[Food]")

        # Metaphorical "เวทีการเมือง" should not trigger [Stage]
        new_tag, _ = suggest_retag("วิเคราะห์ความเคลื่อนไหวบนเวทีการเมือง", "[News]")
        self.assertNotEqual(new_tag, "[Stage]")

    def test_validate_part_coherence_vlog_plus_talk(self):
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
        self.assertEqual(flags, [], f"Expected no flags for TALK + VLOG, got: {flags}")

    def test_knowledge_vlog_mappings(self):
        """Verify knowledge.json correctly routes vlog and event keywords."""
        path = PLUGIN_ROOT / "resources" / "knowledge.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", {})

        self.assertIn("vlog", entries)
        self.assertEqual(entries["vlog"]["file"], "references/stream/vlog-stream.md")

        self.assertIn("nippon haku", entries)
        self.assertEqual(entries["nippon haku"]["file"], "../anibon-world-identity/references/Japan_Event_Convention.md")

        self.assertIn("japan expo", entries)
        self.assertEqual(entries["japan expo"]["file"], "../anibon-world-identity/references/Japan_Event_Convention.md")

        self.assertIn("งานญี่ปุ่น", entries)
        self.assertEqual(entries["งานญี่ปุ่น"]["file"], "../anibon-world-identity/references/Japan_Event_Convention.md")

        self.assertIn("สัปดาห์หนังสือแห่งชาติ", entries)
        self.assertEqual(entries["สัปดาห์หนังสือแห่งชาติ"]["file"], "../anibon-world-identity/references/Thai_Book_Fair_Convention.md")

        self.assertIn("มหกรรมหนังสือแห่งชาติ", entries)
        self.assertEqual(entries["มหกรรมหนังสือแห่งชาติ"]["file"], "../anibon-world-identity/references/Thai_Book_Fair_Convention.md")

        self.assertIn("ซื้อมาดอง", entries)
        self.assertEqual(entries["ซื้อมาดอง"]["file"], "references/stream/vlog-stream.md")

    def test_vlog_reference_files_exist(self):
        """Verify new reference files exist and have valid structure."""
        vlog_stream = TIMESTAMPER_DIR / "references" / "stream" / "vlog-stream.md"
        self.assertTrue(vlog_stream.exists())
        vlog_text = vlog_stream.read_text(encoding="utf-8")
        self.assertIn("name: anibon-vlog-stream", vlog_text)
        self.assertIn("NIPPON HAKU", vlog_text)
        self.assertIn("Book Fair", vlog_text)

        japan_event = WORLD_ID_DIR / "references" / "Japan_Event_Convention.md"
        self.assertTrue(japan_event.exists())
        event_text = japan_event.read_text(encoding="utf-8")
        self.assertIn("name: Japan_Event_Convention", event_text)
        self.assertIn("Takoyaki", event_text)

        book_fair = WORLD_ID_DIR / "references" / "Thai_Book_Fair_Convention.md"
        self.assertTrue(book_fair.exists())
        bf_text = book_fair.read_text(encoding="utf-8")
        self.assertIn("name: Thai_Book_Fair_Convention", bf_text)
        self.assertIn("Phoenix Next", bf_text)
        self.assertIn("Tsundoku", bf_text)


if __name__ == "__main__":
    unittest.main()
