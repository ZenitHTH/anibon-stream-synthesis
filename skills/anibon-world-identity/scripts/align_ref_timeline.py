"""Align reference video SRT timestamps with stream chunk timestamps.

Usage:
    python3 align_ref_timeline.py ref_story.en.srt /path/to/chunks/ [--output align.json]

Parses reference SRT, extracts character/scene keywords, searches stream chunks
for first occurrence of each keyword, outputs alignment table.
"""

import json, re, sys
from pathlib import Path


def parse_srt(path):
    """Parse SRT file into list of {start_sec, end_sec, text} blocks."""
    raw = Path(path).read_text(encoding='utf-8-sig')
    blocks = re.split(r'\n\n+', raw.strip())
    result = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 3:
            continue
        time_match = re.match(r'(\d{2}):(\d{2}):(\d{2})', lines[1])
        if not time_match:
            continue
        h, m, s = int(time_match[1]), int(time_match[2]), int(time_match[3])
        start_sec = h * 3600 + m * 60 + s
        end_sec = start_sec
        end_match = re.search(r'-->[^0-9]*(\d{2}):(\d{2}):(\d{2})', lines[1])
        if end_match:
            h, m, s = int(end_match[1]), int(end_match[2]), int(end_match[3])
            end_sec = h * 3600 + m * 60 + s
        text = ' '.join(lines[2:]).strip()
        result.append({'start_sec': start_sec, 'end_sec': end_sec, 'text': text})
    return result


def search_chunks(chunks_dir, keywords):
    """Find earliest stream chunk timestamp for each keyword."""
    results = {}
    paths = sorted(Path(chunks_dir).glob('chunk_*.json'))
    if not paths:
        paths = sorted(Path(chunks_dir).glob('*.json'))
    if not paths:
        print(f"[!] No JSON files found in {chunks_dir}", file=sys.stderr)
        return results

    for path in paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        start_sec = data.get('start_sec', 0)
        for seg in data.get('items', []):
            text = seg.get('text', '')
            for kw in keywords:
                if kw not in results and kw.lower() in text.lower():
                    results[kw] = {
                        'stream_sec': start_sec,
                        'stream_time': f"{start_sec//3600:02d}:{(start_sec%3600)//60:02d}:{start_sec%60:02d}",
                        'chunk': path.name
                    }
    return results


BUILTIN_KEYWORDS = [
    'Sparkle', 'Silver Wolf', 'Jing Yuan', 'Yao Guang', 'Aha',
    'Phantasmoon', 'mask', 'Mourning Actor', 'Masked Fool', 'Elation',
    'Pearl', 'IPC', 'Graia', 'Himeko', 'Black Swan', 'Sunday',
    'Welt', 'Robin', 'Xianzhou', 'Yuque', 'Termina',
    'Clockie', 'Mikhail', 'Chandramaya', 'Hanabi', 'Hibana',
]


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Align reference SRT with stream chunks')
    ap.add_argument('srt', help='Reference video SRT file')
    ap.add_argument('chunks', help='Directory of chunk JSON files')
    ap.add_argument('--output', '-o', default='', help='Output JSON file (default: stdout)')
    ap.add_argument('--keywords', '-k', default='',
                    help='Comma-separated keywords (default: builtin HSR list)')
    args = ap.parse_args()

    keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]
    if not keywords:
        keywords = BUILTIN_KEYWORDS

    srt_blocks = parse_srt(args.srt)
    print(f"[*] Parsed {len(srt_blocks)} SRT blocks", file=sys.stderr)

    chunk_hits = search_chunks(args.chunks, keywords)
    print(f"[*] Found {len(chunk_hits)} keyword matches in chunks", file=sys.stderr)

    alignment = []
    for block in srt_blocks:
        matched = []
        for kw in keywords:
            if kw.lower() in block['text'].lower():
                info = chunk_hits.get(kw)
                if info:
                    matched.append({'keyword': kw, **info})
                break
        ref_time = f"{block['start_sec']//3600:02d}:{(block['start_sec']%3600)//60:02d}:{block['start_sec']%60:02d}"
        row = {
            'ref_time': ref_time,
            'ref_sec': block['start_sec'],
            'text_preview': block['text'][:100],
            'matched_keywords': matched,
        }
        alignment.append(row)

    output = {
        'total_srt_blocks': len(srt_blocks),
        'keywords_searched': keywords,
        'matches_found': len(chunk_hits),
        'alignment': alignment,
    }

    if args.output:
        Path(args.output).write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"[*] Written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
