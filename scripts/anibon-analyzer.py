# anibon-analyzer.py
import sys
import argparse
import os
from anibon_analyzer_core import load_chunks, classify_chunk, detect_timeline_gaps, calculate_youtube_blocks

def main():
    parser = argparse.ArgumentParser(description="Anibon Transcript CLI Analyzer")
    parser.add_argument("workspace_dir", help="Path to a video workspace folder")
    parser.add_argument("-g", "--gap-limit", type=int, default=600, help="Seconds before a gap triggers a warning")
    parser.add_argument("-w", "--warn-bytes", type=int, default=3500, help="Byte threshold for YouTube block warnings")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show matched keywords per chunk")
    
    args = parser.parse_args()
    
    try:
        chunks = load_chunks(args.workspace_dir)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
        
    print("Chunk       Start     End       Categories          Snippet")
    print("──────────  ────────  ────────  ──────────────────  ──────────────────────")
    
    for idx, chunk in enumerate(chunks):
        tags = classify_chunk(chunk)
        chunk["category"] = tags[0] # primary category for blocks
        
        start_ts = chunk["items"][0]["timestamp"] if chunk.get("items") else "00:00:00"
        end_ts = chunk["items"][-1]["timestamp"] if chunk.get("items") else "00:00:00"
        snippet = " ".join([it.get("text", "") for it in chunk.get("items", [])])[:22].replace("\n", " ")
        cats = ", ".join(tags)
        
        chunk_name = f"chunk_{idx:02d}"
        print(f"{chunk_name:<10}  {start_ts:<8}  {end_ts:<8}  {cats:<18}  {snippet}")
        
    print("\n")
    
    gaps = detect_timeline_gaps(chunks, args.gap_limit)
    if gaps:
        for gap in gaps:
            sys.stderr.write(f"⚠️  GAP DETECTED: {gap['from_ts']} → {gap['to_ts']}  ({gap['gap_sec']}s, limit={args.gap_limit}s)\n")
        sys.stderr.write("\n")
            
    print("Status    Bytes   Category     Start     End")
    print("────────  ──────  ───────────  ────────  ────────")
    
    blocks = calculate_youtube_blocks(chunks, args.warn_bytes)
    for block in blocks:
        status = block["status"]
        icon = "✅ OK   " if status == "OK" else "⚠️  WARN" if status == "WARN" else "❌ OVER "
        b_size = f"{block['byte_size']}B"
        print(f"{icon:<8}  {b_size:<6}  {block['category']:<11}  {block['start_ts']:<8}  {block['end_ts']:<8}")

if __name__ == "__main__":
    main()
