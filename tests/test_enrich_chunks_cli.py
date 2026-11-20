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


if __name__ == "__main__":
    unittest.main()
