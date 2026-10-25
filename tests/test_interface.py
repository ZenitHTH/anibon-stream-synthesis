"""
Unit tests for the root unified interface facade (lib/interface.py).
"""

from __future__ import annotations

import unittest
from pathlib import Path

import interface


class TestLibInterface(unittest.TestCase):
    def test_subpackages_exposed(self):
        self.assertTrue(hasattr(interface, "common"))
        self.assertTrue(hasattr(interface, "download"))
        self.assertTrue(hasattr(interface, "chunk"))
        self.assertTrue(hasattr(interface, "process"))

    def test_all_symbols_in_dunder_all_exist(self):
        for name in interface.__all__:
            self.assertTrue(
                hasattr(interface, name),
                f"Symbol '{name}' listed in __all__ but missing on interface module",
            )

    def test_common_functions_callable(self):
        self.assertTrue(callable(interface.clean_text))
        self.assertTrue(callable(interface.fmt_ts))
        self.assertTrue(callable(interface.parse_ts))
        self.assertTrue(callable(interface.load_config))
        self.assertTrue(callable(interface.resource_path))
        self.assertEqual(interface.fmt_ts(125), "00:02:05")
        self.assertEqual(interface.parse_ts("00:02:05"), 125)

    def test_download_functions_callable(self):
        self.assertTrue(callable(interface.detect_transcript_source))
        self.assertTrue(callable(interface.is_youtube_auto_transcript))
        self.assertTrue(callable(interface.download_transcript))
        self.assertTrue(callable(interface.load_transcript))
        self.assertTrue(callable(interface.save_metadata))
        self.assertEqual(interface.DEFAULT_SUB_LANGS, "th-orig,en-orig,th,en")

    def test_chunk_functions_callable(self):
        self.assertTrue(callable(interface.load_chunks))
        self.assertTrue(callable(interface.load_state))
        self.assertTrue(callable(interface.save_state))
        self.assertTrue(callable(interface.chunk_sort_key))
        self.assertEqual(interface.chunk_sort_key(Path("chunk_05.txt")), 5)

    def test_process_functions_callable(self):
        self.assertTrue(callable(interface.detect_signals_for_chunks))
        self.assertTrue(callable(interface.get_domain_guidance))
        self.assertTrue(callable(interface.run_recursive_mode))
        self.assertTrue(callable(interface.run_group_mode))
        self.assertTrue(callable(interface.finalize_and_assemble_timestamps))
        self.assertTrue(callable(interface.audit_timestamps_against_glossary))


if __name__ == "__main__":
    unittest.main()
