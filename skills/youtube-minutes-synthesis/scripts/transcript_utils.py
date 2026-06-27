import json
import sys
import argparse

def format_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"

def search_transcript(args):
    sys.stdout.reconfigure(encoding='utf-8')
    with open(args.file, encoding='utf-8') as f:
        d = json.load(f)
    
    last_t = -100
    for item in d:
        text = item['text']
        t = item['start']
        
        match = False
        matched_word = ""
        for kw in args.keywords:
            if kw.lower() in text.lower():
                match = True
                matched_word = kw
                break
                
        if match and t - last_t > args.cooldown:
            print(f"{format_time(t)} ({matched_word}) {text}")
            last_t = t

def dump_transcript(args):
    sys.stdout.reconfigure(encoding='utf-8')
    with open(args.file, encoding='utf-8') as f:
        d = json.load(f)
        
    for item in d:
        t = item['start']
        if args.start <= t <= args.end:
            print(f"{format_time(t)} {item['text']}")

def preview_transcript(args):
    sys.stdout.reconfigure(encoding='utf-8')
    with open(args.file, encoding='utf-8') as f:
        d = json.load(f)
        
    for i, item in enumerate(d):
        if i >= args.limit:
            break
        print(f"{format_time(item['start'])} {item['text']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcript utility for searching, dumping, and previewing JSON transcripts.")
    subparsers = parser.add_subparsers(dest="command")
    
    # Search command
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("file", help="Path to transcript JSON file")
    search_parser.add_argument("keywords", nargs="+", help="Keywords to search for")
    search_parser.add_argument("--cooldown", type=int, default=30, help="Minimum seconds between printed matches to avoid spam")
    
    # Dump command
    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("file", help="Path to transcript JSON file")
    dump_parser.add_argument("start", type=float, help="Start time in seconds")
    dump_parser.add_argument("end", type=float, help="End time in seconds")
    
    # Preview command
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("file", help="Path to transcript JSON file")
    preview_parser.add_argument("--limit", type=int, default=10, help="Number of items to preview")
    
    args = parser.parse_args()
    
    if args.command == "search":
        search_transcript(args)
    elif args.command == "dump":
        dump_transcript(args)
    elif args.command == "preview":
        preview_transcript(args)
    else:
        parser.print_help()
