import json
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Fallback to local _transcript path if needed
try:
    import _transcript
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
    import _transcript

def analyze_logic(events, keywords, window=600):
    results = defaultdict(lambda: {k: 0 for k in keywords})
    time_map = {}
    
    for item in events:
        text = (item.get("text") or "").lower()
        slot = int(item.get("start", 0) // window)
        
        if slot not in time_map:
            time_map[slot] = item.get("timestamp", "")
            
        for key, pats in keywords.items():
            if any(p.lower() in text for p in pats):
                results[slot][key] += 1
                
    output = []
    for slot in sorted(results.keys()):
        row = {"Time": time_map[slot]}
        row.update(results[slot])
        output.append(row)
        
    return output

def main():
    parser = argparse.ArgumentParser(description="Analyze keyword density in transcripts.")
    parser.add_argument("transcript", help="Raw transcript JSON")
    parser.add_argument("--keywords", required=True, help="Keywords JSON config file")
    parser.add_argument("--window", type=int, default=600, help="Time window in seconds")
    args = parser.parse_args()
    
    with open(args.transcript, "r", encoding="utf-8") as f:
        events = _transcript._flatten_json3(json.load(f))
        
    with open(args.keywords, "r", encoding="utf-8") as f:
        keywords = json.load(f)
        
    results = analyze_logic(events, keywords, args.window)
    
    writer = csv.DictWriter(sys.stdout, fieldnames=["Time"] + list(keywords.keys()))
    writer.writeheader()
    
    if not results: return
    
    writer.writerows(results)

if __name__ == "__main__":
    main()
