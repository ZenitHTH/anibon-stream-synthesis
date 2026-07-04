import re
import argparse
import sys

def parse_time(ts_str):
    parts = list(map(int, ts_str.split(":")))
    return parts[0]*3600 + parts[1]*60 + parts[2] if len(parts) == 3 else 0

def merge_logic(file_paths):
    merged = []
    pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})\s*(?:-\s*)?(?:\[(.*?)\])?\s*(.*)$')
    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    match = pattern.match(line)
                    if match:
                        ts, tag, desc = match.groups()
                        tag_str = f"[{tag}] " if tag else "[Talk] "
                        seconds = parse_time(ts)
                        merged.append({"sec": seconds, "line": f"{ts} - {tag_str}{desc}"})
        except FileNotFoundError:
            print(f"Warning: {fp} not found", file=sys.stderr)
            
    merged.sort(key=lambda x: x["sec"])
    # Deduplicate using dict insertion order (Ponytail principle)
    deduped = list({e["line"]: None for e in merged}.keys())
    return deduped

def main():
    parser = argparse.ArgumentParser(description="Merge and sort timestamps.")
    parser.add_argument("inputs", nargs="+", help="Input text files")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    results = merge_logic(args.inputs)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(results) + "\n")
    else:
        for r in results:
            print(r)

if __name__ == "__main__":
    main()
