import sys, json, re
from pathlib import Path

# ponytail: single entry-point for the full pipeline (flatten json3 → clean → optionally chunk)
# Ceiling: no streaming; loads full transcript into memory (~few MB). Upgrade: ijson if RAM is tight.

def _flatten_json3(raw):
    """Convert yt-dlp json3 format to flat [{text, start, duration}] list."""
    events = raw.get("events", [])
    items = []
    for e in events:
        if "segs" not in e:
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).strip()
        if text:
            items.append({"text": text, "start": e.get("tStartMs", 0) / 1000.0,
                          "duration": e.get("dDurationMs", 0) / 1000.0})
    items.sort(key=lambda x: x["start"])
    return items

def _load(path):
    raw = json.load(open(path, encoding="utf-8"))
    # Auto-detect json3 by presence of 'events' key
    return _flatten_json3(raw) if "events" in raw else raw

def clean_transcript_data(transcript, mappings):
    for item in transcript:
        text = re.sub(r'\s+', ' ', item['text']).strip()
        for mapping in mappings.get('mappings', []):
            for pat in mapping.get('patterns', []):
                if any(re.search(re.escape(ex), text, re.I) for ex in mapping.get('exclude_if_contains', [])): continue
                text = re.sub(re.escape(pat), mapping['correct'], text, flags=re.I)
        item['text'] = text
    return transcript



def get_mapreduce_chunks(transcript, block_sec=900, overlap_sec=60):
    """Yields (start_sec, end_sec, text) tuples for MapReduce subagents."""
    total = int(transcript[-1]['start'] + transcript[-1]['duration'])
    step = block_sec - overlap_sec
    for start in range(0, total, step):
        end = start + block_sec
        text = " ".join(f"({int(i['start']//3600):02d}:{int((i['start']%3600)//60):02d}:{int(i['start']%60):02d}) {i['text'].strip()}"
                        for i in transcript if start <= i['start'] < end)
        if text:
            yield start, end, text

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Raw json3 or flat transcript JSON")
    ap.add_argument("mappings", nargs="?", help="Custom mappings JSON (optional)")
    ap.add_argument("--chunk", action="store_true", help="Output chunks dir instead of cleaned JSON")
    ap.add_argument("--chunk-dir", default="chunks", help="Output directory for chunk files")
    ap.add_argument("--block", type=int, default=900, help="Chunk block size in seconds (default 900)")
    ap.add_argument("--overlap", type=int, default=60, help="Chunk overlap in seconds (default 60)")
    args = ap.parse_args()

    transcript = _load(args.input)
    map_file = args.mappings or str(Path(__file__).parent.parent / "resources" / "default_mappings.json")
    mappings = json.load(open(map_file, encoding="utf-8"))
    cleaned = clean_transcript_data(transcript, mappings)

    if args.chunk:
        import os
        os.makedirs(args.chunk_dir, exist_ok=True)
        for i, (s, e, _) in enumerate(get_mapreduce_chunks(cleaned, args.block, args.overlap)):
            items = [x for x in cleaned if s <= x['start'] < e]
            with open(f"{args.chunk_dir}/chunk_{i:02d}.json", "w", encoding="utf-8") as f:
                json.dump({"start_sec": s, "end_sec": e, "items": items}, f, ensure_ascii=False, indent=2)
        print(f"Wrote {i+1} chunks to {args.chunk_dir}/", file=sys.stderr)
    else:
        print(json.dumps(cleaned, ensure_ascii=False, indent=2))
