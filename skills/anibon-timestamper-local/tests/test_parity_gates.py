import unittest
from unittest.mock import patch
from pathlib import Path
from process.parity_gates import ensure_mood_555, run_parity_gates


class TestParityGates(unittest.TestCase):

    @patch("process.parity_gates._run")
    def test_ensure_mood_555_runs_when_missing(self, mock_run):
        mock_run.return_value = 0
        tmp_ws = Path("/tmp/test_parity_ws")
        livechat = tmp_ws / "livechat"
        mood = tmp_ws / "mood_555.json"

        with patch.object(Path, "is_dir", return_value=True), \
             patch.object(Path, "exists", side_effect=lambda: False):
            ensure_mood_555(tmp_ws)
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            self.assertEqual(args[0], "analyze_555.py")

    @patch("process.parity_gates._run")
    def test_ensure_mood_555_skips_when_exists(self, mock_run):
        tmp_ws = Path("/tmp/test_parity_ws")
        with patch.object(Path, "is_dir", return_value=True), \
             patch.object(Path, "exists", return_value=True):
            ensure_mood_555(tmp_ws)
            mock_run.assert_not_called()

    @patch("process.parity_gates._run")
    def test_run_parity_gates_invokes_audit_and_check(self, mock_run):
        mock_run.return_value = 0
        tmp_ws = Path("/tmp/test_parity_ws")
        out_md = tmp_ws / "out.md"

        with patch.object(Path, "exists", return_value=True):
            run_parity_gates(tmp_ws, out_md)
            self.assertEqual(mock_run.call_count, 2)
            called_scripts = [call[0][0] for call in mock_run.call_args_list]
            self.assertIn("audit_gaps.py", called_scripts)
            self.assertIn("check_sections.py", called_scripts)


if __name__ == "__main__":
    unittest.main()
