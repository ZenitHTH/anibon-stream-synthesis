#!/usr/bin/env python3
"""Fetch story synopsis from websearch + cache to local file.

Usage:
  python3 fetch_story_ref.py --game "FGO" --scene "Babylonia Gilgamesh Tiamat"
  python3 fetch_story_ref.py --game "HSR" --scene "Penacony Sunday boss" --cache ./refs
  python3 fetch_story_ref.py --list  # show cached entries
"""

import sys
import json
import os
import re
import hashlib
from pathlib import Path


CACHE_DIR = Path(__file__).resolve().parent.parent / "references" / "stories"


def slug(text):
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60]


def cache_path(game, scene, cache_dir):
    key = f"{slug(game)}_{slug(scene)}"
    return Path(cache_dir) / f"{key}.md"


def load_cache(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def write_cache(path, synopsis):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(synopsis.strip() + "\n")


def websearch_synopsis(game, scene):
    import urllib.request
    import urllib.parse

    query = f"{game} {scene} story synopsis"
    params = urllib.parse.urlencode({"q": query})
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "anibon-fetch-story-ref/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        # Try AbstractText first, then RelatedTopics
        text = data.get("AbstractText", "")
        if not text and data.get("RelatedTopics"):
            text = data[0].get("Text", "")
        if not text:
            text = data.get("Definition", "")
        if not text:
            text = f"{game} — {scene}"
        return text[:200]
    except Exception as e:
        return f"[{game}] {scene} (synopsis unavailable: {e})"


def list_cache(cache_dir):
    p = Path(cache_dir)
    if not p.exists():
        print("No cached references.")
        return
    for f in sorted(p.iterdir()):
        if f.suffix == ".md" and f.name != ".gitkeep":
            with open(f, encoding="utf-8") as fh:
                first_line = fh.readline().strip()
            print(f"{f.stem}: {first_line[:80]}")


def main():
    import argparse

    ap = argparse.ArgumentParser(
        prog="fetch_story_ref",
        description="Fetch story synopsis via websearch and cache locally. "
                    "Returns synopsis text to stdout for timestamp enrichment.",
        epilog="Examples:\n"
               "  %(prog)s --game FGO --scene \"Babylonia Tiamat war\"\n"
               "  %(prog)s --game \"Honkai Star Rail\" --scene \"Penacony\" --cache ./refs\n"
               "  %(prog)s --list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--game", "-g", help="Game title (exact name)")
    ap.add_argument("--scene", "-s", help="Chapter/scene/mission description")
    ap.add_argument("--cache", default=str(CACHE_DIR),
                    help=f"Cache directory (default: {CACHE_DIR})")
    ap.add_argument("--list", "-l", action="store_true", help="List cached entries")

    args = ap.parse_args()

    if args.list:
        list_cache(args.cache)
        return

    if not args.game or not args.scene:
        print("Error: --game and --scene are required (unless --list).", file=sys.stderr)
        sys.exit(64)

    cpath = cache_path(args.game, args.scene, args.cache)
    cached = load_cache(cpath)

    if cached:
        print(cached)
        return

    synopsis = websearch_synopsis(args.game, args.scene)
    write_cache(cpath, synopsis)
    print(synopsis)


if __name__ == "__main__":
    main()
