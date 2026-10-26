"""
anibon.garbled_rules — Validation, filtering, and domain hints for garbled tokens.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

BATCH_SIZE = 10
MIN_PURE_THAI_LEN = 4
MIN_GARBLED_LEN = 2
MAX_GARBLED_LEN = 40
FILLER_PREFIXES = (
    "ตัวออกมาเป็นเรียกว่าแบบ",
    "ตัวออกมาเป็นเรียกว่า",
    "ตัวออกมาเป็น",
    "ตัวของมาเป็น",
)
BLOCKED_THAI_WORDS = frozenset({
    "ครัว", "บีด", "เวฟ", "สัญญา", "ไอ้เหี้ย", "ไอ้สัตว์", "พศ", "คายเครียด",
    "มยเอ้า", "โคมั้มั้ล่ะ", "มั้ฮะเออเออ", "ชราเออ", "ไอ้หยงๆ", "ฉี่ๆ", "ชอ", "ไวท",
})
RAW_TRANSCRIPT_NAMES = (
    "raw_transcript.th-orig.json3",
    "raw_transcript.json",
    "raw_transcript.th.json3",
)
UNSAFE_TARGET_KEYWORDS = frozenset({"null", "none", "unknown", "n/a", "-"})


def has_garbled_candidates(workspace: Path) -> bool:
    """Check if raw garbled candidate notes exist in workspace."""
    raw_dir = workspace / "garbled_notes_raw"
    notes_json = workspace / "garbled_notes.json"
    has_raw = raw_dir.is_dir() and any(raw_dir.glob("*.txt"))
    return bool(has_raw or notes_json.is_file())


def strip_filler_prefix(garbled: str) -> str:
    """Strip common spoken Thai filler prefixes from spotter tokens."""
    cleaned = garbled.strip()
    for prefix in FILLER_PREFIXES:
        if cleaned.startswith(prefix):
            rest = cleaned[len(prefix):].strip()
            if len(rest) >= MIN_GARBLED_LEN:
                return rest
    return cleaned


def has_non_thai_script(text: str) -> bool:
    """Return True if text contains Latin, CJK, or Kana/Hangul characters."""
    return bool(re.search(r"[A-Za-z\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", text))


def is_valid_candidate_token(garbled: str) -> bool:
    """Check if a garbled token is safe to consider for regex replacement."""
    if not (MIN_GARBLED_LEN <= len(garbled) <= MAX_GARBLED_LEN):
        return False
    if garbled in BLOCKED_THAI_WORDS:
        return False
    if not has_non_thai_script(garbled) and len(garbled) < MIN_PURE_THAI_LEN:
        return False
    return True


def is_safe_replacement(garbled: str, correct: Optional[str]) -> bool:
    """Validate that a resolved (garbled -> correct) pair will not cause false cascades."""
    if not correct or not isinstance(correct, str):
        return False
    target = correct.strip()
    if not target or target.lower() in UNSAFE_TARGET_KEYWORDS:
        return False
    if garbled.lower() == target.lower() or not is_valid_candidate_token(garbled):
        return False
    if _is_ascii_subset(garbled, target):
        return False
    return True


def _is_ascii_subset(garbled: str, target: str) -> bool:
    return bool(
        garbled.isalpha()
        and garbled.isascii()
        and garbled.lower() in target.lower().split()
    )


def load_raw_transcript_compact(workspace: Path) -> str:
    """Load space-stripped raw Google ASR text for anti-cascade ground-truth checks."""
    for name in RAW_TRANSCRIPT_NAMES:
        path = workspace / name
        if path.is_file():
            content = _read_compact_file(path)
            if content:
                return content
    return ""


def _read_compact_file(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
        return re.sub(r"\s+", "", raw)
    except Exception:
        return ""


def _extract_stream_title(workspace: Path) -> str:
    info_path = workspace / "info.json"
    if not info_path.is_file():
        return ""
    try:
        data = json.loads(info_path.read_text(encoding="utf-8"))
        return str(data.get("title", ""))
    except Exception:
        return ""


def _extract_glossary_names(workspace: Path) -> List[str]:
    gloss_path = workspace / "entity_glossary.json"
    if not gloss_path.is_file():
        return []
    try:
        gloss = json.loads(gloss_path.read_text(encoding="utf-8"))
        return [k for k in list(gloss.keys())[:80] if len(k) >= 3]
    except Exception:
        return []


def load_domain_hint(workspace: Path) -> str:
    """Build compact domain proper-noun hint from info.json title and entity_glossary.json."""
    parts: List[str] = []
    title = _extract_stream_title(workspace)
    if title:
        parts.append(f"Stream Title: {title}")
    names = _extract_glossary_names(workspace)
    if names:
        parts.append("Known Entities: " + ", ".join(names))
    return "\n".join(parts)
