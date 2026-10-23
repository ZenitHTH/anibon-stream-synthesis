"""
Storyboard extraction and frame cropping utilities.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]


def _extract_single_jpeg(data: bytes, output_dir: str) -> List[str]:
    """Save raw JPEG byte data as slide 1."""
    out_path = os.path.join(output_dir, "slide_0001.jpg")
    with open(out_path, "wb") as f:
        f.write(data)
    return [out_path]


def _extract_jpeg_part(part: bytes) -> bytes | None:
    """Extract JPEG segment between SOI and EOI markers."""
    idx = part.find(b"\xff\xd8")
    if idx == -1:
        return None
    end_idx = part.rfind(b"\xff\xd9")
    if end_idx != -1:
        return part[idx : end_idx + 2]
    return part[idx:]


def extract_slides_from_mhtml_bytes(data: bytes, output_dir: str) -> List[str]:
    """Extract individual JPEG slides from MHTML multipart data or raw JPEG."""
    os.makedirs(output_dir, exist_ok=True)
    if data.startswith(b"\xff\xd8"):
        return _extract_single_jpeg(data, output_dir)

    slide_paths: List[str] = []
    for part in data.split(b"--"):
        if b"image/jpeg" not in part and b"\xff\xd8" not in part:
            continue
        jpg_data = _extract_jpeg_part(part)
        if not jpg_data:
            continue
        idx = len(slide_paths) + 1
        path = os.path.join(output_dir, f"slide_{idx:04d}.jpg")
        with open(path, "wb") as f:
            f.write(jpg_data)
        slide_paths.append(path)
    return slide_paths


def extract_slides_from_mhtml_file(mhtml_path: str, output_dir: str) -> List[str]:
    """Extract individual JPEG slides from an MHTML file path or raw image."""
    data = Path(mhtml_path).read_bytes()
    return extract_slides_from_mhtml_bytes(data, output_dir)


def calculate_tile_bbox(
    tile_index: int, grid_cols: int, grid_rows: int, img_w: int, img_h: int
) -> Tuple[int, int, int, int]:
    """Calculate the bounding box (left, top, right, bottom) for a tile index."""
    col = tile_index % grid_cols
    row = tile_index // grid_cols
    tile_w = img_w // grid_cols
    tile_h = img_h // grid_rows
    x1 = col * tile_w
    y1 = row * tile_h
    return (x1, y1, x1 + tile_w, y1 + tile_h)


def _resolve_tile_position(
    target_sec: float, total_duration: float, total_tiles: int, tiles_per_slide: int
) -> Tuple[int, int]:
    """Determine slide index and local tile index for a target second."""
    sec_per_tile = total_duration / total_tiles if total_tiles > 0 and total_duration > 0 else 10.0
    global_idx = min(total_tiles - 1, max(0, int(target_sec / sec_per_tile)))
    return global_idx // tiles_per_slide, global_idx % tiles_per_slide


def crop_frame_at_second(
    slide_paths: List[str],
    target_sec: float,
    total_duration: float,
    out_path: str,
    grid_cols: int = 3,
    grid_rows: int = 3,
) -> str:
    """Extract and crop a single frame for target_sec from unpacked slides."""
    if not slide_paths:
        raise ValueError("No slides provided")
    if Image is None:
        raise RuntimeError("Pillow required for crop_frame_at_second")

    tiles_per_slide = grid_cols * grid_rows
    total_tiles = len(slide_paths) * tiles_per_slide
    slide_idx, tile_in_slide = _resolve_tile_position(
        target_sec, total_duration, total_tiles, tiles_per_slide
    )

    chosen_path = slide_paths[min(slide_idx, len(slide_paths) - 1)]
    with Image.open(chosen_path) as img:
        bbox = calculate_tile_bbox(tile_in_slide, grid_cols, grid_rows, img.width, img.height)
        cropped = img.crop(bbox)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        cropped.save(out_path, "JPEG", quality=95)
    return out_path
