import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from anibon.cleaner import clean_text, clean_text_with_count, load_replacements
from anibon.resources import resource_path


class TestCleanerV2(unittest.TestCase):
    def test_v2_schema_and_word_boundary_patterns(self):
        compiled = load_replacements(resource_path("garbled_replacements.json"))
        self.assertGreater(len(compiled), 2000)
        cleaned, count = clean_text_with_count("เล่น 2SKO กับปู่บอท", compiled)
        self.assertIn("2XKO", cleaned)
        self.assertIn("ปู่โบ๊ต", cleaned)
        self.assertGreaterEqual(count, 2)

    def test_xml_cleaning_does_not_double_escape_ampersand(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = Path(tmp) / "chunk_01.xml"
            xml_path.write_text(
                '<transcript start_sec="0"><item timestamp="00:00:01">Tom &amp; Jerry เล่น 2SKO</item></transcript>',
                encoding="utf-8",
            )
            tree = ET.parse(xml_path)
            for item in tree.getroot().iter("item"):
                item.text = clean_text((item.text or "").strip())
            tree.write(xml_path, encoding="utf-8", xml_declaration=False)
            raw_out = xml_path.read_text(encoding="utf-8")
            self.assertIn("Tom &amp; Jerry เล่น 2XKO", raw_out)
            self.assertNotIn("&amp;amp;", raw_out)


if __name__ == "__main__":
    unittest.main()
