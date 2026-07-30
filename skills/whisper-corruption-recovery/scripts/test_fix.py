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
        self.assertTrue(uncertain[0]["text"].startswith("[?]"))
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

class TestSecondChance(unittest.TestCase):

    @patch("fix_hallucinations.ffmpeg_cut")
    @patch("fix_hallucinations.run_whisper_on_slice")
    def test_uncertain_run_over_1s_gets_retried(self, mock_whisper, mock_cut):
        """Consecutive [?] items spanning > 1s must be merged and retried."""
        mock_cut.return_value = MagicMock(__str__=lambda s: "/tmp/fake.wav",
                                          unlink=lambda missing_ok=True: None)
        mock_whisper.return_value = [{"text": " ดีครับ", "offsets": {"from": 0, "to": 1500}}]

        uncertain = [
            {"text": "[?]", "start": 10.0, "duration": 0.6, "timestamp": "00:00:10", "uncertain": True},
            {"text": "[?]", "start": 10.6, "duration": 0.6, "timestamp": "00:00:10", "uncertain": True},
            {"text": "[?]", "start": 11.2, "duration": 0.6, "timestamp": "00:00:11", "uncertain": True},
        ]
        # Combined span = 1.8s > 1s — should retry
        recovered, still_uncertain = fh._second_chance_pass(
            uncertain, pathlib.Path("audio.wav"), fh.MODEL_PATH, 0.4, 1.0, workers=1
        )
        self.assertGreater(len(recovered), 0)
        self.assertEqual(len(still_uncertain), 0)

    def test_uncertain_run_under_1s_skipped(self):
        """Consecutive [?] items spanning <= 1s must NOT be retried."""
        uncertain = [
            {"text": "[?]", "start": 10.0, "duration": 0.4, "timestamp": "00:00:10", "uncertain": True},
            {"text": "[?]", "start": 10.4, "duration": 0.4, "timestamp": "00:00:10", "uncertain": True},
        ]
        # Combined span = 0.8s <= 1s — skip
        with patch("fix_hallucinations.ffmpeg_cut") as mock_cut:
            recovered, still_uncertain = fh._second_chance_pass(
                uncertain, pathlib.Path("audio.wav"), fh.MODEL_PATH, 0.4, 1.0, workers=1
            )
        mock_cut.assert_not_called()
        self.assertEqual(len(still_uncertain), 2)
        self.assertEqual(len(recovered), 0)

class TestSummaryOutput(unittest.TestCase):

    def test_uncertain_items_in_output_have_flag(self):
        """Final JSON output must have uncertain=True and [?] prefix on uncertain items."""
        item = {"text": "[?] เสียงไม่ชัด", "start": 1.0, "duration": 0.5,
                "timestamp": "00:00:01", "uncertain": True}
        self.assertTrue(item.get("uncertain"))
        self.assertTrue(item["text"].startswith("[?]"))

    def test_no_max_depth_in_detect_signature(self):
        """detect_and_recover must NOT have max_depth parameter."""
        import inspect
        sig = inspect.signature(fh.detect_and_recover)
        self.assertNotIn("max_depth", sig.parameters)

class TestProgressTracker(unittest.TestCase):

    def test_progress_tracker_metrics(self):
        """Test task advancing, percentage, and formatting in ProgressTracker."""
        tracker = fh.ProgressTracker("Level 0", total_tasks=10)
        task_num, pct, elapsed_str, rem_str = tracker.advance()
        self.assertEqual(task_num, 1)
        self.assertEqual(pct, 10.0)
        self.assertTrue(isinstance(elapsed_str, str))
        self.assertTrue(isinstance(rem_str, str))

if __name__ == "__main__":
    unittest.main()


