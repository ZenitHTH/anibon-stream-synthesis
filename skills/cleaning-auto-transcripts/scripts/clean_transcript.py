# skills/cleaning-auto-transcripts/scripts/clean_transcript.py
import sys
import json
import re
import argparse
from pathlib import Path

# Add script's directory to python path
sys.path.insert(0, str(Path(__file__).parent))

def format_time(s: float) -> str:
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

def clean_text(text: str, mappings: dict) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    for mapping in mappings.get('mappings', []):
        for pat in mapping.get('patterns', []):
            excludes = mapping.get('exclude_if_contains', [])
            if any(re.search(re.escape(ex), text, re.I) for ex in excludes):
                continue
            text = re.sub(re.escape(pat), lambda m: mapping['correct'], text, flags=re.I)
    return text

def main():
    ap = argparse.ArgumentParser(description="Clean and chunk auto-transcripts.")
    ap.add_argument("input", help="Path to raw_transcript.json")
    ap.add_argument("custom_mappings", nargs="?", help="Optional path to custom mappings JSON")
    ap.add_argument("--chunk", action="store_true", help="Chunk the output")
    ap.add_argument("--chunk-dir", default="chunks", help="Directory for chunks")
    ap.add_argument("--block", type=int, default=900, help="Block size in seconds")
    ap.add_argument("--overlap", type=int, default=60, help="Overlap size in seconds")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    
    # Flatten if json3 format
    from _transcript import _flatten_json3
    items = _flatten_json3(raw) if "events" in raw else raw

    # Load mappings
    if args.custom_mappings:
        map_path = Path(args.custom_mappings)
    else:
        map_path = Path(__file__).parent.parent / "resources" / "default_mappings.json"
    
    mappings = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else {"mappings": []}

    # Clean text
    for item in items:
        item["text"] = clean_text(item["text"], mappings)

    if not args.chunk:
        # Output clean JSON to stdout
        json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
        return

    # Chunking mode
    chunk_dir = Path(args.chunk_dir)
    chunk_dir.mkdir(exist_ok=True)
    total = int(items[-1]['start'] + items[-1].get('duration', 0)) if items else 0
    step = args.block - args.overlap
    idx = 0

    for start in range(0, total, step):
        end = start + args.block
        chunk_items = [x for x in items if start <= x['start'] < end]
        if not chunk_items:
            continue
        path = chunk_dir / f"chunk_{idx:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"start_sec": start, "end_sec": end, "items": chunk_items}, f, ensure_ascii=False, indent=2)
        idx += 1

    print(f"Wrote {idx} chunks to {chunk_dir}", file=sys.stderr)

if __name__ == "__main__":
    main()
