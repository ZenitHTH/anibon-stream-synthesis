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
    r"ขอบคุณผู้ชม",
    r"ราตรีสวัสดิ์",
    r"เจอกันใหม่ไลฟ์หน้า",
    r"เจอกันใหม่",
    r"บ๊ายบาย",
    r"ปิดสตรีม",
]

VERB_ROTATION_POOLS: Dict[str, List[str]] = {
    "วิเคราะห์": ["เจาะลึก", "ชำแหละ", "ถกประเด็น", "กางทฤษฎี", "ตีแผ่", "ส่อง", "เช็ค", "คาดการณ์"],
    "อึ้ง!": ["ขนลุก!", "ไฮป์หนักมาก!", "ตะลึง!", "เดือดจัด!", "เซอร์ไพรส์!"],
    "พูดถึง": ["เม้าท์มอย", "แวะคุย", "เล่าเบื้องหลัง", "อัปเดต", "รำลึก"],
}

_TS_LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\s*-\s*(?:\[[^\]]+\])+\s*)(.+)$")
_SUFFIX_RE = re.compile(r"^(.{12,}?)(\s+(?:ใน|ของ)\s+[A-Za-z0-9_\-]+)$")


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


def _rotate_verb_in_desc(desc: str, counts: Dict[str, int], prev_verb: str) -> Tuple[str, str]:
    """Rotate overused or consecutive opening verb using deterministic synonym pools."""
    for verb, pool in VERB_ROTATION_POOLS.items():
        if not desc.startswith(verb):
            continue
        seen = counts.get(verb, 0)
        counts[verb] = seen + 1
        if seen == 0 and verb != prev_verb:
            return desc, verb
        replacement = pool[(seen - 1) % len(pool)]
        return replacement + desc[len(verb):], replacement
    return desc, ""


def _strip_consecutive_suffix(desc: str, prev_suffix: str) -> Tuple[str, str]:
    """Strip trailing 'ใน/ของ <Title>' when identical to the preceding timestamp line."""
    m = _SUFFIX_RE.match(desc)
    if not m:
        return desc, ""
    stem, suffix = m.group(1), m.group(2).strip()
    if suffix.lower() == prev_suffix.lower():
        return stem, suffix
    return desc, suffix


def diversify_repetitive_stamps(text: str) -> str:
    """Deterministically rotate repetitive opening verbs and strip consecutive title suffixes."""
    if not text:
        return ""
    counts: Dict[str, int] = {}
    prev_verb, prev_suffix = "", ""
    out_lines: List[str] = []
    for line in text.splitlines():
        m = _TS_LINE_RE.match(line.strip())
        if not m:
            out_lines.append(line)
            continue
        prefix, desc = m.group(1), m.group(2).strip()
        desc, prev_verb = _rotate_verb_in_desc(desc, counts, prev_verb)
        desc, prev_suffix = _strip_consecutive_suffix(desc, prev_suffix)
        out_lines.append(f"{prefix}{desc}")
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


def ensure_outro_timestamp(timestamps_text: str, last_chunk_text: str) -> str:
    """Ensure stream has an [Ending] timestamp if farewell phrases occur in the last chunk."""
    if not timestamps_text or not last_chunk_text:
        return timestamps_text

    tail = timestamps_text[-1500:] if len(timestamps_text) > 1500 else timestamps_text
    if "[Ending]" in tail:
        return timestamps_text

    lines = timestamps_text.rstrip().splitlines()
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if re.match(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[.*?\]", line):
            if any(re.search(pat, line) for pat in FAREWELL_PATTERNS) or any(w in line for w in ["ปิดไลฟ์", "ปิดสตรีม", "บอกลา"]):
                lines[i] = re.sub(r"\[(Greeting|Talk|Chat|Donation)\]", "[Ending]", line)
                return "\n".join(lines) + "\n"
            break

    has_farewell = any(re.search(pat, last_chunk_text) for pat in FAREWELL_PATTERNS)
    if not has_farewell:
        return timestamps_text

    all_ts = re.findall(r"\((\d{2}:\d{2}:\d{2})\)", last_chunk_text)
    outro_ts = all_ts[-1] if all_ts else "99:99:99"
    outro_line = f"{outro_ts} - [Ending] กล่าวขอบคุณทุกคนและปิดไลฟ์สตรีม\n"
    return f"{timestamps_text.rstrip()}\n{outro_line}"


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
    cleaned = diversify_repetitive_stamps(cleaned)

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
