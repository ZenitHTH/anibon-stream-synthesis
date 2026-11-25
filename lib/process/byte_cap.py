"""Topic transition boundary detection and line/byte cap enforcement."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from common.config import BYTE_CAP_LIMIT, LINE_CAP_LIMIT
from process.caveman import clean_caveman_text

TRANSITION_PATTERNS = [
    r"เตรียมเปลี่ยนไปคุย",
    r"สรุปการพูดคุย.*?และเตรียม",
    r"เตรียมเข้าสู่ช่วง",
    r"เตรียมเริ่มเล่นเกม",
    r"เข้าสู่ช่วง",
    r"เตรียมปิดไลฟ์",
]

_PART_NUM_RE = re.compile(r"ส่วนที่ \d+:")
_SECONDARY_CLAUSE_RE = re.compile(
    r"\s+(?:พร้อม(?:กับ|ทั้ง)?|เพื่อ|โดย|แต่|จน|หลังจาก|ระหว่าง|เมื่อเทียบกับ|ใน\s+[A-Za-z0-9]).*$"
)


_THAI_CLAUSE_RE = re.compile(r"(?:และ|กับ|เกี่ยวกับ|พร้อม)")
_THAI_SAFE_BREAK_RE = re.compile(r"(?:เพื่อ|สร้าง|จาก|ก่อน|หลัง|(?<![าิะ])การ|[\u0E40-\u0E44])")
_THAI_NON_START = set("\u0E30\u0E31\u0E32\u0E33\u0E34\u0E35\u0E36\u0E37\u0E38\u0E39\u0E3A\u0E45\u0E47\u0E48\u0E49\u0E4A\u0E4B\u0E4C\u0E4D\u0E4E")
_THAI_LEADING = set("\u0E40\u0E41\u0E42\u0E43\u0E44")


def _is_safe_thai_split(text: str, idx: int) -> bool:
    """Return True if slicing text[:idx] avoids broken grapheme clusters or ASCII tokens."""
    if idx <= 0 or idx >= len(text):
        return True
    prev_c, next_c = text[idx - 1], text[idx]
    if prev_c in _THAI_LEADING or next_c in _THAI_NON_START:
        return False
    return not (prev_c.isascii() and next_c.isascii() and prev_c.isalnum() and next_c.isalnum())


def _find_thai_cut_index(trimmed: str, max_len: int) -> int:
    """Find cleanest cut index <= max_len along spaces, Thai clauses, or syllable boundaries."""
    min_idx = min(10, max_len)
    space_idx = trimmed[:max_len + 1].rfind(" ")
    conn_matches = [min_idx + m.start() for m in _THAI_CLAUSE_RE.finditer(trimmed[min_idx:max_len + 1])]
    primary = max([space_idx] + conn_matches)
    if primary >= min_idx:
        return primary
    safe_matches = [min_idx + m.start() for m in _THAI_SAFE_BREAK_RE.finditer(trimmed[min_idx:max_len + 1])]
    if safe_matches and _is_safe_thai_split(trimmed, safe_matches[-1]):
        return safe_matches[-1]
    for k in range(min(len(trimmed), max_len), min_idx - 1, -1):
        if _is_safe_thai_split(trimmed, k):
            return k
    return max_len


def _compact_topic_clause(text: str, max_len: int = 30) -> str:
    """Compact a single timestamp description into a concise header clause (<= max_len chars)."""
    trimmed = _SECONDARY_CLAUSE_RE.sub("", text).strip(" ,.")
    if len(trimmed) <= max_len:
        return trimmed
    cut_idx = _find_thai_cut_index(trimmed, max_len)
    return trimmed[:cut_idx].strip(" ,.")


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a clean 2-3 topic summary phrase from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[[^\]]+\]\s*", "", s).strip()
        clean = _compact_topic_clause(clean_caveman_text(desc).strip(". "))
        if clean and clean not in topics:
            topics.append(clean)
    if not topics:
        return "สรุปเนื้อหาและบรรยากาศในไลฟ์สตรีม"
    if len(topics) <= 2:
        return " และ ".join(topics)
    return f"{topics[0]}, {topics[len(topics) // 2]} และ {topics[-1]}"


def find_best_boundary(stamps: List[str], target_idx: int, window: int = 4) -> int:
    """Snap split index to the nearest major topic transition marker within window."""
    start = max(1, target_idx - window)
    end = min(len(stamps), target_idx + window + 1)
    matches = [
        idx for idx in range(start, end)
        if any(re.search(pat, stamps[idx]) for pat in TRANSITION_PATTERNS)
    ]
    if matches:
        return min(matches, key=lambda idx: abs(idx - target_idx)) + 1
    return target_idx


def _split_oversized_block(block: str, limit: int) -> Optional[Tuple[str, str]]:
    """Attempt splitting a block exceeding line/byte limit at the optimal boundary."""
    lines = block.splitlines()
    border_indices = [i for i, line in enumerate(lines) if line.startswith("═")]
    stamps_start = (border_indices[1] + 1) if len(border_indices) >= 2 else 3
    header_chunk = "\n".join(lines[:stamps_start])
    stamps = lines[stamps_start:]
    border = lines[border_indices[0]] if border_indices else (lines[0] if lines else "═" * 57)

    is_oversized = (len(stamps) > limit) if limit <= 100 else (len(block.encode("utf-8")) > limit)
    if not is_oversized or len(stamps) < 2:
        return None

    mid = min(max(find_best_boundary(stamps, len(stamps) // 2, window=3), 1), len(stamps) - 1)
    first, second = stamps[:mid], stamps[mid:]
    summary = clean_caveman_text(generate_part_summary(second))
    second_header = f" ส่วนที่ 0: {summary} (⏱ เริ่ม: {second[0][:8]})"
    return f"{header_chunk}\n" + "\n".join(first), f"{border}\n{second_header}\n{border}\n" + "\n".join(second)


def enforce_line_cap(md: str, limit: int = LINE_CAP_LIMIT) -> str:
    """Split any part exceeding line count limit, then renumber."""
    out: List[str] = []
    queue = [b for b in md.strip().split("\n\n") if b.strip()]
    while queue:
        block = queue.pop(0)
        split_result = _split_oversized_block(block, limit)
        if not split_result:
            out.append(block)
            continue
        queue[0:0] = [split_result[0], split_result[1]]
    return "\n\n".join(_PART_NUM_RE.sub(f"ส่วนที่ {i}:", b, count=1) for i, b in enumerate(out, 1))


def enforce_byte_cap(md: str, limit: int = BYTE_CAP_LIMIT) -> str:
    """Split any part exceeding byte limit, then renumber."""
    out: List[str] = []
    queue = [b for b in md.strip().split("\n\n") if b.strip()]
    while queue:
        block = queue.pop(0)
        split_result = _split_oversized_block(block, limit)
        if not split_result:
            out.append(block)
            continue
        queue[0:0] = [split_result[0], split_result[1]]
    return "\n\n".join(_PART_NUM_RE.sub(f"ส่วนที่ {i}:", b, count=1) for i, b in enumerate(out, 1))
