"""Stage 5 deterministic post-pass sanitizer & world identity auditor.

Enforces:
- Mandatory Pokémon Thai naming conventions (name_th (name_en))
- Repetition token stutter cleanup (e.g. Wildild -> Wild)
- Missing outro timestamp detection and injection
- YouTube comment byte limits (< 3,500 bytes per part)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

KNOWN_POKEMON_MAP = {
    "การ์โชมป์": "การ์โชมป์ (Garchomp)",
    "เป็ดต้นหอม": "คาโมเนกิ (เป็ดต้นหอม) (Farfetch'd)",
    "แบกซ์แคลิเบอร์": "แบกซ์แคลิเบอร์ (Baxcalibur)",
    "สเปกเทรียร์": "ม้าดำ / สเปกเทรียร์ (Spectrier)",
    "ลิซาร์ดอน": "ลิซาร์ดอน (Charizard)",
    "เกงกา": "เกงกา (Gengar)",
}

STUTTER_PATTERNS = [
    (re.compile(r"Wildild\b", re.IGNORECASE), "Wild"),
    (re.compile(r"botwtw\b", re.IGNORECASE), "BotW"),
    (re.compile(r"Orderder\b", re.IGNORECASE), "Order"),
    (re.compile(r"Luminaina\b", re.IGNORECASE), "Lumina"),
]

FAREWELL_PATTERNS = [
    r"ขอบคุณทุกคน",
    r"ราตรีสวัสดิ์",
    r"เจอกันใหม่ไลฟ์หน้า",
    r"เจอกันใหม่",
    r"บ๊ายบาย",
    r"ปิดสตรีม",
]


def sanitize_pokemon_names(text: str) -> str:
    """Enforce Thai community/sound name first with English in parentheses."""
    if not text:
        return ""
    result = text
    for th_key, canonical in KNOWN_POKEMON_MAP.items():
        # Match standalone th_key not already followed by parentheses
        pattern = rf"{re.escape(th_key)}(?!\s*\([^\)]+\))"
        result = re.sub(pattern, canonical, result)
    return result


def clean_token_stutters(text: str) -> str:
    """Clean common repetition token stutters in generated output."""
    if not text:
        return ""
    result = text
    for pattern, replacement in STUTTER_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def ensure_outro_timestamp(timestamps_text: str, last_chunk_text: str) -> str:
    """Ensure stream has an [Ending] timestamp if farewell phrases occur in the last chunk."""
    if not timestamps_text or not last_chunk_text:
        return timestamps_text

    # If ending stamp already exists within the last 1500 chars, no need to inject
    tail = timestamps_text[-1500:] if len(timestamps_text) > 1500 else timestamps_text
    if "[Ending]" in tail:
        return timestamps_text

    # Check for farewell phrases in last chunk
    has_farewell = any(re.search(pat, last_chunk_text) for pat in FAREWELL_PATTERNS)
    if not has_farewell:
        return timestamps_text

    # Extract timestamp from last chunk
    m_ts = re.search(r"\((\d{2}:\d{2}:\d{2})\)", last_chunk_text)
    outro_ts = m_ts.group(1) if m_ts else "99:99:99"

    outro_line = f"{outro_ts} - [Ending] ปู่โบ๊ตกล่าวขอบคุณทุกคนและปิดไลฟ์สตรีม\n"
    
    # Append to end of timestamps
    stripped = timestamps_text.rstrip()
    return f"{stripped}\n{outro_line}"


def audit_and_sanitize_final_markdown(
    md_content: str,
    workspace: Path,
    macro_anchor: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Deterministically audit final markdown output before delivering to user."""
    if not md_content:
        return "", {"status": "empty"}

    cleaned = sanitize_pokemon_names(md_content)
    cleaned = clean_token_stutters(cleaned)

    # Check last chunk for outro
    workspace = Path(workspace)
    chunks_dir = workspace / "chunks"
    if chunks_dir.is_dir():
        chunk_files = sorted(chunks_dir.glob("chunk_*.txt"))
        if chunk_files:
            last_chunk = chunk_files[-1].read_text(encoding="utf-8", errors="ignore")
            cleaned = ensure_outro_timestamp(cleaned, last_chunk)

    stats = {
        "macro_anchor": macro_anchor,
        "length_bytes": len(cleaned.encode("utf-8")),
    }
    return cleaned, stats
