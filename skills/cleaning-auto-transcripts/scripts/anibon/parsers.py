"""Timestamp line parsing utilities.

Consumers (before extraction):
  LINE_RE                — pack_timestamps.py:29, merge_timestamps.py:11
  parse_timestamps()     — pack_timestamps.py (2 variants)
  parse_timestamp_line() — merge_timestamps.py:11
"""
import re
from anibon.time import parse_ts

# Standard format:   HH:MM:SS - [Tag][Tag] Description
LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*-\s*((?:\[.*?\])+)\s*(.*)$")

# Flexible format used by merge_timestamps:   HH:MM:SS - [Tag] Desc  or  HH:MM:SS Desc
MERGE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*(?:-\s*)?(?:\[(.*?)\])?\s*(.*)$")


def parse_timestamps(lines: list) -> list:
    """Parse timestamp lines into a chronologically sorted list of dicts.

    Each dict has keys: time (str), sec (int), tag (str), desc (str), raw (str), bytes (int).
    Skips unparsable lines.
    """
    timestamps = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        time_str, tag, desc = m.groups()
        raw = f"{time_str} - {tag} {desc}"
        timestamps.append({
            "time": time_str,
            "sec": parse_ts(time_str),
            "tag": tag,
            "desc": desc,
            "raw": raw,
            "bytes": len(raw.encode("utf-8")),
        })
    timestamps.sort(key=lambda x: x["sec"])
    return timestamps


def parse_timestamp_line(line: str) -> dict | None:
    """Parse a single flexible-format timestamp line.

    Accepts: HH:MM:SS - [Tag] Description
             HH:MM:SS Description  (Tag defaults to "[Talk]")

    Returns dict or None if unparsable.
    """
    line = line.strip()
    if not line:
        return None
    m = MERGE_RE.match(line)
    if not m:
        return None
    ts, tag, desc = m.groups()
    tag_str = f"[{tag}]" if tag else "[Talk]"
    raw = f"{ts} - {tag_str} {desc}"
    return {
        "time": ts,
        "sec": parse_ts(ts),
        "tag": tag_str,
        "desc": desc or "",
        "raw": raw,
        "bytes": len(raw.encode("utf-8")),
    }
