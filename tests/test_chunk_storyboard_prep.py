from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))

try:
    from PIL import Image
except ImportError:
    Image = None

from process.chunk_enrichment import ChunkEnrichConfig, enrich_single_chunk, enrich_workspace_chunks
from process.chunk_storyboard_prep import prep_chunk_storyboard

_CHUNK_TXT = "# chunk_01 00:01:00-00:03:30 cutoff=00:03:30\n(00:01:05) สวัสดี\n"


def _make_slides(root: Path) -> Path:
    d = root / "frames" / "slides_clean"
    d.mkdir(parents=True)
    for i in range(1, 12):
        shade = (i * 23) % 255
        Image.new("RGB", (960, 540), (shade, shade, shade)).save(d / f"slide_{i:04d}.jpg")
    return d


@unittest.skipIf(Image is None, "Pillow not installed")
class TestChunkStoryboardPrep(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.slides = _make_slides(self.ws)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_chunk(self) -> Path:
        (self.ws / "chunks").mkdir(exist_ok=True)
        cp = self.ws / "chunks" / "chunk_01.txt"
        cp.write_text(_CHUNK_TXT, encoding="utf-8")
        return cp

    def test_silent_chunk_gets_tiles(self) -> None:
        out = prep_chunk_storyboard({"_idx": 1, "start_sec": 60, "end_sec": 210, "items": []}, self.slides, self.ws)
        self.assertTrue(out)
        self.assertTrue(all(Path(f["path"]).is_file() for f in out))
        self.assertTrue(all(set(f) == {"ts", "path"} for f in out))

    def test_no_slides_is_empty(self) -> None:
        self.assertEqual(prep_chunk_storyboard({"_idx": 0, "start_sec": 0, "end_sec": 150}, None, self.ws), [])

    def test_payload_has_storyboard_frames(self) -> None:
        cfg = ChunkEnrichConfig(workspace=self.ws, video_source=str(self.ws / "v.mp4"), slides_dir=self.slides)
        with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=()):
            payload = enrich_single_chunk(self._write_chunk(), cfg)
        self.assertTrue(payload["storyboard_frames"])
        cached = json.loads((self.ws / "enrichment" / "chunk_01.json").read_text(encoding="utf-8"))
        self.assertEqual(cached["storyboard_frames"], payload["storyboard_frames"])

    def test_workspace_run_resolves_slides_itself(self) -> None:
        self._write_chunk()
        cfg = ChunkEnrichConfig(workspace=self.ws, video_source=str(self.ws / "v.mp4"))
        with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=()):
            enrich_workspace_chunks(cfg)
        cached = json.loads((self.ws / "enrichment" / "chunk_01.json").read_text(encoding="utf-8"))
        self.assertTrue(cached["storyboard_frames"])


if __name__ == "__main__":
    unittest.main()
