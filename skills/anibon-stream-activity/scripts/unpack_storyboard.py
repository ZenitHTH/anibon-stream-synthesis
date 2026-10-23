#!/usr/bin/env python3
"""
Unpack YouTube Storyboard MHTML and slice high-resolution tile frames.
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from video.storyboard import (
    calculate_tile_bbox,
    crop_frame_at_second,
    extract_slides_from_mhtml_bytes,
    extract_slides_from_mhtml_file,
)


def _build_cli_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for unpack_storyboard."""
    parser = argparse.ArgumentParser(description="Unpack storyboard and crop high-res frames")
    parser.add_argument("--mhtml", help="Path to storyboard MHTML file or glob pattern")
    parser.add_argument("--out-dir", default="frames/slides", help="Output directory for unpacked slides")
    parser.add_argument("--crop-sec", type=float, help="Target timestamp in seconds to crop")
    parser.add_argument("--duration", type=float, default=0.0, help="Total stream duration in seconds")
    parser.add_argument("--out-crop", help="Output path for cropped JPEG frame")
    parser.add_argument("--grid-cols", type=int, default=3, help="Grid columns per slide (default 3)")
    parser.add_argument("--grid-rows", type=int, default=3, help="Grid rows per slide (default 3)")
    return parser


def main() -> None:
    args = _build_cli_parser().parse_args()
    if not args.mhtml:
        return
    matches = glob.glob(args.mhtml)
    if not matches:
        print(f"Error: No files found matching {args.mhtml}", file=sys.stderr)
        sys.exit(1)

    slides = extract_slides_from_mhtml_file(matches[0], args.out_dir)
    print(f"Extracted {len(slides)} slides into {args.out_dir}")
    if args.crop_sec is not None and args.out_crop:
        crop_frame_at_second(
            slides, args.crop_sec, args.duration, args.out_crop, args.grid_cols, args.grid_rows
        )
        print(f"Cropped frame at {args.crop_sec}s -> {args.out_crop}")


if __name__ == "__main__":
    main()
