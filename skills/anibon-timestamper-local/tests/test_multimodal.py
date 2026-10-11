"""tests/test_multimodal.py — Unit tests for anibon.multimodal module."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from anibon.multimodal import (
    sec_to_ts,
    build_multimodal_content,
    sample_chunk_keyframes,
    prepare_storyboard_slides,
    unpack_mhtml_storyboard,
)


class TestMultimodal(unittest.TestCase):
    def test_sec_to_ts(self):
        self.assertEqual(sec_to_ts(0), "00:00:00")
        self.assertEqual(sec_to_ts(65), "00:01:05")
        self.assertEqual(sec_to_ts(3988), "01:06:28")
        self.assertEqual(sec_to_ts(7200), "02:00:00")

    def test_build_multimodal_content(self):
        prompt = "Describe these images"
        keyframes = [
            ("00:01:00", Path("/tmp/f1.jpg"), "b64_data_1"),
            ("00:02:00", Path("/tmp/f2.jpg"), "b64_data_2"),
        ]
        content = build_multimodal_content(prompt, keyframes)
        self.assertEqual(len(content), 3)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], prompt)
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/jpeg;base64,b64_data_1")
        self.assertEqual(content[2]["type"], "image_url")
        self.assertEqual(content[2]["image_url"]["url"], "data:image/jpeg;base64,b64_data_2")

    def test_sample_chunk_keyframes_empty_dir(self):
        empty_dir = Path("/tmp/non_existent_slides_dir_12345")
        res = sample_chunk_keyframes(0, 270, empty_dir, Path("/tmp"))
        self.assertEqual(res, [])

    def test_prepare_storyboard_slides_not_found(self):
        dummy_ws = Path("/tmp/empty_workspace_12345")
        self.assertIsNone(prepare_storyboard_slides(dummy_ws))

    def test_unpack_mhtml_dummy(self):
        dummy_mhtml = Path("/tmp/dummy_non_existent.mhtml")
        self.assertEqual(unpack_mhtml_storyboard(dummy_mhtml, Path("/tmp")), 0)


if __name__ == "__main__":
    unittest.main()
