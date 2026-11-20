from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "skills" / "anibon-timestamper-local" / "scripts"))

import interface
import process_chunks_local


class TestEnrichChunksCLI(unittest.TestCase):
    def test_interface_exports_enrichment_symbols(self) -> None:
        self.assertTrue(callable(interface.enrich_workspace_chunks))
        self.assertTrue(callable(interface.load_chunk_enrichment))

    def test_enrich_cli_help_and_local_runner_flag(self) -> None:
        res = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "enrich_chunks.py"), "--help"],
            capture_output=True, text=True, cwd=str(_ROOT),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--audiocpp-url", res.stdout)
        ap = process_chunks_local.build_argument_parser()
        args = ap.parse_args(["/tmp/ws", "--enrich"])
        self.assertTrue(args.enrich)

    def test_enrich_cli_help_succeeds_even_without_numpy(self) -> None:
        code = (
            "import sys, runpy; "
            "sys.modules['numpy'] = None; "
            "sys.argv = ['scripts/enrich_chunks.py', '--help']; "
            "runpy.run_path('scripts/enrich_chunks.py', run_name='__main__')"
        )
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(_ROOT))
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn("--audiocpp-url", res.stdout)

    def test_local_runner_enrich_forwards_whisper_flags(self) -> None:
        from unittest.mock import patch
        ap = process_chunks_local.build_argument_parser()
        args = ap.parse_args([
            "/tmp/ws", "--enrich", "--whisper-bin", "/opt/whisper-cli", "--whisper-model", "/opt/ggml.bin"
        ])
        captured = {}
        def fake_enrich(cfg):
            captured["cfg"] = cfg
            return 1
        with patch("process_chunks_local.enrich_workspace_chunks", side_effect=fake_enrich), \
             patch("process.chunk_enrichment.resolve_workspace_media", return_value=("a.m4a", "v.mp4")):
            process_chunks_local._run_pre_enrichment_if_requested(Path("/tmp/ws"), args)
        self.assertEqual(captured["cfg"].song_cfg.whisper_bin, "/opt/whisper-cli")
        self.assertEqual(captured["cfg"].song_cfg.whisper_model, "/opt/ggml.bin")


if __name__ == "__main__":
    unittest.main()
