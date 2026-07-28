#!/usr/bin/env python3
"""Validate timestamp tags against description content. Retag misclassified entries.

Usage:
    python validate_tags.py all_timestamps.txt -o validated_timestamps.txt

Tag rules (Thai keywords → expected tag):
    Boss keywords  → [Boss]     (สู้บอส, บอส, boss, ไฟต์บอส, ตีบอส, boss fight)
    Death keywords → [Death]    (ตาย, death, ตายแล้ว, โมง, wipe, party wipe)
    Victory kw     → [Victory]  (เคลียร์, ชนะ, จบ, clear, victory, ผ่าน, สำเร็จ)
    Gacha kw       → [Gacha]    (กาชา, gacha, สุ่ม, จิ้ม, summon, 10 โรล, multi)
    Chat kw        → [Chat]     (ในแชท, แชทบอก, chat, แชท, คุณ...บอก)
    Reaction kw    → [Reaction] (ดูคลิป, reaction, watch, trailer, ตัวอย่าง)
    News kw        → [News]     (ข่าว, news, อัปเดต, update, ประกาศ, announce)

If description matches NEW rule but tag is different → retag.
If description matches NO rule → keep original tag.
"""
import re
import sys
import argparse
from pathlib import Path

# ── Tag rules: (pattern, target_tag, priority) ──────────────────
# Priority: higher number = checked first (avoid false matches)
TAG_RULES = [
    # Victory / clear boss (compound before bare "บอส")
    (r"เคลียร์.*บอส|เคลีย.*บอส|ผ่าน.*บอส|ชนะ.*บอส|บอส.*เคลียร์|บอส.*เคลีย", "[Victory]", 95),
    # Death
    (r"ตาย\s*(แล้ว|หมด|ทั้ง|หมู่|กัน|ทั้งทีม)?|death|wipe|party\s*wipe|โมง|ล้ม|ตายหมด", "[Death]", 85),
    # Victory / clear (general)
    (r"เคลียร์|เคลีย|ชนะ|clear|ผ่าน\s*(แล้ว|ได้)|สำเร็จ|victory|จบ\s*(แล้ว)?|เสร็จ", "[Victory]", 80),
    # Boss
    (r"บอส|boss\s*fight|สู้บอส|ตีบอส|ไฟต์บอส|เจอบอส|บอสตัว", "[Boss]", 70),
    # Gacha
    (r"กาชา|gacha|สุ่ม|จิ้ม|summon|10\s*โรล|multi|วอช|ประกัน|ssr|เกาชา|ดึง", "[Gacha]", 60),
    # Chat (speaker reading chat)
    (r"ในแชท|แชทบอก|chat\s*(บอก|ว่า)|คุณ.*บอกว่า|คนดูบอก", "[Chat]", 55),
    # Donation
    (r"donation|super.?chat|ซุปฯ|sup.?chat|ขอบคุณ.*(ครับ|คะ).*donate", "[Donation]", 50),
    # Reaction (watching external media)
    (r"ดูคลิป|reaction|watch|trailer|ตัวอย่าง|ดูวิดีโอ|ดูclip|ดู(ยูทูป|youtube|คลิป)", "[Reaction]", 45),
    # News
    (r"ข่าว|news|อัปเดต|update|ประกาศ|announce|พาดพิง|ล่าสุด", "[News]", 40),
]

# ── False-positive patterns: if these are present, DO NOT retag ──
FALSE_POSITIVE_BLOCK = [
    # "บอส" can appear in non-boss contexts
    (r"พูดถึงบอส|บอสว่า|บอส(พูด|บอก|คุย)", "[Boss]"),
    (r"เกียวตาย|อัตราตาย|ตาย(ตัว|ครั้ง)", "[Death]"),
    # "กาชา" in "talking about gacha games" context, not pulling
    (r"คุยเรื่อง.*กาชา|พูดถึง.*กาชา|เกม.*กาชา|เกมมือถือ.*กาชา", "[Gacha]"),
    # "อัปเดต" in greeting context, not news
    (r"เปิดไลฟ์.*อัปเดต|ทักทาย.*อัปเดต", "[News]"),
    # "donation" mentioned in passing, not a donate event
    (r"และอ่าน.*donation|และ.*donation|donation.*และ", "[Donation]"),
]

LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*-\s*(\[.*?\])\s+(.*)$")


def parse_line(line: str):
    """Parse timestamp line → (time_str, tag, desc) or None."""
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def check_false_positive(desc: str, tag: str) -> bool:
    """Return True if desc has a false-positive pattern that blocks retag to tag."""
    desc_lower = desc.lower()
    for pattern, target in FALSE_POSITIVE_BLOCK:
        if re.search(pattern, desc_lower) and target == tag:
            return True
    return False


def suggest_retag(desc: str, current_tag: str):
    """Suggest corrected tag based on description keywords.
    
    Returns (new_tag | None, rule_name | None).
    None = keep original tag.
    """
    desc_lower = desc.lower()
    
    # Sort rules by priority (descending)
    sorted_rules = sorted(TAG_RULES, key=lambda r: -r[2])
    
    matches = []
    for pattern, target_tag, priority in sorted_rules:
        if re.search(pattern, desc_lower):
            matches.append((target_tag, priority))
    
    if not matches:
        return None, None
    
    # Take highest-priority match
    best_tag, _ = max(matches, key=lambda m: m[1])
    
    # Check false positives against BEST MATCHING tag (not current_tag)
    if check_false_positive(desc, best_tag):
        return None, None
    
    if best_tag == current_tag:
        return None, None  # already correct
    
    return best_tag, f"retag: {current_tag} → {best_tag}"


def validate_file(input_path: Path, output_path: Path):
    """Validate all timestamps in a file, write corrected version."""
    lines = input_path.read_text(encoding="utf-8").splitlines()
    
    corrected = []
    stats = {"total": 0, "changed": 0, "unchanged": 0, "skipped": 0}
    changes = []
    
    for i, line in enumerate(lines):
        parsed = parse_line(line)
        if not parsed:
            corrected.append(line)  # pass through unparseable lines
            stats["skipped"] += 1
            continue
        
        time_str, tag, desc = parsed
        stats["total"] += 1
        
        result = suggest_retag(desc, tag)
        if result[0]:
            new_tag, reason = result
            new_line = f"{time_str} - {new_tag} {desc}"
            corrected.append(new_line)
            stats["changed"] += 1
            changes.append(f"  {time_str} {reason}: {desc[:50]}")
        else:
            corrected.append(line)
            stats["unchanged"] += 1
    
    # Write output
    output_path.write_text("\n".join(corrected) + "\n", encoding="utf-8")
    
    # Report
    print(f"[*] Validated {stats['total']} timestamps:", file=sys.stderr)
    print(f"    Changed: {stats['changed']}", file=sys.stderr)
    print(f"    Unchanged: {stats['unchanged']}", file=sys.stderr)
    print(f"    Skipped: {stats['skipped']}", file=sys.stderr)
    if changes:
        print(f"[*] Changes:", file=sys.stderr)
        for c in changes:
            print(c, file=sys.stderr)
    print(f"[*] Output → {output_path}", file=sys.stderr)
    
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Validate timestamp tags against description content.")
    ap.add_argument("input", type=Path, help="Input timestamp file")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Output path (default: input_stem_validated.txt)")
    ap.add_argument("--report", action="store_true",
                    help="Only report issues, don't write")
    args = ap.parse_args()
    
    if not args.input.exists():
        print(f"[!] File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    output = args.output or args.input.parent / f"{args.input.stem}_validated.txt"
    
    stats = validate_file(args.input, output)
    
    if stats["changed"] == 0 and stats["total"] > 0:
        print("[*] All tags correct. No changes needed.", file=sys.stderr)


if __name__ == "__main__":
    main()
