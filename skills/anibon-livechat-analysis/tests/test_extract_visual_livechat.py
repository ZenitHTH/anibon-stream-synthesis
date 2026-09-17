import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from skills.anibon_livechat_analysis.scripts.extract_visual_livechat import (
    parse_time_range,
    parse_gemini_chat_json,
    detect_chat_layout,
    probe_chat_layout_from_image,
    acquire_video_slice,
    convert_to_frames_data,
    build_arg_parser,
)


def test_parse_time_range():
    start_sec, end_sec = parse_time_range("00:10:00-00:12:30")
    assert start_sec == 600
    assert end_sec == 750


def test_parse_time_range_mm_ss_and_seconds():
    assert parse_time_range("10:00-12:30") == (600, 750)
    assert parse_time_range("100-200") == (100, 200)


def test_parse_time_range_invalid():
    with pytest.raises(ValueError):
        parse_time_range("invalid_range")
    with pytest.raises(ValueError):
        parse_time_range("00:12:00-00:10:00")


def test_parse_gemini_chat_json_fenced():
    raw_response = """
    Here are the messages:
    ```json
    [
      {"author": "@user1", "text": "ฮัลโหล :_Nerd:", "superchat": null}
    ]
    ```
    """
    parsed = parse_gemini_chat_json(raw_response)
    assert len(parsed) == 1
    assert parsed[0]["author"] == "@user1"
    assert parsed[0]["text"] == "ฮัลโหล :_Nerd:"


def test_parse_gemini_chat_json_raw_array():
    raw = '[{"author": "@user2", "text": "555", "superchat": "THB 50"}]'
    parsed = parse_gemini_chat_json(raw)
    assert len(parsed) == 1
    assert parsed[0]["author"] == "@user2"
    assert parsed[0]["superchat"] == "THB 50"


def test_parse_gemini_chat_json_dict_with_messages():
    raw = '{"messages": [{"author": "@bot", "text": "welcome"}]}'
    parsed = parse_gemini_chat_json(raw)
    assert len(parsed) == 1
    assert parsed[0]["author"] == "@bot"


def test_parse_gemini_chat_json_invalid():
    assert parse_gemini_chat_json("Not a json at all") == []
    assert parse_gemini_chat_json("") == []


def test_detect_chat_layout_forced():
    assert detect_chat_layout("any.mp4", force_pos="bottom-right") == "bottom-right"
    assert detect_chat_layout("any.mp4", force_pos="left") == "left"
    with pytest.raises(ValueError):
        detect_chat_layout("any.mp4", force_pos="invalid_layout")


def test_detect_chat_layout_auto_missing_file_defaults_bottom_right():
    # If file doesn't exist or probing fails, fallback to bottom-right
    layout = detect_chat_layout("non_existent_file.mp4", force_pos="auto")
    assert layout == "bottom-right"


def test_probe_chat_layout_from_image():
    # Create synthetic test image (1280x720)
    w, h = 1280, 720

    # Image 1: active text patterns in bottom-right
    img_br = Image.new("RGB", (w, h), color=(20, 20, 20))
    draw_br = ImageDraw.Draw(img_br)
    # Bottom-right ROI is approx x: 960..1280, y: 388..690
    for y in range(400, 680, 20):
        draw_br.text((980, y), "User: High activity live chat message 55555", fill=(255, 255, 255))
    layout_br = probe_chat_layout_from_image(img_br)
    assert layout_br == "bottom-right"

    # Image 2: active text patterns in left side
    img_left = Image.new("RGB", (w, h), color=(20, 20, 20))
    draw_left = ImageDraw.Draw(img_left)
    # Left ROI is approx x: 12..370, y: 158..590
    for y in range(180, 560, 20):
        draw_left.text((20, y), "User: Left overlay active chat message :_Nerd:", fill=(255, 255, 255))
    layout_left = probe_chat_layout_from_image(img_left)
    assert layout_left == "left"


def test_acquire_video_slice_existing_file(tmp_path):
    video_file = tmp_path / "stream.mp4"
    video_file.write_text("dummy video content")
    result = acquire_video_slice(
        video_path=str(video_file),
        video_id=None,
        time_range="00:01:00-00:02:00",
        output_dir=tmp_path,
    )
    assert result == video_file


def test_acquire_video_slice_no_input_error(tmp_path):
    with pytest.raises(ValueError, match="Either video_path or video_id"):
        acquire_video_slice(video_path=None, video_id=None, time_range="00:01:00-00:02:00", output_dir=tmp_path)


def test_convert_to_frames_data_flat_list():
    parsed = [{"author": "@user1", "text": "hello", "superchat": None}]
    frame_files = [(600, Path("frame_000.jpg"))]
    frames_data = convert_to_frames_data(parsed, frame_files)
    assert len(frames_data) == 1
    assert frames_data[0]["sec"] == 600
    assert frames_data[0]["messages"] == parsed


def test_convert_to_frames_data_per_frame():
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
    assert len(frames_data) == 2
    assert frames_data[0]["sec"] == 600
    assert frames_data[1]["sec"] == 604


def test_build_arg_parser():
    parser = build_arg_parser()
    args = parser.parse_args(["--video-id", "test12345", "--range", "00:10:00-00:10:10", "--force-pos", "bottom-right"])
    assert args.video_id == "test12345"
    assert args.range == "00:10:00-00:10:10"
    assert args.force_pos == "bottom-right"
