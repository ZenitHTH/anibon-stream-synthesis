#!/usr/bin/env python3
"""Detect topic signals in transcript chunks by matching against knowledge.json entries.

Main idea = rare (low document-frequency) words, not common daily-use words.
Uses corpus-level inverse document frequency over the knowledge-keyword substring hits:

    weight = log(N / df)     # N = chunks, df = chunks containing the word

- High df (word in most chunks)  -> daily/ambient word  -> low weight -> NOT the main idea.
- Low df (word in few chunks)    -> special/distinctive -> high weight -> the main idea + category.

Each chunk gets: ranked `weighted_matched_files`, a `best_file`, `primary_topic`,
and a `confidence` ratio (top file score / total). Hand `best_file` to subagents only
when `confidence` is clear — never glue a knowledge file to a bare substring hit.

# ponytail: pure stdlib local IDF / keyword matching; no Thai tokenizer needed
# (weight computed over the well-defined Keyword set in knowledge.json).
"""

import argparse
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _process_single_chunk(item: tuple, entries: dict, idf_stats: dict, total_chunks: int, threshold: int = 1) -> tuple[str, dict, bool]:
    """Process a single chunk tuple (chunk_name, start_sec, chunk_text).

    Scores each matched knowledge keyword by corpus rarity: rare (low df) terms
    dominate; daily-use (high df) terms are downweighted. Emits a ranked best-file
    and a primary_topic label for subagent routing.
    """
    chunk_name, start_sec, chunk_text = item
    matched, kinds = match_chunk(chunk_text, entries, threshold)
    matched_files = []
    file_weighted = {}
    kind_weighted = {}
    for kw, data in matched.items():
        file = data.get("file")
        count = data["count"]
        stat = idf_stats.get(kw.lower(), {})
        df = stat.get("df", 1)
        weight = stat.get("idf", 0.0)
        if file:
            matched_files.append({
                "keyword": kw, "file": file, "count": count,
                "df": df, "weight": round(weight, 4),
            })
            file_weighted[file] = file_weighted.get(file, 0.0) + count * weight
        kind = data.get("kind", "topic")
        kind_weighted[kind] = kind_weighted.get(kind, 0.0) + count * weight

    weighted_files = sorted(
        ({"file": f, "score": round(s, 4)} for f, s in file_weighted.items()),
        key=lambda x: x["score"], reverse=True,
    )
    total_weighted = sum(file_weighted.values())
    best = weighted_files[0] if weighted_files else None
    confidence = (best["score"] / total_weighted) if best and total_weighted > 0 else 0.0

    top_kind = max(kind_weighted.items(), key=lambda kv: kv[1])[0] if kind_weighted else ""
    primary_topic = ""
    if best:
        stem = Path(best["file"]).stem
        primary_topic = stem.replace("-", " ").replace("_", " ").strip().title()
        if top_kind and top_kind != "topic":
            primary_topic += f" ({top_kind})"

    res = {
        "start_sec": start_sec,
        "matched_keywords": matched,
        "kinds": kinds,
        "signal_score": dict(Counter([data["kind"] for data in matched.values()])),
        "matched_files": matched_files,
        "weighted_matched_files": weighted_files,
        "weighted_signal_score": {k: round(v, 4) for k, v in kind_weighted.items()},
        "best_file": best["file"] if best and best["score"] > 0 else None,
        "primary_topic": primary_topic,
        "confidence": round(confidence, 4),
        "total_chunks": total_chunks,
    }
    return chunk_name, res, bool(matched)


def compute_idf_stats(chunks_texts: list, entries: dict) -> dict:
    """Corpus-level document frequency + inverse-document-frequency per keyword.

    df  = number of chunks containing the keyword (high = daily-use, ambient).
    idf = log(N / df)  -> rare words score high (the interesting ones).
    """
    n = len(chunks_texts)
    df_counts = {kw: 0 for kw in entries}
    for text in chunks_texts:
        tl = text.lower()
        for kw in entries:
            if kw.lower() in tl:
                df_counts[kw] += 1
    stats = {}
    for kw, df in df_counts.items():
        if df <= 0:
            continue
        stats[kw.lower()] = {
            "df": df,
            "idf": round(math.log(n / df), 4),
        }
    return stats


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
