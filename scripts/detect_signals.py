#!/usr/bin/env python3
"""Zero-maintenance TF-IDF signal detection for chunk workspaces.

No hardcoded term databases. Pure frequency-based detection.
Adapts to any workspace automatically.

Usage:
  python3 detect_signals.py /path/to/chunks                # table output
  python3 detect_signals.py /path/to/chunks --output json
  python3 detect_signals.py /path/to/chunks --chunk chunk_28 --output block
  python3 detect_signals.py /path/to/chunks --match-knowledge
"""

import json, math, sys, argparse
from pathlib import Path
from collections import Counter

THAI_PARTICLES = {
    "ครับ","นะครับ","ครับผม","คะ","ค่ะ","จ้า","นะ","สิ","ซิ",
    "ละ","ล่ะ","หรอ","รึ","มั้ย","ใช่","ไม่","ได้","เลย","แล้ว",
    "อีก","ยัง","ก็","จะ","คง","นะคะ","ฮะ","เว้ย","วะ","ดิ",
    "อ่ะ","นะฮะ","จ้ะ","น้า","นะจ๊ะ","มั้ง","นะครับผม",
    "เป็น","มี","อยู่","คือ","ให้","มา","ไป","ทำ","พูด","บอก",
    "ดู","รู้","คิด","เห็น","เอา","ใส่","ออก","เข้า","ขึ้น",
    "ลง","ไว้","เออ","อือ","อ่า","โอเค",
}

def tokenize(text):
    text = text.replace("\n"," ").replace("\t"," ")
    return [t for t in text.split() if t.strip() and t not in THAI_PARTICLES]

def load_chunks(path):
    p = Path(path)
    if p.is_file():
        with open(p, encoding="utf-8") as f:
            yield p.name, json.load(f)
        return
    for fp in sorted(p.iterdir()):
        if fp.suffix == ".json":
            with open(fp, encoding="utf-8") as f:
                yield fp.name, json.load(f)

def build_corpus(path):
    corpus = []
    for name, data in load_chunks(path):
        texts = [i["text"] for i in data.get("items",[]) if i.get("text","").strip()]
        toks = tokenize(" ".join(texts))
        corpus.append({
            "name": name,
            "tokens": toks,
            "total": len(toks),
            "items": data.get("items",[]),
            "start_sec": data.get("start_sec", 0),
        })
    return corpus

def compute_idf(corpus):
    total = len(corpus)
    df = Counter()
    for doc in corpus:
        for t in set(doc["tokens"]):
            df[t] += 1
    return {t: math.log(total / (1 + c)) for t, c in df.items()}

def chunk_signals(tokens, idf, top_n=8):
    tf = Counter(tokens)
    total = len(tokens) or 1
    scored = [(t, (c/total) * idf.get(t, 0)) for t, c in tf.items() if idf.get(t, 0) > 1.0]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]

def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0

def split_signal(items, idf, top_n=8, jaccard_threshold=0.2):
    n = len(items)
    if n < 6:
        toks = [t for it in items for t in tokenize(it.get("text",""))]
        sig = chunk_signals(toks, idf, top_n)
        return [("full", sig)] if sig else [("silent", [])]

    thirds = [items[:n//3], items[n//3:2*n//3], items[2*n//3:]]
    sigs = []
    for group in thirds:
        toks = [t for it in group for t in tokenize(it.get("text",""))]
        sigs.append(set(t for t,_ in chunk_signals(toks, idf, top_n)))

    if jaccard(sigs[0], sigs[1]) < jaccard_threshold or jaccard(sigs[1], sigs[2]) < jaccard_threshold:
        merged = []
        for i, group in enumerate(thirds):
            toks = [t for it in group for t in tokenize(it.get("text",""))]
            sig = chunk_signals(toks, idf, top_n)
            if sig:
                merged.append((["start","mid","end"][i], sig))
        return merged if merged else [("silent", [])]

    toks = [t for it in items for t in tokenize(it.get("text",""))]
    sig = chunk_signals(toks, idf, top_n)
    return [("full", sig)] if sig else [("silent", [])]

def match_knowledge(terms, ref_dirs):
    matched = []
    seen = set()
    for term, _ in terms:
        if len(term) < 3:
            continue
        for rd in ref_dirs:
            rd = Path(rd)
            if not rd.exists():
                continue
            for fp in sorted(rd.rglob("*.md")):
                if fp.stem.lower() in term.lower() or term.lower() in fp.stem.lower():
                    try:
                        rel = str(fp.relative_to(rd))
                    except ValueError:
                        rel = fp.name
                    if rel not in seen:
                        matched.append(rel)
                        seen.add(rel)
    return matched[:8]

def output_table(corpus, idf, top_n=8, jt=0.2):
    for doc in corpus:
        segments = split_signal(doc["items"], idf, top_n, jt)
        labels = ", ".join(f"[{l}] {' '.join(t for t,_ in s[:4])}" for l, s in segments if s)
        print(f"{doc['name']:12} ({doc['total']:4d}tok) {labels}")

def output_json(corpus, idf, knowledge_dirs=None, top_n=8, jt=0.2):
    results = []
    for doc in corpus:
        segments = split_signal(doc["items"], idf, top_n, jt)
        segs_out = []
        all_terms = []
        for label, sig in segments:
            terms = [{"term": t, "score": round(s, 4)} for t, s in sig]
            segs_out.append({"label": label, "terms": terms})
            all_terms.extend(terms)
        entry = {
            "name": doc["name"],
            "tokens": doc["total"],
            "segments": segs_out,
        }
        if knowledge_dirs:
            entry["knowledge"] = match_knowledge([(t["term"], t["score"]) for t in all_terms], knowledge_dirs)
        results.append(entry)
    print(json.dumps(results, ensure_ascii=False, indent=2))

def output_block(doc, idf, knowledge_dirs=None, top_n=8, jt=0.2):
    segments = split_signal(doc["items"], idf, top_n, jt)
    print("[DETECTION SIGNAL]")
    print(f"chunk: {Path(doc['name']).stem}")
    print(f"tokens: {doc['total']}")
    all_terms = []
    for label, sig in segments:
        terms_str = ", ".join(f"{t}({s:.3f})" for t, s in sig)
        print(f"  {label}: {terms_str}")
        all_terms.extend([(t, s) for t, s in sig])
    if knowledge_dirs:
        matched = match_knowledge(all_terms, knowledge_dirs)
        if matched:
            print(f"knowledge:")
            for m in matched:
                print(f"  - {m}")
    print()

def main():
    ap = argparse.ArgumentParser(
        prog="detect_signals",
        description="TF-IDF signal detection for chunk workspaces. No hardcoded terms.",
        epilog="Examples:\n"
               "  %(prog)s chunks/\n"
               "  %(prog)s chunks/ --output json\n"
               "  %(prog)s chunks/ --chunk chunk_28.json --output block\n"
               "  %(prog)s chunks/ --match-knowledge skills/ references/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("path", help="Chunk JSON file or directory")
    ap.add_argument("--output", choices=["table", "json", "block"], default="table",
                    help="output format (default: table)")
    ap.add_argument("--chunk", help="Filter to single chunk (filename or index)")
    ap.add_argument("--match-knowledge", nargs="*", default=None,
                    help="Knowledge dirs to scan for matching reference files")
    ap.add_argument("--top-n", type=int, default=8,
                    help="Number of top terms per signal (default: 8)")
    ap.add_argument("--jaccard-threshold", type=float, default=0.2,
                    help="Sub-chunk split threshold (default: 0.2)")
    args = ap.parse_args()

    corpus = build_corpus(args.path)
    if not corpus:
        print("No chunks found.", file=sys.stderr)
        sys.exit(1)

    idf = compute_idf(corpus)

    if args.chunk:
        corpus = [d for d in corpus if args.chunk in d["name"] or args.chunk in str(d.get("start_sec",""))]
        if not corpus:
            print(f"Chunk '{args.chunk}' not found.", file=sys.stderr)
            sys.exit(1)

    if args.output == "table":
        output_table(corpus, idf, args.top_n, args.jaccard_threshold)
    elif args.output == "json":
        output_json(corpus, idf, args.match_knowledge, args.top_n, args.jaccard_threshold)
    elif args.output == "block":
        for doc in corpus:
            output_block(doc, idf, args.match_knowledge, args.top_n, args.jaccard_threshold)

if __name__ == "__main__":
    main()
