from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))
if str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts"))

import process_chunks_local as pcl
from process.assembly import _prune_and_verify_timestamps
from process.runners.common import _init_webcam_source


class TestPostReactionOptIn(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pass2_skips_reaction_verify_unless_post_reaction_verify_set(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws), "--reaction-verify"])
        self.assertFalse(getattr(args, "post_reaction_verify", False))
        stamps = ["00:01:00 - [Reaction] อึ้งกับฉากเปิดตัวบอสใหม่"]
        with patch("process.assembly.apply_reaction_verify") as m_rx, \
             patch("process.assembly.apply_vision_verify", side_effect=lambda s, *a: s):
            _prune_and_verify_timestamps(stamps, self.ws, "http://127.0.0.1:1234", "m", 0.1, args, True)
        m_rx.assert_not_called()

    def test_pass2_runs_reaction_verify_when_post_reaction_verify_set(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws), "--post-reaction-verify"])
        self.assertTrue(args.post_reaction_verify)
        stamps = ["00:01:00 - [Reaction] อึ้งกับฉากเปิดตัวบอสใหม่"]
        with patch("process.assembly.apply_reaction_verify", return_value=stamps) as m_rx, \
             patch("process.assembly.apply_vision_verify", side_effect=lambda s, *a: s):
            _prune_and_verify_timestamps(stamps, self.ws, "http://127.0.0.1:1234", "m", 0.1, args, True)
        m_rx.assert_called_once()

    def test_init_webcam_source_resolves_when_video_file_present(self) -> None:
        v = self.ws / "video_360p.mp4"
        v.write_bytes(b"fake")
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws), "--video-file", str(v)])
        src = _init_webcam_source(self.ws, args)
        self.assertEqual(Path(str(src)), v)


if __name__ == "__main__":
    unittest.main()
