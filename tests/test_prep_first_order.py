from __future__ import annotations

import os
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


class TestPrepFirstOrder(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        (self.ws / "chunks").mkdir()
        (self.ws / "chunks" / "chunk_00.txt").write_text(
            "# chunk_00 00:00:00-00:02:30 cutoff=00:02:30\n(00:00:05) สวัสดี\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_enrich_is_default_true_and_no_enrich_disables_it(self) -> None:
        ap = pcl.build_argument_parser()
        default_args = ap.parse_args([str(self.ws)])
        self.assertTrue(default_args.enrich)
        disabled_args = ap.parse_args([str(self.ws), "--no-enrich"])
        self.assertFalse(disabled_args.enrich)

    def test_prep_runs_before_signals_and_pass1(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws), "--no-knowledge-reader"])
        ctx = pcl._PipelineContext(args, self.ws, "test-model", [self.ws / "chunks" / "chunk_00.txt"], None)
        calls: list[str] = []
        with patch.object(pcl, "_run_prep_stage", side_effect=lambda *a: calls.append("prep")), \
             patch.object(pcl, "_load_or_detect_signals", side_effect=lambda *a: calls.append("signals") or {}), \
             patch.object(pcl, "_dispatch_pipeline_mode", side_effect=lambda *a: calls.append("pass1")):
            pcl._run_active_pipeline(ctx)
        self.assertEqual(calls, ["prep", "signals", "pass1"])

    def test_no_enrich_skips_prep_stage(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws), "--no-enrich"])
        with patch.object(pcl, "enrich_workspace_chunks") as m_enrich:
            pcl._run_prep_stage(self.ws, args)
        m_enrich.assert_not_called()

    def test_no_media_warns_and_does_not_crash(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws)])
        with patch("process.chunk_enrichment.resolve_workspace_media", return_value=(None, None)), \
             patch.object(pcl, "log_warn") as m_warn:
            pcl._run_prep_stage(self.ws, args)
            pcl._assert_prep_complete(self.ws, [self.ws / "chunks" / "chunk_00.txt"])
        self.assertTrue(m_warn.called)

    def test_prep_forwards_audiocpp_url_from_env(self) -> None:
        ap = pcl.build_argument_parser()
        args = ap.parse_args([str(self.ws)])
        captured = {}
        def fake_enrich(cfg):
            captured["cfg"] = cfg
            return 1
        with patch.dict(os.environ, {"AUDIOCPP_URL": "http://100.115.25.30:8080/v1/tasks/run"}), \
             patch.object(pcl, "enrich_workspace_chunks", side_effect=fake_enrich), \
             patch("process.chunk_enrichment.resolve_workspace_media", return_value=("a.m4a", "v.mp4")):
            pcl._run_prep_stage(self.ws, args)
        self.assertEqual(captured["cfg"].song_cfg.audiocpp_url, "http://100.115.25.30:8080/v1/tasks/run")


if __name__ == "__main__":
    unittest.main()
