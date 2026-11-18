"""Shared lightweight pixel-tone classifiers for OBS webcam vs LiveChat disambiguation."""
from __future__ import annotations


def face_tone_fraction(rgb: bytes) -> float:
    """Estimate fraction of pixels matching indoor neutral/warm human skin tones."""
    n = len(rgb) // 3
    if n < 16:
        return 0.0
    rs, gs, bs = rgb[0 : n * 3 : 3], rgb[1 : n * 3 : 3], rgb[2 : n * 3 : 3]
    hits = sum(
        1 for r, g, b in zip(rs, gs, bs)
        if 95 <= r <= 245 and r >= b - 8 and g >= b - 10 and (r - b) <= 65 and (g - r) <= 18
    )
    return hits / n


def green_chat_fraction(rgb: bytes) -> float:
    """Estimate fraction of pixels matching green YouTube LiveChat overlay bars."""
    n = len(rgb) // 3
    if n < 16:
        return 0.0
    rs, gs, bs = rgb[0 : n * 3 : 3], rgb[1 : n * 3 : 3], rgb[2 : n * 3 : 3]
    return sum(1 for r, g, b in zip(rs, gs, bs) if g > r + 10 and g > b + 10) / n
