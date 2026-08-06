#!/usr/bin/env python3
"""Clean garbled English loanwords in chunk transcripts (JSON or XML).

Thai Whisper auto-transcription commonly garbles English words.
This normaliser runs BETWEEN prepare_video.py and detect_signals.py
so that downstream LLM subagents see clean text.

Usage:
  # In-place clean a chunks directory (default)
  python3 clean_garbled_english.py --chunks ~/youtube_xxx_workspace/chunks/

  # Dry-run (print changes, no writes)
  python3 clean_garbled_english.py --chunks ~/youtube_xxx_workspace/chunks/ --dry-run

  # Single file
  python3 clean_garbled_english.py --chunks ~/youtube_xxx_workspace/chunks/chunk_26.json

Pipeline:
  prepare_video.py  →  clean_garbled_english.py  →  detect_signals.py
"""

import sys, json, re, xml.etree.ElementTree as ET
from pathlib import Path

from anibon.resources import resource_path


def load_replacements() -> list[tuple[re.Pattern, str]]:
    """Load garbled→correct replacements from JSON config."""
    path = resource_path("garbled_replacements.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    compiled = []
    for entry in data.get("replacements", []):
        compiled.append((re.compile(entry["pattern"], re.IGNORECASE), entry["replacement"]))
    return compiled


# Compiled regex cache — loaded once at import time
_COMPILED = load_replacements()


def clean_text(text: str) -> str:
    """Apply all garbled-English replacements to a single text string."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text


def clean_chunk(data: dict) -> list[tuple[str, str]]:
    """Clean all item['text'] fields in a chunk JSON structure."""
    changes = []
    for item in data.get("items", []):
        orig = item.get("text", "")
        cleaned = clean_text(orig)
        if cleaned != orig:
            changes.append((orig, cleaned))
            item["text"] = cleaned
    return changes


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean_xml_chunk(path: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    """Clean <item> text in an XML chunk. Returns (orig, cleaned) pairs."""
    tree = ET.parse(path)
    root = tree.getroot()
    changed = False
    changes = []
    for item in root.iter("item"):
        orig = item.text or ""
        cleaned = clean_text(orig.strip())
        if cleaned != orig.strip():
            changes.append((orig.strip(), cleaned))
            item.text = _escape_xml(cleaned)
            changed = True
    if not dry_run and changed:
        tree.write(path, encoding="utf-8", xml_declaration=False)
    return changes


def process_file(path: Path, dry_run: bool = False) -> int:
    """Process a single chunk file (JSON or XML). Returns change count."""
    if path.suffix == ".xml":
        changes = _clean_xml_chunk(path, dry_run=dry_run)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        changes = clean_chunk(data)
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    if not changes:
        return 0

    # Print changes for review
    name = path.stem
    for orig, cleaned in changes:
        print(f"  {name}: {orig!r} → {cleaned!r}")

    return len(changes)


def process_dir(path: Path, dry_run: bool = False) -> int:
    """Process all chunk files in a directory. Returns total changes."""
    files = sorted(set(path.glob("chunk_*.json")) | set(path.glob("chunk_*.xml")))
    total = 0
    for f in files:
        total += process_file(f, dry_run=dry_run)
    return total


def main():
    import argparse
    ap = argparse.ArgumentParser(
        prog="clean_garbled_english",
        description="Normalise garbled English loanwords in chunk JSON transcripts."
    )
    ap.add_argument("--chunks", required=True,
                    help="Path to chunks directory or single chunk JSON file")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print changes without modifying files")
    args = ap.parse_args()

    path = Path(args.chunks).expanduser().resolve()
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    if path.is_file():
        total = process_file(path, dry_run=args.dry_run)
    else:
        total = process_dir(path, dry_run=args.dry_run)

    mode = " (dry-run)" if args.dry_run else ""
    print(f"Cleaned {total} garbled English occurrences{mode}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
