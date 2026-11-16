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

    def test_plugin_scripts_directory_exists_and_contains_gates(self):
        from process.parity_gates import _PLUGIN_SCRIPTS
        self.assertTrue(_PLUGIN_SCRIPTS.is_dir(), f"_PLUGIN_SCRIPTS does not exist: {_PLUGIN_SCRIPTS}")
        self.assertTrue((_PLUGIN_SCRIPTS / "audit_gaps.py").is_file(), "audit_gaps.py missing in _PLUGIN_SCRIPTS")
        self.assertTrue((_PLUGIN_SCRIPTS / "check_sections.py").is_file(), "check_sections.py missing in _PLUGIN_SCRIPTS")

    def test_audit_gaps_skips_explicit_afk_breaks_and_flags_real_gaps(self):
        import sys
        from process.parity_gates import _PLUGIN_SCRIPTS
        scripts_dir = str(_PLUGIN_SCRIPTS)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import audit_gaps

        ts = [
            (0, "00:00:00 - [Intro] เปิดสตรีม"),
            (3600, "01:00:00 - [Talk] พักเบรกเข้าห้องน้ำสักครู่"),
            (4680, "01:18:00 - [Talk] กลับมาคุยต่อ"),
            (4980, "01:23:00 - [Gameplay] ลุยด่าน"),
        ]
        gaps = audit_gaps.find_gaps(ts, max_gap_sec=600)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][0], 3600)


if __name__ == "__main__":
    unittest.main()
