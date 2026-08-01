# scripts/dump_chunk_text.py
import sys, argparse
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Dump transcript text from chunk XML files cleanly.")
    ap.add_argument("chunks", nargs="+", help="Paths to chunk XML files")
    args = ap.parse_args()

    for p in args.chunks:
        path = Path(p)
        if not path.exists():
            continue
        print(f"=== {path.name} ===")
        try:
            tree = ET.parse(path)
            for el in tree.getroot().findall("item"):
                ts = el.attrib.get("timestamp", "00:00:00")
                txt = (el.text or "").strip()
                if txt:
                    print(f"{ts} | {txt}")
        except Exception as e:
            print(f"[!] Error reading {path.name}: {e}")
        print()

if __name__ == "__main__":
    main()
