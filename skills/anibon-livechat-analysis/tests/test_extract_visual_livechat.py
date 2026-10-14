import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = ImageDraw = None  # type: ignore[assignment]


_test_dir = Path(__file__).resolve().parent
if str(_test_dir) not in sys.path:
    sys.path.insert(0, str(_test_dir))
import conftest  # noqa: F401

from skills.anibon_livechat_analysis.scripts.extract_visual_livechat import (
    parse_time_range,
    parse_gemini_chat_json,
    detect_chat_layout,
    probe_chat_layout,
    probe_chat_layout_from_image,
    acquire_video_slice,
    extract_chat_frames,
    convert_to_frames_data,
    build_arg_parser,
)
import skills.anibon_livechat_analysis.scripts.extract_visual_livechat as evl


class TestExtractVisualLivechat(unittest.TestCase):
    def test_parse_time_range(self):
        start_sec, end_sec = parse_time_range("00:10:00-00:12:30")
        self.assertEqual(start_sec, 600)
        self.assertEqual(end_sec, 750)

    def test_parse_time_range_mm_ss_and_seconds(self):
        self.assertEqual(parse_time_range("10:00-12:30"), (600, 750))
        self.assertEqual(parse_time_range("100-200"), (100, 200))

    def test_parse_time_range_invalid(self):
        with self.assertRaises(ValueError):
            parse_time_range("invalid_range")
        with self.assertRaises(ValueError):
            parse_time_range("00:12:00-00:10:00")

    def test_parse_gemini_chat_json_fenced(self):
        raw_response = """
        Here are the messages:
        ```json
        [
          {"author": "@user1", "text": "ฮัลโหล :_Nerd:", "superchat": null}
        ]
        ```
        """
        parsed = parse_gemini_chat_json(raw_response)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["author"], "@user1")
        self.assertEqual(parsed[0]["text"], "ฮัลโหล :_Nerd:")

    def test_parse_gemini_chat_json_raw_array(self):
        raw = '[{"author": "@user2", "text": "555", "superchat": "THB 50"}]'
        parsed = parse_gemini_chat_json(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["author"], "@user2")
        self.assertEqual(parsed[0]["superchat"], "THB 50")

    def test_parse_gemini_chat_json_dict_with_messages(self):
        raw = '{"messages": [{"author": "@bot", "text": "welcome"}]}'
        parsed = parse_gemini_chat_json(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["author"], "@bot")

    def test_parse_gemini_chat_json_invalid(self):
        self.assertEqual(parse_gemini_chat_json("Not a json at all"), [])
        self.assertEqual(parse_gemini_chat_json(""), [])

    def test_detect_chat_layout_forced(self):
        self.assertEqual(detect_chat_layout("any.mp4", force_pos="bottom-right"), "bottom-right")
        self.assertEqual(detect_chat_layout("any.mp4", force_pos="left"), "left")
        with self.assertRaises(ValueError):
            detect_chat_layout("any.mp4", force_pos="invalid_layout")

    def test_detect_chat_layout_auto_missing_file_defaults_bottom_right(self):
        layout = detect_chat_layout("non_existent_file.mp4", force_pos="auto")
        self.assertEqual(layout, "bottom-right")

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_probe_chat_layout_from_image(self):
        w, h = 1280, 720

        # Image 1: active text patterns in bottom-right
        img_br = Image.new("RGB", (w, h), color=(20, 20, 20))
        draw_br = ImageDraw.Draw(img_br)
        for y in range(400, 680, 20):
            draw_br.text((980, y), "User: High activity live chat message 55555", fill=(255, 255, 255))
        layout_br = probe_chat_layout_from_image(img_br)
        self.assertEqual(layout_br, "bottom-right")

        # Image 2: active text patterns in left side
        img_left = Image.new("RGB", (w, h), color=(20, 20, 20))
        draw_left = ImageDraw.Draw(img_left)
        for y in range(180, 560, 20):
            draw_left.text((20, y), "User: Left overlay active chat message :_Nerd:", fill=(255, 255, 255))
        layout_left = probe_chat_layout_from_image(img_left)
        self.assertEqual(layout_left, "left")

    def test_acquire_video_slice_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_file = tmp_path / "stream.mp4"
            video_file.write_text("dummy video content")
            result = acquire_video_slice(
                video_path=str(video_file),
                video_id=None,
                time_range="00:01:00-00:02:00",
                output_dir=tmp_path,
            )
            self.assertEqual(result, video_file)

    def test_acquire_video_slice_no_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with self.assertRaisesRegex(ValueError, "Either video_path or video_id"):
                acquire_video_slice(video_path=None, video_id=None, time_range="00:01:00-00:02:00", output_dir=tmp_path)

    def test_convert_to_frames_data_flat_list(self):
        parsed = [{"author": "@user1", "text": "hello", "superchat": None}]
        frame_files = [(600, Path("frame_000.jpg"))]
        frames_data = convert_to_frames_data(parsed, frame_files)
        self.assertEqual(len(frames_data), 1)
        self.assertEqual(frames_data[0]["sec"], 600)
        self.assertEqual(frames_data[0]["messages"], parsed)

    def test_convert_to_frames_data_per_frame(self):
        parsed = [
            {
                "frame": "frame_000.jpg",
                "messages": [{"author": "@user1", "text": "hello", "superchat": None}],
            },
            {
                "frame": "frame_001.jpg",
                "messages": [{"author": "@user2", "text": "world", "superchat": None}],
            },
        ]
        frame_files = [(600, Path("frame_000.jpg")), (604, Path("frame_001.jpg"))]
        frames_data = convert_to_frames_data(parsed, frame_files)
        self.assertEqual(len(frames_data), 2)
        self.assertEqual(frames_data[0]["sec"], 600)
        self.assertEqual(frames_data[1]["sec"], 604)

    def test_build_arg_parser(self):
        parser = build_arg_parser()
        args = parser.parse_args(["--video-id", "test12345", "--range", "00:10:00-00:10:10", "--force-pos", "bottom-right"])
        self.assertEqual(args.video_id, "test12345")
        self.assertEqual(args.range, "00:10:00-00:10:10")
        self.assertEqual(args.force_pos, "bottom-right")

    def test_probe_chat_layout_pre_sliced_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dummy_video = tmp_path / "slice.mp4"
            dummy_video.write_text("fake video")

            captured_cmds = []

            def mock_run(cmd, *args, **kwargs):
                captured_cmds.append(cmd)
                class Res:
                    returncode = 1
                    stdout = b""
                    stderr = b""
                return Res()

            with patch.object(evl, "get_video_duration", return_value=120.0), \
                 patch("subprocess.run", side_effect=mock_run):
                layout = probe_chat_layout(dummy_video, sample_sec=600)
                self.assertEqual(layout, "bottom-right")
                self.assertEqual(len(captured_cmds), 1)
                cmd = captured_cmds[0]
                ss_idx = cmd.index("-ss")
                self.assertEqual(cmd[ss_idx + 1], "0")

    def test_extract_chat_frames_pre_sliced_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dummy_video = tmp_path / "slice.mp4"
            dummy_video.write_text("fake video")
            frames_dir = tmp_path / "frames"

            captured_cmds = []

            def mock_run(cmd, *args, **kwargs):
                captured_cmds.append(cmd)
                class Res:
                    returncode = 0
                    stdout = b""
                    stderr = b""
                return Res()

            with patch.object(evl, "get_video_duration", return_value=120.0), \
                 patch.object(evl, "get_video_resolution", return_value=(1280, 720)), \
                 patch("subprocess.run", side_effect=mock_run):
                extract_chat_frames(
                    video_path=dummy_video,
                    start_sec=600,
                    end_sec=720,
                    layout="bottom-right",
                    interval=4.0,
                    frames_dir=frames_dir,
                )
                self.assertEqual(len(captured_cmds), 1)
                cmd = captured_cmds[0]
                ss_idx = cmd.index("-ss")
                to_idx = cmd.index("-to")
                self.assertEqual(cmd[ss_idx + 1], "00:00:00")
                self.assertEqual(cmd[to_idx + 1], "00:02:00")

    def test_extract_chat_frames_full_video_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dummy_video = tmp_path / "full.mp4"
            dummy_video.write_text("fake video")
            frames_dir = tmp_path / "frames"

            captured_cmds = []

            def mock_run(cmd, *args, **kwargs):
                captured_cmds.append(cmd)
                class Res:
                    returncode = 0
                    stdout = b""
                    stderr = b""
                return Res()

            with patch.object(evl, "get_video_duration", return_value=7200.0), \
                 patch.object(evl, "get_video_resolution", return_value=(1280, 720)), \
                 patch("subprocess.run", side_effect=mock_run):
                extract_chat_frames(
                    video_path=dummy_video,
                    start_sec=600,
                    end_sec=720,
                    layout="bottom-right",
                    interval=4.0,
                    frames_dir=frames_dir,
                )
                self.assertEqual(len(captured_cmds), 1)
                cmd = captured_cmds[0]
                ss_idx = cmd.index("-ss")
                to_idx = cmd.index("-to")
                self.assertEqual(cmd[ss_idx + 1], "00:10:00")
                self.assertEqual(cmd[to_idx + 1], "00:12:00")


if __name__ == "__main__":
    unittest.main()
