#!/usr/bin/env python3
"""Detect topic keywords across chunk JSON files.

Usage:
  python3 detect_topics.py ~/workspace/chunks --words "รัชกาล,สวรรคต,ปืน" --category royal
  python3 detect_topics.py chunk_05.json --words "Fate,Arknights,กาชา" -c gaming --output json
  python3 detect_topics.py ~/workspace/chunks --words "ลา,จบ,ขอบคุณ" --context
"""

import sys, json, os, re
from pathlib import Path


def load_chunks(path):
    """Yield (filename, data) for each chunk JSON at path (file or dir)."""
    p = Path(path)
    if p.is_file():
        with open(p, encoding="utf-8") as f:
            yield p.name, json.load(f)
        return
    for f in sorted(p.iterdir()):
        if f.suffix == ".json":
            with open(f, encoding="utf-8") as fh:
                yield f.name, json.load(fh)


def detect_items(chunks, keywords, context=0):
    """Scan chunks for keywords. Yield (chunk_name, ts, text) per match.

    If context > 0, yield all items from chunks that have any match.
    """
    for name, data in load_chunks(chunks):
        matched_items = []
        for item in data["items"]:
            for kw in keywords:
                if kw in item["text"]:
                    matched_items.append(item)
                    break
        if matched_items:
            if context:
                yield name, data["start_sec"], data["items"][:context]
            else:
                for item in matched_items:
                    yield name, item["timestamp"], item["text"][:80]


def scan_chunks(path, keywords, category=None, context=0, output="table"):
    results = list(detect_items(path, keywords, context))

    if not results:
        print("No matches." if output == "table" else json.dumps([]))
        return

    if output == "json":
        out = []
        for name, ts, text in results:
            if isinstance(text, list):
                for item in text:
                    entry = {"chunk": name, "timestamp": item.get("timestamp", ""), "text": item.get("text", "").strip()}
                    if category:
                        entry["category"] = category
                    out.append(entry)
            else:
                entry = {"chunk": name, "timestamp": ts, "text": text.strip()}
                if category:
                    entry["category"] = category
                out.append(entry)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if output == "compact":
        counts = {}
        for name, ts, text in results:
            counts[name] = counts.get(name, 0) + (len(text) if isinstance(text, list) else 1)
        for name in sorted(counts):
            print(f"{name}: {counts[name]} matches")
        return

    # table
    sep = f"{'Chunk':12} {'Time':>10}  Text"
    print(sep)
    print("-" * len(sep))
    for name, ts, text in results:
        if isinstance(text, list):
            m, s = divmod(ts, 60)
            label = f"{m//60:02d}:{m%60:02d}:{s:02d}"
            print(f"{name:12} {label:>10}  -- {len(text)} items (use --context 0 for matches)")
        else:
            short = text.strip().replace("\n", " ")
            print(f"{name:12} {str(ts):>10}  {short}")


def main():
    import argparse
    ap = argparse.ArgumentParser(
        prog="detect_topics",
        description="Scan chunk JSONs (from prepare_video.py) for topic keywords. "
                    "Returns file + timestamp for each match.",
        epilog="Examples:\n"
               "  %(prog)s chunks/ -w \"รัชกาล,สวรรคต,ปืน\" -c royal\n"
               "  %(prog)s chunk_05.json -w \"Fate,Arknights,กาชา\" -o json\n"
               "  %(prog)s chunks/ -w \"ลา,จบ\" -o compact\n"
               "  %(prog)s chunks/ -w \"สลับปืน\" --context 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("path",
                    help="Chunk JSON file or directory (from prepare_video.py output)")
    ap.add_argument("-w", "--words", required=True,
                    help="Comma-separated keywords to search for. Substring match (not regex). "
                         "Example: --words \"Fate,Grand Order,Arknights\"")
    ap.add_argument("-c", "--category",
                    help="Label attached to every match (e.g. 'royal', 'gaming', 'talk'). "
                         "Only shows in JSON output.")
    ap.add_argument("--context", type=int, default=0,
                    help="Show first N transcript items from matched chunks instead of "
                         "individual keyword hits. Useful for understanding chunk content.")
    ap.add_argument("-o", "--output", choices=["table", "json", "compact"], default="table",
                    help="table  = chunk + timestamp + matching text (default)\n"
                         "json   = array of {chunk, timestamp, text[, category]}\n"
                         "compact = just match counts per chunk")
    args = ap.parse_args()

    keywords = [w.strip() for w in args.words.split(",") if w.strip()]
    if not keywords:
        print("No keywords provided.", file=sys.stderr)
        sys.exit(64)

    try:
        scan_chunks(args.path, keywords, args.category, args.context, args.output)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
