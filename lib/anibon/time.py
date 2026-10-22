"""Time formatting and parsing utilities.

Consumers (before extraction):
  fmt_ts   — _chunker.py:5, _transcript.py:5 (identical)
  fmt_hhmmss — plan_highlight.py:41, verify_highlight.py (identical)
  parse_ts — merge_timestamps.py:6, pack_timestamps.py (inline), plan_highlight.py:30
"""


import re


def fmt_ts(seconds: float) -> str:
    """Format float seconds → HH:MM:SS."""
    return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"


def fmt_hhmmss(seconds: int) -> str:
    """Format int seconds → HH:MM:SS."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_ts(ts_str: str) -> int:
    """Parse HH:MM:SS or MM:SS string → int seconds.

    Handles both 3-part (HH:MM:SS) and 2-part (MM:SS) formats.
    Returns 0 on parse failure.
    """
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})", ts_str.strip())
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.match(r"^(\d{1,2}):(\d{2})", ts_str.strip())
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 0
