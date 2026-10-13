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
        # 1 initial prompt text + (1 timestamp label + 1 image_url) per keyframe = 5
        self.assertEqual(len(content), 5)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], prompt)
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("00:01:00", content[1]["text"])
        self.assertEqual(content[2]["type"], "image_url")
        self.assertEqual(content[2]["image_url"]["url"], "data:image/jpeg;base64,b64_data_1")
        self.assertEqual(content[3]["type"], "text")
        self.assertIn("00:02:00", content[3]["text"])
        self.assertEqual(content[4]["type"], "image_url")
        self.assertEqual(content[4]["image_url"]["url"], "data:image/jpeg;base64,b64_data_2")

    def test_select_target_seconds_incomplete_cues(self):
        from anibon.multimodal import select_target_seconds
        items = [
            {"start": 10, "text": "สวัสดีครับทุกคน วันนี้มาคุยกัน"},
            {"start": 60, "text": "เนี่ยดูดิ อันนี้ในจอคืออะไร"},
            {"start": 120, "text": "ส่วนอันนี้เป็นอีกเกมหนึ่ง"},
            {"start": 200, "text": "ขอบคุณทุกคนที่ติดตามครับ"},
        ]
        res = select_target_seconds(0, 270, num_frames=2, items=items)
        self.assertEqual(len(res), 2)
        # Should pick the cues at 60 and 120
        self.assertIn(60, res)
        self.assertIn(120, res)

    def test_select_target_seconds_full_context_interesting(self):
        from anibon.multimodal import select_target_seconds
        items = [
            {"start": 30, "text": "วันนี้เราจะมาวิเคราะห์ระบบเศรษฐกิจและการเมืองระยะยาว"},
            {"start": 110, "text": "ปัญหาคือว่ามันกระทบกับทุกคนมาก 555 ไม่น่าเชื่อเลย!"},
            {"start": 220, "text": "สรุปคือแนวทางนี้ต้องปรับแก้ใหม่ทั้งหมด"},
        ]
        res = select_target_seconds(0, 270, num_frames=2, items=items)
        self.assertEqual(len(res), 2)

    def test_select_target_seconds_dynamic_min_max(self):
        from anibon.multimodal import select_target_seconds
        # 1 cue -> ensures at least 3 frames
        items_few = [{"start": 50, "text": "ดูอันนี้ดิ"}]
        res_few = select_target_seconds(0, 270, min_frames=3, max_frames=5, items=items_few)
        self.assertGreaterEqual(len(res_few), 3)

        # 4 distinct cues -> returns 4 frames
        items_many = [
            {"start": 30, "text": "ดูอันนี้ดิ"},
            {"start": 70, "text": "ตัวนี้คือใคร"},
            {"start": 120, "text": "ในจอนี้มีอะไร"},
            {"start": 180, "text": "เปิดดูรูปนี้"},
        ]
        res_many = select_target_seconds(0, 270, min_frames=3, max_frames=5, items=items_many)
        self.assertEqual(len(res_many), 4)

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
