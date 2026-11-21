from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))

from process.runners.dynamic_chunk import (
    _balance_dynamic_chunk_frames,
    _load_cached_storyboard,
)


class TestPass1FullFrames(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        (self.ws / "enrichment").mkdir()
        (self.ws / "frames" / "chunk_tiles").mkdir(parents=True)
        (self.ws / "frames" / "webcam_chunk").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cached_webcam_does_not_trim_storyboard(self) -> None:
        wc_file = self.ws / "frames" / "webcam_chunk" / "wc_sheet_00_0.jpg"
        wc_file.write_bytes(b"fake-jpg-bytes")
        enr = {
            "audio_cues": [{"sec": 30, "event_type": "loud_peak", "score": 3.5, "note": "loud_peak"}],
            "webcam_frames": [str(wc_file)],
            "song": None,
            "recovered_items": [],
        }
        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps(enr), encoding="utf-8")

        sb = [(f"00:00:{i:02d}", wc_file, "b64", "STORYBOARD SCREEN") for i in range(16)]
        chunk = {"_idx": 0, "start_sec": 0, "end_sec": 150, "items": []}
        out_sb, wc, tier = _balance_dynamic_chunk_frames(self.ws, chunk, sb, None, None)
        self.assertEqual(len(out_sb), 16)
        self.assertEqual(len(wc), 1)
        self.assertEqual(tier, "cached-enrichment")

    def test_load_cached_storyboard_reads_prepped_tiles(self) -> None:
        t1 = self.ws / "frames" / "chunk_tiles" / "tile_000010.jpg"
        t2 = self.ws / "frames" / "chunk_tiles" / "tile_000040.jpg"
        t1.write_bytes(b"tile1")
        t2.write_bytes(b"tile2")
        enr = {
            "storyboard_frames": [
                {"ts": "00:00:10", "path": str(t1)},
                {"ts": "00:00:40", "path": str(t2)},
            ],
        }
        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps(enr), encoding="utf-8")
        out = _load_cached_storyboard(self.ws, {"_idx": 0})
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "00:00:10")
        self.assertEqual(out[0][3], "STORYBOARD SCREEN")

    def test_stale_cache_without_storyboard_frames_returns_empty(self) -> None:
        (self.ws / "enrichment" / "chunk_00.json").write_text(json.dumps({"audio_cues": []}), encoding="utf-8")
        out = _load_cached_storyboard(self.ws, {"_idx": 0})
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
