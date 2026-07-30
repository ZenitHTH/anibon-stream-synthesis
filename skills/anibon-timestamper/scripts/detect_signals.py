#!/usr/bin/env python3
"""Detect topic signals in transcript chunks by matching against knowledge.json entries.

# ponytail: pure stdlib local TF-IDF / keyword matching; removed web discovery & side-effecting git commits.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def load_knowledge(path: Path) -> dict:
    """Load knowledge.json entries."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", {})


def load_chunk_json(path: Path):
    """Load a single JSON chunk. Returns (name, start_sec, full_text)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    texts = [it.get("text", "").strip() for it in data.get("items", []) if it.get("text")]
    return path.stem, data.get("start_sec", 0), " ".join(texts)


def load_chunk_xml(path: Path):
    """Load a single XML chunk. Returns (name, start_sec, full_text)."""
    tree = ET.parse(path)
    root = tree.getroot()
    texts = [(item.text or "").strip() for item in root.iter("item") if item.text]
    start_sec = int(root.get("start_sec", 0))
    return path.stem, start_sec, " ".join(texts)


def load_chunks(path: Path):
    """Yield (name, start_sec, full_text) for each chunk."""
    p = Path(path)
    if p.is_file():
        yield load_chunk_xml(p) if p.suffix == ".xml" else load_chunk_json(p)
        return

    def sort_key(f):
        try:
            return int(f.stem.split("_")[-1])
        except (ValueError, IndexError):
            return 0

    candidates = sorted(p.glob("chunk_*.json"), key=sort_key)
    fmt = "json"
    if not candidates:
        candidates = sorted(p.glob("chunk_*.xml"), key=sort_key)
        fmt = "xml"

    loader = load_chunk_xml if fmt == "xml" else load_chunk_json
    for f in candidates:
        yield loader(f)


def match_chunk(chunk_text: str, entries: dict, threshold: int = 1):
    """Match chunk text against knowledge entries."""
    matched = {}
    matched_kinds = set()
    text_lower = chunk_text.lower()

    for keyword, info in entries.items():
        kw_lower = keyword.lower()
        count = text_lower.count(kw_lower)
        if count >= threshold:
            kind = info.get("kind", "topic")
            target_file = info.get("file")
            matched_kinds.add(kind)
            matched[keyword] = {
                "count": count,
                "kind": kind,
                "file": target_file
            }

    return matched, list(matched_kinds)


def main():
    parser = argparse.ArgumentParser(description="Match transcript chunks against knowledge.json entries.")
    parser.add_argument("--chunks", required=True, help="Path to chunks directory or single file")
    parser.add_argument("--knowledge", required=True, help="Path to knowledge.json")
    parser.add_argument("--output", default="-", help="Output path for signals.json ('-' for stdout)")
    parser.add_argument("--threshold", type=int, default=1, help="Minimum keyword occurrences to match")
    args = parser.parse_args()

    knowledge_path = Path(args.knowledge).expanduser().resolve()
    chunks_path = Path(args.chunks).expanduser().resolve()

    if not knowledge_path.exists():
        print(f"Error: knowledge.json not found at {knowledge_path}", file=sys.stderr)
        sys.exit(1)

    entries = load_knowledge(knowledge_path)

    results = {}
    total_matched = 0
    chunks_list = list(load_chunks(chunks_path))

    for chunk_name, start_sec, chunk_text in chunks_list:
        matched, kinds = match_chunk(chunk_text, entries, args.threshold)
        matched_files = [
            {"keyword": kw, "file": data["file"], "count": data["count"]}
            for kw, data in matched.items() if data.get("file")
        ]
        signal_scores = Counter([data["kind"] for data in matched.values()])

        results[chunk_name] = {
            "start_sec": start_sec,
            "matched_keywords": matched,
            "kinds": kinds,
            "signal_score": dict(signal_scores),
            "matched_files": matched_files
        }
        if matched:
            total_matched += 1

    output = {
        "chunks_processed": len(chunks_list),
        "chunks_with_signals": total_matched,
        "chunks": results
    }

    if args.output == "-":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Wrote signals to {out_path} ({total_matched}/{len(chunks_list)} chunks matched)", file=sys.stderr)


if __name__ == "__main__":
    main()
