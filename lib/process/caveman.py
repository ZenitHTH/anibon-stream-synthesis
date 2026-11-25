"""Caveman text cleaning and prefix stripping utilities."""
from __future__ import annotations

import re

_FILLER_PREFIX_RE = re.compile(
    r"^(?:(?:ปู่โบ๊ต|ปู่บอร์ด)\s*)?(?:พูดถึงเรื่อง|พูดถึงการ(?![\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]|ตูน)|กล่าวถึง)\s*"
)
_DUAL_TRACK_PREFIX_RE = re.compile(
    r"^เฝ้า(?:สำรวจ|ด่าน|ฟาร์ม|หน้าจอ|สู้บอส|โลก|เกม)[^,]+?พร้อม(?:กับ)?\s*"
)
_LEADING_SPEAKER_RE = re.compile(r"^(?:ปู่โบ๊ต|ปู่บอร์ด)\s*")
_STAMP_PREFIX_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\s*-\s*\[[^\]]+\]\s*)(.*)$")
_SELF_EVAL_SUFFIX_RE = re.compile(
    r"(?:\s*\((?:Analyze|Summary|Discuss|Review|Compare|Watch|Update|Part\s*\d+)[^)]*\))?\s*(?:-\s*(?:Good|OK|Pass|Valid|Done)\.?)\s*$"
    r"|\s*\((?:Analyze|Summary|Discuss|Review|Compare|Watch|Update)\s+[A-Za-z0-9\s,.'\"-]+\)\s*$",
    re.IGNORECASE,
)
_THAI_STUTTER_RE = re.compile(r"โปรโมโมชั่น")


def _strip_prefixes(desc: str) -> str:
    """Strip speaker, filler, repetitive dual-track prefixes, and LLM self-eval artifacts."""
    desc = _FILLER_PREFIX_RE.sub("", desc)
    desc = _LEADING_SPEAKER_RE.sub("", desc)
    desc = _DUAL_TRACK_PREFIX_RE.sub("", desc)
    desc = _SELF_EVAL_SUFFIX_RE.sub("", desc)
    desc = _THAI_STUTTER_RE.sub("โปรโมชั่น", desc)
    return desc.strip()


def clean_caveman_text(text: str) -> str:
    """Strip redundant leading 'ปู่โบ๊ต' and monotonous filler prefixes."""
    m = _STAMP_PREFIX_RE.match(text)
    if m:
        prefix, desc = m.group(1), m.group(2)
        return f"{prefix}{_strip_prefixes(desc)}"
    return _strip_prefixes(text)

