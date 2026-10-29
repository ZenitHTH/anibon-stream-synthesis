from __future__ import annotations

import unittest
from pathlib import Path
import sys

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.media.types import MediaCandidate, load_media_catalog


class TestMediaSeparation(unittest.TestCase):
    def test_load_media_catalog_contains_core_stream_songs(self) -> None:
        catalog = load_media_catalog()
        ids = {c.media_id for c in catalog}
        self.assertIn("mairom_phi_mai_rak", ids)
        self.assertIn("ksc_return_happiness", ids)
        self.assertIn("maha_chulalongkorn", ids)
        mairom = next(c for c in catalog if c.media_id == "mairom_phi_mai_rak")
        self.assertIn("พี่ไม่รักน้องเจ้า", mairom.title)
        self.assertTrue(any("ผีไม่ได้ดักเจ้า" in g for g in mairom.garble_patterns))
