#!/usr/bin/env python3
"""
Unpack YouTube Storyboard MHTML into clean JPEG slides and slice high-resolution tile frames.
Supports dynamic grid sizes (3x3, 5x5, 10x10) and prevents blur/pixelation.
"""

import argparse
import glob
import os
import sys
from PIL import Image


def extract_slides_from_mhtml_bytes(data: bytes, output_dir: str) -> list[str]:
    """Extract individual JPEG slides from MHTML multipart byte data or direct JPEG image."""
    os.makedirs(output_dir, exist_ok=True)
    
    # If the input is already a raw JPEG image file
    if data.startswith(b"\xff\xd8"):
        out_path = os.path.join(output_dir, "slide_0001.jpg")
        with open(out_path, "wb") as f:
            f.write(data)
        return [out_path]

    parts = data.split(b"--")
    slide_paths = []
    valid_count = 0
    for p in parts:
        if b"image/jpeg" in p or b"\xff\xd8" in p:
            idx = p.find(b"\xff\xd8")
            end_idx = p.rfind(b"\xff\xd9")
            if idx != -1:
                valid_count += 1
                jpg_data = p[idx : end_idx + 2] if end_idx != -1 else p[idx:]
                out_path = os.path.join(output_dir, f"slide_{valid_count:04d}.jpg")
                with open(out_path, "wb") as f:
                    f.write(jpg_data)
                slide_paths.append(out_path)
    return slide_paths


def extract_slides_from_mhtml_file(mhtml_path: str, output_dir: str) -> list[str]:
    """Extract individual JPEG slides from an MHTML file path or direct image file."""
    with open(mhtml_path, "rb") as f:
        data = f.read()
    return extract_slides_from_mhtml_bytes(data, output_dir)


def calculate_tile_bbox(
    tile_index: int, grid_cols: int, grid_rows: int, img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    """Calculate the (left, top, right, bottom) bounding box for a given tile index."""
    col = tile_index % grid_cols
    row = tile_index // grid_cols
    tile_w = img_w // grid_cols
    tile_h = img_h // grid_rows
    x1 = col * tile_w
    y1 = row * tile_h
    return (x1, y1, x1 + tile_w, y1 + tile_h)


def crop_frame_at_second(
    slide_paths: list[str],
    target_sec: float,
    total_duration: float,
    out_path: str,
    grid_cols: int = 3,
    grid_rows: int = 3,
) -> str:
    """Extract and crop a single frame corresponding to target_sec from unpacked slides."""
    if not slide_paths:
        raise ValueError("No slides provided")

    total_slides = len(slide_paths)
    tiles_per_slide = grid_cols * grid_rows
    total_tiles = total_slides * tiles_per_slide

    sec_per_tile = total_duration / total_tiles if total_tiles > 0 and total_duration > 0 else 10.0
    tile_global_idx = min(total_tiles - 1, max(0, int(target_sec / sec_per_tile)))

    slide_idx = tile_global_idx // tiles_per_slide
    tile_in_slide = tile_global_idx % tiles_per_slide

    chosen_slide_path = slide_paths[min(slide_idx, len(slide_paths) - 1)]
    with Image.open(chosen_slide_path) as img:
        bbox = calculate_tile_bbox(tile_in_slide, grid_cols, grid_rows, img.width, img.height)
        cropped = img.crop(bbox)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        cropped.save(out_path, "JPEG", quality=95)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Unpack storyboard and crop high-res frames")
    parser.add_argument("--mhtml", help="Path to storyboard MHTML file or glob pattern")
    parser.add_argument("--out-dir", default="frames/slides", help="Output directory for unpacked slides")
    parser.add_argument("--crop-sec", type=float, help="Target timestamp in seconds to crop")
    parser.add_argument("--duration", type=float, default=0.0, help="Total stream duration in seconds")
    parser.add_argument("--out-crop", help="Output path for cropped JPEG frame")
    parser.add_argument("--grid-cols", type=int, default=3, help="Grid columns per slide (default 3)")
    parser.add_argument("--grid-rows", type=int, default=3, help="Grid rows per slide (default 3)")

    args = parser.parse_args()

    if args.mhtml:
        matches = glob.glob(args.mhtml)
        if not matches:
            print(f"Error: No files found matching {args.mhtml}", file=sys.stderr)
            sys.exit(1)
        mhtml_file = matches[0]
        slides = extract_slides_from_mhtml_file(mhtml_file, args.out_dir)
        print(f"Extracted {len(slides)} slides into {args.out_dir}")

        if args.crop_sec is not None and args.out_crop:
            crop_frame_at_second(
                slides,
                target_sec=args.crop_sec,
                total_duration=args.duration,
                out_path=args.out_crop,
                grid_cols=args.grid_cols,
                grid_rows=args.grid_rows,
            )
            print(f"Cropped frame at {args.crop_sec}s -> {args.out_crop}")


if __name__ == "__main__":
    main()
