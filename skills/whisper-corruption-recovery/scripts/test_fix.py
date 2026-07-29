# test_fix.py  (place in same directory as fix_hallucinations.py)
"""Self-check for BFS D&C engine. Run: python -m pytest test_fix.py -v"""
import json, sys, types, pathlib, unittest
from unittest.mock import patch, MagicMock

# ── bootstrap: import the module without running main() ──────────────────────
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "fix_hallucinations",
    pathlib.Path(__file__).parent / "fix_hallucinations.py",
)
fh = importlib.util.module_from_spec(spec)
sys.modules["fix_hallucinations"] = fh
spec.loader.exec_module(fh)

# ── helpers ───────────────────────────────────────────────────────────────────
def _clean_seg(text, abs_from, abs_to):
    """Fake whisper output segment — clean text."""
    return {"text": text, "offsets": {"from": abs_from, "to": abs_to}}

def _make_whisper_result(segs):
    return segs  # run_whisper_on_slice already returns list of segs

# ── tests ─────────────────────────────────────────────────────────────────────
class TestBfsRecover(unittest.TestCase):

    @patch("fix_hallucinations.ffmpeg_cut")
    @patch("fix_hallucinations.run_whisper_on_slice")
    def test_clean_range_returns_one_item(self, mock_whisper, mock_cut):
        """A range that whisper cleans on first attempt comes back as clean item."""
        mock_cut.return_value = MagicMock(__str__=lambda s: "/tmp/fake.wav",
                                          unlink=lambda missing_ok=True: None)
        mock_whisper.return_value = [_clean_seg(" สวัสดี", 0, 2000)]

        clean, uncertain = fh._bfs_recover(
            [(0, 2000)], pathlib.Path("audio.wav"),
            fh.MODEL_PATH, 0.4, 1.0, workers=1
        )
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["text"], "สวัสดี")
        self.assertEqual(len(uncertain), 0)

    @patch("fix_hallucinations.ffmpeg_cut")
    @patch("fix_hallucinations.run_whisper_on_slice")
    def test_sub_second_hallucination_becomes_uncertain(self, mock_whisper, mock_cut):
        """A < 1s slice that is still hallucinated must produce a [?] item, not be discarded."""
        mock_cut.return_value = MagicMock(__str__=lambda s: "/tmp/fake.wav",
                                          unlink=lambda missing_ok=True: None)
        # Always returns hallucinated text (n-gram repetition)
        mock_whisper.return_value = [_clean_seg(" กกกกกกกกกก", 0, 500)]

        clean, uncertain = fh._bfs_recover(
            [(0, 500)], pathlib.Path("audio.wav"),
            fh.MODEL_PATH, 0.4, 1.0, workers=1
        )
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(uncertain[0]["text"], "[?]")
        self.assertTrue(uncertain[0]["uncertain"])
        self.assertEqual(len(clean), 0)

    @patch("fix_hallucinations.ffmpeg_cut")
    @patch("fix_hallucinations.run_whisper_on_slice")
    def test_hallucinated_range_splits_and_recovers(self, mock_whisper, mock_cut):
        """A hallucinated 4s range splits: left half clean, right half clean → 2 clean items."""
        mock_cut.return_value = MagicMock(__str__=lambda s: "/tmp/fake.wav",
                                          unlink=lambda missing_ok=True: None)
        # Level 0 (4s): hallucinated → splits into two 2s halves
        # Level 1 (2s each): both clean
        call_count = [0]
        def whisper_side_effect(path, model, temperature):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (4s range): hallucinated
                return [_clean_seg(" กกกกกกกก", 0, 4000)]
            else:
                # Subsequent calls: clean
                return [_clean_seg(" ดีครับ", 0, 2000)]
        mock_whisper.side_effect = whisper_side_effect

        clean, uncertain = fh._bfs_recover(
            [(0, 4000)], pathlib.Path("audio.wav"),
            fh.MODEL_PATH, 0.4, 1.0, workers=1
        )
        self.assertGreaterEqual(len(clean), 1)
        self.assertEqual(len(uncertain), 0)

if __name__ == "__main__":
    unittest.main()
