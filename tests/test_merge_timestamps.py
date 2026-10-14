import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/anibon-timestamper/scripts')))
from merge_timestamps import merge_logic


class TestMergeTimestamps(unittest.TestCase):
    def test_merge_logic(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f1, \
             tempfile.NamedTemporaryFile("w", delete=False) as f2:
            f1.write("00:05:00 - [Talk] Hello\n00:01:00 No Tag\n")
            f2.write("00:01:00 No Tag\n00:10:00 - [News] Update\n")

        try:
            results = merge_logic([f1.name, f2.name])
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0], "00:01:00 - [Talk] No Tag")
            self.assertEqual(results[1], "00:05:00 - [Talk] Hello")
            self.assertEqual(results[2], "00:10:00 - [News] Update")
        finally:
            os.remove(f1.name)
            os.remove(f2.name)


if __name__ == "__main__":
    unittest.main()
