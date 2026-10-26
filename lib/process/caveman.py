"""Caveman text cleaning and prefix stripping utilities."""
from __future__ import annotations

import re

_FILLER_PREFIX_RE = re.compile(
    r"^(?:(?:ปู่โบ๊ต|ปู่บอร์ด)\s*)?(?:พูดถึงเรื่อง|พูดถึงการ|กล่าวถึง)\s*"
)
_LEADING_SPEAKER_RE = re.compile(r"^(?:ปู่โบ๊ต|ปู่บอร์ด)\s*")
_STAMP_PREFIX_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*)(.*)$")


def clean_caveman_text(text: str) -> str:
    """Strip redundant leading 'ปู่โบ๊ต' and monotonous filler prefixes."""
    m = _STAMP_PREFIX_RE.match(text)
    if m:
        prefix, desc = m.group(1), m.group(2)
        desc = _FILLER_PREFIX_RE.sub("", desc)
        desc = _LEADING_SPEAKER_RE.sub("", desc).strip()
        return f"{prefix}{desc}"
    cleaned = _FILLER_PREFIX_RE.sub("", text)
    return _LEADING_SPEAKER_RE.sub("", cleaned).strip()
