"""
assemble_timestamps.py - Assemble anibon timestamp sections into a formatted Markdown file.

Usage:
    python assemble_timestamps.py <parts_json> [--output OUTPUT]

Arguments:
    parts_json          Path to a JSON file containing the list of timestamp parts.

Options:
    --output OUTPUT     Output Markdown file path. Default: anibon_timestamps.md
                        in the same directory as parts_json.
"""
import sys
import json
import argparse
from pathlib import Path


def format_sections(parts: list) -> str:
    """Core logic: convert parts list into formatted markdown string."""
    out = []
    for i, part in enumerate(parts, 1):
        out.append("═════════════════════════════════════════════════════════")
        out.append(f"📌 ส่วนที่ {i}: {part['desc']}")
        out.append(f"(หัวข้อ: {part['title']} | ⏱ เริ่ม: {part['start']})")
        out.append("═════════════════════════════════════════════════════════")
        out.append(part["body"])
        out.append("")
    return "\n".join(out).strip() + "\n"


def load_parts(parts_json: Path) -> list:
    """Load and validate parts from a JSON file."""
    data = json.loads(parts_json.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(f"[!] Expected a JSON array in {parts_json}", file=sys.stderr)
        sys.exit(1)
    for item in data:
        for key in ("title", "start", "desc", "body"):
            if key not in item:
                print(f"[!] Missing key '{key}' in part: {item}", file=sys.stderr)
                sys.exit(1)
    return data


def main():
    ap = argparse.ArgumentParser(
        description="Assemble anibon timestamp sections into a formatted Markdown file."
    )
    ap.add_argument("parts_json", type=Path, help="Path to JSON file of timestamp parts.")
    ap.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output Markdown file path. Default: anibon_timestamps.md next to parts_json."
    )
    args = ap.parse_args()

    if not args.parts_json.exists():
        print(f"[!] File not found: {args.parts_json}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.parts_json.parent / "anibon_timestamps.md"

    parts = load_parts(args.parts_json)
    text = format_sections(parts)
    output.write_text(text, encoding="utf-8")
    print(f"[*] Assembled {len(parts)} sections → {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
