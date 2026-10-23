"""
video — Video and storyboard processing utilities.
"""

from __future__ import annotations

from video.storyboard import (
    calculate_tile_bbox,
    crop_frame_at_second,
    extract_slides_from_mhtml_bytes,
    extract_slides_from_mhtml_file,
)

__all__ = [
    "calculate_tile_bbox",
    "crop_frame_at_second",
    "extract_slides_from_mhtml_bytes",
    "extract_slides_from_mhtml_file",
]
