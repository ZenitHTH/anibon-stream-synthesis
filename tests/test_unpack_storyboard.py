#!/usr/bin/env python3
"""Tests for unpack_storyboard.py."""
import os
import sys
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anibon-stream-activity" / "scripts"))
from unpack_storyboard import (
    calculate_tile_bbox,
    extract_slides_from_mhtml_bytes,
    crop_frame_at_second,
)

def test_calculate_tile_bbox():
    # 3x3 grid on a 960x540 image (each tile 320x180)
    bbox = calculate_tile_bbox(tile_index=4, grid_cols=3, grid_rows=3, img_w=960, img_h=540)
    assert bbox == (320, 180, 640, 360)


def test_extract_slides_from_mhtml_bytes(tmp_path):
    # Mock MHTML multipart content with JPEG markers
    # Create a small real JPEG using PIL
    img = Image.new("RGB", (320, 180), color="blue")
    img_path = tmp_path / "sample.jpg"
    img.save(img_path, "JPEG")
    jpeg_bytes = img_path.read_bytes()
    
    mhtml_content = b"--boundary\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n--boundary--"
    slides = extract_slides_from_mhtml_bytes(mhtml_content, str(tmp_path / "slides"))
    assert len(slides) == 1
    assert os.path.exists(slides[0])


def test_extract_slides_direct_jpeg(tmp_path):
    img = Image.new("RGB", (320, 180), color="green")
    img_path = tmp_path / "direct_sprite.jpg"
    img.save(img_path, "JPEG")
    jpeg_bytes = img_path.read_bytes()

    slides = extract_slides_from_mhtml_bytes(jpeg_bytes, str(tmp_path / "direct_slides"))
    assert len(slides) == 1
    assert os.path.exists(slides[0])


def test_crop_frame_at_second(tmp_path):
    # Create a 3x3 grid image (960x540) with red tile at center
    sheet = Image.new("RGB", (960, 540), color="white")
    tile_img = Image.new("RGB", (320, 180), color="red")
    sheet.paste(tile_img, (320, 180)) # tile index 4
    
    slide_path = tmp_path / "slide_0001.jpg"
    sheet.save(slide_path, "JPEG")
    
    out_crop = tmp_path / "crop_target.jpg"
    # Target second that lands on tile index 4 out of 9 tiles (duration 90s, tile 4 is around 45s)
    crop_frame_at_second([str(slide_path)], target_sec=45.0, total_duration=90.0, out_path=str(out_crop), grid_cols=3, grid_rows=3)
    
    assert os.path.exists(out_crop)
    with Image.open(out_crop) as cropped:
        assert cropped.size == (320, 180)
        # Check center pixel is red
        r, g, b = cropped.getpixel((160, 90))
        assert r > 200 and g < 50 and b < 50
