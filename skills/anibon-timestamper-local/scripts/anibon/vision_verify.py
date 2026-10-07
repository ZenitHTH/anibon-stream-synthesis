"""vision_verify.py — Ambiguous timestamp detection and visual ground truth verification."""

import json
import re
from typing import Optional


DEICTIC = ("คุณนี้", "ตัวนี้", "อันนี้", "นี่น่ะ", "นี้น่ะ")
GENERIC = ("สู้มอนสเตอร์", "ในเกม", "เล่นเกมจนจบ")


def stamp_seconds(stamp: str) -> int:
    """Parse HH:MM:SS from timestamp string and return seconds."""
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})", stamp.strip())
    if not m:
        return 0
    h, m_val, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + m_val * 60 + s


def is_ambiguous(stamp: str) -> bool:
    """Determine if a timestamp description needs visual grounding.

    Criteria:
    1. Contains uncertainty marker '[?]'
    2. Description length after '] ' is under 20 characters
    3. Contains deictic pronouns ('คุณนี้', 'ตัวนี้', etc.)
    4. Contains generic gameplay phrases without an identifiable English proper noun (>= 4 chars)
    """
    if "[?]" in stamp:
        return True

    # Extract description after tag: 'HH:MM:SS - [Tag] Description'
    m = re.search(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]\s*(.*)$", stamp.strip())
    if not m:
        return False

    desc = m.group(3).strip()
    if len(desc) < 20:
        return True

    for word in DEICTIC:
        if word in desc:
            return True

    for phrase in GENERIC:
        if phrase in desc:
            # Check if there is an identifiable English entity (>= 4 letters)
            if not re.search(r"[A-Za-z]{4,}", desc):
                return True

    return False


def build_verify_prompt(stamp: str, context: str = "") -> str:
    """Build a prompt asking the vision model to inspect the frame and verify/disambiguate the timestamp."""
    m = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]\s*(.*)$", stamp.strip())
    ts = m.group(1) if m else "00:00:00"
    tag = m.group(2) if m else "Talk"
    desc = m.group(3) if m else stamp

    ctx_block = f"\nContext Transcript around this moment:\n{context}\n" if context else ""

    return f"""Inspect this screenshot from an Anibon livestream at timestamp {ts}.
Original draft timestamp line:
{ts} - [{tag}] {desc}
{ctx_block}
Task:
1. Examine what is literally visible on screen (game title, character/hero names, UI elements, website, steam chart, article, or video).
2. If the draft description is vague, misheard, or phonetically garbled (e.g. 'ตัวละครใหม่' -> 'Acheron ใน Honkai: Star Rail'), correct the entity name accurately in Thai.
3. Keep the EXACT same timestamp '{ts}' and tag '[{tag}]'. Only refine the description text following '[{tag}] '.
4. Never report hyperbolic roasts as literal depiction.
5. Return JSON ONLY in this format:
{{
  "corrected": "{ts} - [{tag}] <accurate Thai description>",
  "confidence": <float between 0.0 and 1.0>
}}"""


def parse_verify_response(raw: str, original: str, min_conf: float = 0.6) -> str:
    """Parse JSON response from vision model and validate constraints.

    Must keep identical HH:MM:SS and [Tag], and meet minimum confidence.
    Returns corrected string if valid, otherwise original.
    """
    if not raw or not isinstance(raw, str):
        return original

    jm = re.search(r"(\{.*\})", raw, re.DOTALL)
    if not jm:
        return original

    try:
        data = json.loads(jm.group(1))
    except Exception:
        return original

    corrected = data.get("corrected")
    if not corrected or not isinstance(corrected, str):
        return original

    try:
        confidence = float(data.get("confidence", 0.0))
    except (ValueError, TypeError):
        return original

    if confidence < min_conf:
        return original

    # Validate that HH:MM:SS and [Tag] are preserved exactly
    m_orig = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]", original.strip())
    m_corr = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]", corrected.strip())

    if not m_orig or not m_corr:
        return original

    if m_orig.group(1) != m_corr.group(1):
        # Timestamp changed
        return original

    if m_orig.group(2).strip().lower() != m_corr.group(2).strip().lower():
        # Tag changed
        return original

    return corrected.strip()
