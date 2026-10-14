import sys
import unittest
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from skills.anibon_livechat_analysis.scripts.visual_chat_crop import get_chat_roi, build_crop_filter
except (ImportError, ModuleNotFoundError):
    from visual_chat_crop import get_chat_roi, build_crop_filter


class TestVisualChatCrop(unittest.TestCase):
    def test_get_chat_roi_bottom_right(self):
        roi = get_chat_roi("bottom-right", 1280, 720)
        self.assertEqual(roi["w"], 320)
        self.assertEqual(roi["h"], 302)
        self.assertEqual(roi["x"], 960)
        self.assertEqual(roi["y"], 388)

    def test_get_chat_roi_left(self):
        roi = get_chat_roi("left", 1280, 720)
        self.assertEqual(roi["w"], 358)
        self.assertEqual(roi["h"], 432)
        self.assertEqual(roi["x"], 12)
        self.assertEqual(roi["y"], 158)

    def test_build_crop_filter(self):
        roi = {"w": 320, "h": 302, "x": 960, "y": 388}
        self.assertEqual(build_crop_filter(roi), "crop=320:302:960:388")

    def test_get_chat_roi_unknown_layout(self):
        with self.assertRaisesRegex(ValueError, "Unknown layout"):
            get_chat_roi("invalid-preset", 1280, 720)


if __name__ == "__main__":
    unittest.main()
