"""Time formatting and parsing utilities.

Canonical shared time math for all skills and scripts.
"""

from __future__ import annotations

import re


def fmt_ts(seconds: float | int) -> str:
    """Format seconds → HH:MM:SS."""
    sec = int(seconds)
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def fmt_hhmmss(seconds: float | int) -> str:
    """Format seconds → strictly 3-segment 00:00:00."""
    sec = int(seconds)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_ts(ts_str: str) -> int:
    """Parse HH:MM:SS or MM:SS string → int seconds.

    Handles both 3-part (HH:MM:SS) and 2-part (MM:SS) formats.
    Returns 0 on parse failure.
    """
    if not ts_str:
        return 0
    clean = ts_str.strip()
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})", clean)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.match(r"^(\d{1,2}):(\d{2})", clean)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 0
