"""Time formatting and parsing utilities.

Consumers (before extraction):
  fmt_ts   — _chunker.py:5, _transcript.py:5 (identical)
  fmt_hhmmss — plan_highlight.py:41, verify_highlight.py (identical)
  parse_ts — merge_timestamps.py:6, pack_timestamps.py (inline), plan_highlight.py:30
"""


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
    parts = ts_str.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0
