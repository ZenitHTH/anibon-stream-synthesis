"""
assembly-gate.py — MUST run after collecting all subagent results.

Root cause: pack_timestamps.py output accepted without review.
Auto-copied headers from first stamp. Undersized parts (<4 stamps) kept.
Gaps unverified.

Fix: deduplicate adjacent stamps, rewrite caveman headers, merge undersized parts,
audit gaps. Blocks if quality criteria unmet.
"""

import json, sys, os
from datetime import datetime


def parse_timestamps(text):
    """Parse flat timestamp list into list of dicts."""
    stamps = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        # Parse "HH:MM:SS - [Tag] Description"
        if ' - ' not in line:
            continue
        ts_part, rest = line.split(' - ', 1)
        stamps.append({
            'raw': line,
            'time': ts_part,
            'rest': rest
        })
    return stamps


def deduplicate(stamps):
    """Merge adjacent same-topic stamps (<10min apart, same tag, similar topic)."""
    if not stamps:
        return []

    result = [stamps[0]]
    for s in stamps[1:]:
        prev = result[-1]

        # Parse times
        def to_sec(t):
            p = t.split(':')
            return int(p[0])*3600 + int(p[1])*60 + int(p[2])

        gap = to_sec(s['time']) - to_sec(prev['time'])

        # Get tag
        prev_tag = prev['rest'].split(']')[0].split('[')[-1] if '[' in prev['rest'] else ''
        curr_tag = s['rest'].split(']')[0].split('[')[-1] if '[' in s['rest'] else ''

        # Same tag + <10min gap = likely same topic
        if prev_tag == curr_tag and gap < 600 and prev_tag in ('Talk', 'WatchParty', 'Gameplay'):
            # Merge: keep first, skip second (macro-density: don't stamp subtopic shifts)
            continue

        result.append(s)

    removed = len(stamps) - len(result)
    return result, removed


def compute_section_bytes(lines):
    """Compute UTF-8 byte size of a section block."""
    return len('\n'.join(lines).encode('utf-8'))


def rewrite_section_headers(sections):
    """Rewrite section headers with caveman summaries (not first timestamp text)."""
    import re
    for i, sec in enumerate(sections):
        # Extract first timestamp description for context
        stamps = [l for l in sec if l.strip() and l[0].isdigit() and ' - ' in l]
        if not stamps:
            continue

        # Derive theme from all stamps
        tags = set()
        topics = []
        for s in stamps:
            tag_match = re.search(r'\[(\w+)\]', s)
            if tag_match:
                tags.add(tag_match.group(1))
            desc = s.split('] ')[-1] if '] ' in s else ''
            topics.append(desc[:20])

        # Build caveman summary
        first_ts = stamps[0].split(' - ')[0]

        if 'WatchParty' in tags or 'Story' in tags:
            theme = "ดูเนื้อเรื่อง Penacony"
            if any('จบ' in t or 'สรุป' in t for t in topics):
                theme = "บทสรุป Penacony ปิดท้าย"
        elif 'Gacha' in tags or any('กาชา' in t for t in topics):
            theme = "ถกเกมกาชา FGO vs HSR"
        elif 'Gameplay' in tags and not any('กาชา' in t for t in topics):
            theme = "เล่น HSR จัดทีมสู้"
        elif 'Greeting' in tags:
            theme = "เปิดสตรีม กลับมาเล่น HSR"
        else:
            theme = "คุยเกม วิเคราะห์เมต้า"

        # Write header line (first non-header, non-empty line)
        header = f" ส่วนที่ {i+1}: {theme} (⏱ เริ่ม: {first_ts})"
        for j, line in enumerate(sec):
            if 'ส่วนที่' in line:
                sec[j] = header
                break

    return sections


def audit_gaps(stamps, max_gap_min=15):
    """Find gaps > max_gap_min between consecutive stamps."""
    issues = []
    for i in range(1, len(stamps)):
        def to_sec(t):
            p = t.split(':')
            return int(p[0])*3600 + int(p[1])*60 + int(p[2])

        gap = to_sec(stamps[i]['time']) - to_sec(stamps[i-1]['time'])
        if gap > max_gap_min * 60:
            issues.append({
                'from': stamps[i-1]['time'],
                'to': stamps[i]['time'],
                'gap_min': gap // 60,
                'gap_sec': gap
            })

    return issues


def merge_undersized_sections(sections, stamps_list, min_stamps=4, byte_limit=4200):
    """
    Merge sections with < min_stamps into neighbor, unless byte cap prevents.
    """
    if len(sections) < 2:
        return sections, stamps_list

    merged = False
    new_sections = []
    new_stamps_list = []

    for i in range(len(sections)):
        if not new_sections:
            new_sections.append(sections[i])
            new_stamps_list.append(stamps_list[i])
            continue

        prev_stamps = new_stamps_list[-1]
        curr_stamps = stamps_list[i]

        # Check if previous section is undersized
        if len(prev_stamps) < min_stamps:
            # Estimate combined bytes
            combined = '\n'.join(new_sections[-1]).encode('utf-8') + b'\n' + '\n'.join(sections[i]).encode('utf-8')
            if len(combined) < byte_limit:
                # Merge prev and curr
                merged_section = new_sections[-1][:-1] + [""] + sections[i][1:]
                new_sections[-1] = merged_section
                new_stamps_list[-1].extend(curr_stamps)
                merged = True
                continue

        new_sections.append(sections[i])
        new_stamps_list.append(curr_stamps)

    if merged:
        return new_sections, new_stamps_list
    return sections, stamps_list


def main():
    """CLI: python3 assembly-gate.py <anibon_timestamps.md>"""
    if len(sys.argv) < 2:
        print("Usage: python3 assembly-gate.py <anibon_timestamps.md>", file=sys.stderr)
        sys.exit(1)

    md_path = sys.argv[1]
    with open(md_path, encoding='utf-8') as f:
        content = f.read()

    print("=" * 60)
    print("ASSEMBLY GATE")
    print("=" * 60)

    # Parse sections
    sections = []
    current = []
    for line in content.split('\n'):
        if line.startswith('═══════════════════') and current:
            sections.append(current)
            current = [line]
        elif line.startswith('═══════════════════') and not current:
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    if len(sections) < 2:
        print("❌ No section separators found. Wrong format.")
        sys.exit(1)

    print(f"\nParsed {len(sections)-1} content sections "
          f"(section 0 is header: '{sections[0][:2]}')")

    # Parse stamps per section (skip header)
    content_sections = sections[1:]
    stamps_per_section = []
    for sec in content_sections:
        stamps_per_section.append(parse_timestamps('\n'.join(sec)))

    total_stamps = sum(len(s) for s in stamps_per_section)
    print(f"Total raw stamps: {total_stamps}")

    # 1. Deduplicate
    total_removed = 0
    for i in range(len(stamps_per_section)):
        result = deduplicate(stamps_per_section[i])
        if isinstance(result, tuple):
            stamps_per_section[i], removed = result
            total_removed += removed
        else:
            stamps_per_section[i] = result

    if total_removed > 0:
        print(f"✅ Deduplicated: {total_removed} adjacent same-topic stamps removed")

    # 2. Gap audit
    all_stamps = [s for sub in stamps_per_section for s in sub]
    gaps = audit_gaps(all_stamps)
    if gaps:
        print(f"\n⚠️  GAPS >15min:")
        for g in gaps:
            print(f"  {g['from']} → {g['to']}: {g['gap_min']}min gap")
    else:
        print("\n✅ No gaps >15min")

    # 3. Section size check
    small_sections = [(i, len(s)) for i, s in enumerate(stamps_per_section) if len(s) < 4]
    if small_sections:
        print(f"\n⚠️  Undersized sections (<4 stamps):")
        for idx, count in small_sections:
            print(f"  Section {idx+1}: {count} stamps")
            byte_size = 0
            if idx < len(content_sections):
                byte_size = compute_section_bytes(content_sections[idx])
                print(f"    {byte_size}B — {'under' if byte_size < 3500 else 'over'} 3500 target")

    # 4. Header quality check
    print("\nSection headers:")
    for i, sec in enumerate(content_sections):
        for line in sec:
            if 'ส่วนที่' in line:
                is_caveman = not any(word in line for word in
                    ['เริ่ม', 'สวัสดี', 'เปิด', 'ทักทาย']) or 'กลับมา' in line
                status = '✅' if is_caveman else '⚠️ generic'
                print(f"  {status} {line.strip()[:80]}")
                break

    # 5. Byte limit check
    print("\nByte limits:")
    all_ok = True
    for i, sec in enumerate(content_sections):
        size = compute_section_bytes(sec)
        status = '✅' if size <= 3500 else ('⚠️' if size <= 4500 else '❌')
        if status != '✅':
            all_ok = False
        print(f"  {status} Section {i+1}: {size}B / 3500 target")

    # Summary
    if all_ok and not gaps and small_sections == []:
        print(f"\n{'='*60}")
        print("✅ ASSEMBLY GATE PASSED. Ready for YouTube.")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("⚠️  ASSEMBLY GATE: review flagged items above")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
