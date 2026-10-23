#!/usr/bin/env python3
"""Detect topic signals in transcript chunks by matching against knowledge.json entries.

CLI runner powered by shared lib/anibon/signal_detector.py and lib/anibon/chunk_io.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from chunk.chunk_io import (
    load_chunk_json,
    load_chunk_xml,
    load_chunks,
)
from process.signals.detector import (
    _process_single_chunk,
    compute_idf_stats,
    load_knowledge,
    match_chunk,
)

__all__ = [
    "_process_single_chunk",
    "compute_idf_stats",
    "load_chunk_json",
    "load_chunk_xml",
    "load_chunks",
    "load_knowledge",
    "match_chunk",
]


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

    chunks_list = list(load_chunks(chunks_path))
    chunks_texts = [chunk_text for _, _, chunk_text in chunks_list]
    idf_stats = compute_idf_stats(chunks_texts, entries)

    results = {}
    total_matched = 0

    workers = min(32, (os.cpu_count() or 1) + 4)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_process_single_chunk, item, entries, idf_stats, len(chunks_list), args.threshold)
            for item in chunks_list
        ]
        for f in futures:
            chunk_name, res, matched = f.result()
            results[chunk_name] = res
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
