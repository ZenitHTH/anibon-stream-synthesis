import sys
from pathlib import Path
import pytest

_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from skills.anibon_livechat_analysis.scripts.visual_chat_crop import get_chat_roi, build_crop_filter
except (ImportError, ModuleNotFoundError):
    from visual_chat_crop import get_chat_roi, build_crop_filter



def test_get_chat_roi_bottom_right():
    roi = get_chat_roi("bottom-right", 1280, 720)
    assert roi["w"] == 320
    assert roi["h"] == 302
    assert roi["x"] == 960
    assert roi["y"] == 388


def test_get_chat_roi_left():
    roi = get_chat_roi("left", 1280, 720)
    assert roi["w"] == 358
    assert roi["h"] == 432
    assert roi["x"] == 12
    assert roi["y"] == 158


def test_build_crop_filter():
    roi = {"w": 320, "h": 302, "x": 960, "y": 388}
    assert build_crop_filter(roi) == "crop=320:302:960:388"


def test_get_chat_roi_unknown_layout():
    with pytest.raises(ValueError, match="Unknown layout"):
        get_chat_roi("invalid-preset", 1280, 720)
