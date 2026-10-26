"""Topic transition boundary detection and byte-cap enforcement."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from common.config import BYTE_CAP_LIMIT
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


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a clean 2-3 topic summary phrase from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        clean = clean_caveman_text(desc).strip(". ")
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
    """Attempt splitting a block exceeding limit at the optimal boundary."""
    lines = block.splitlines()
    border_indices = [i for i, line in enumerate(lines) if line.startswith("═")]
    stamps_start = (border_indices[1] + 1) if len(border_indices) >= 2 else 3
    header_chunk = "\n".join(lines[:stamps_start])
    stamps = lines[stamps_start:]
    border = lines[border_indices[0]] if border_indices else (lines[0] if lines else "═" * 57)

    if len(block.encode("utf-8")) <= limit or len(lines) < 4 or len(stamps) < 2:
        return None

    mid = min(max(find_best_boundary(stamps, len(stamps) // 2, window=3), 1), len(stamps) - 1)
    first, second = stamps[:mid], stamps[mid:]
    summary = clean_caveman_text(generate_part_summary(second))
    second_header = f" ส่วนที่ 0: {summary} (⏱ เริ่ม: {second[0][:8]})"
    return f"{header_chunk}\n" + "\n".join(first), f"{border}\n{second_header}\n{border}\n" + "\n".join(second)


def enforce_byte_cap(md: str, limit: int = BYTE_CAP_LIMIT) -> str:
    """Split any part over `limit` bytes, then renumber."""
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
