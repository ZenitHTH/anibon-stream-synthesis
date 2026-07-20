"""
pack_timestamps.py - Pack flat timestamp list into byte-limited parts.

Takes a chronological timestamp list, packs entries into parts respecting
a byte limit, and outputs the result as a formatted markdown document
with separator blocks (matching the anibon-timestamper summarizer spec).

Also writes a parts.json alongside the output for manual editing/reassembly.

Usage:
    python pack_timestamps.py <input> [--byte-limit LIMIT] [--output FILE] [--title TITLE]

Arguments:
    input               Path to timestamp list file (one per line:
                        HH:MM:SS - [Tag] Description)

Options:
    --byte-limit LIMIT  Target bytes per part (default: 3500)
    --output FILE       Output markdown path (default: auto from input name)
    --title TITLE       Document title (default: "วิดีโอสตรีม ANIBON")
    --parts-json FILE   Output parts.json path (default: same as markdown with .json)
"""
import re
import sys
import json
import argparse
from pathlib import Path

LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*-\s*((?:\[.*?\])+)\s*(.*)$")


def parse_timestamps(lines: list) -> list:
    """Parse timestamp lines into sorted list of dicts."""
    timestamps = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"[!] Skipping unparsable line {i+1}: {line[:60]}", file=sys.stderr)
            continue
        time_str, tag, desc = m.groups()
        parts = list(map(int, time_str.split(":")))
        seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        raw = f"{time_str} - {tag} {desc}"
        timestamps.append({
            "time": time_str,
            "sec": seconds,
            "tag": tag,
            "desc": desc,
            "raw": raw,
            "bytes": len(raw.encode("utf-8")),
        })
    timestamps.sort(key=lambda x: x["sec"])
    return timestamps


def _header_bytes(part_index: int, title: str) -> int:
    """Accurate byte cost of the separator block around one part."""
    sep = "═════════════════════════════════════════════════════════\n"
    line2 = f" ส่วนที่ {part_index}: {title} (⏱ เริ่ม: HH:MM:SS)\n"
    return len(sep.encode("utf-8")) * 2 + len(line2.encode("utf-8"))


def pack_parts(timestamps: list, byte_limit: int) -> list:
    """Group timestamps into parts respecting byte_limit."""
    parts = []
    current = {"entries": [], "bytes": 0, "title": "", "start": ""}
    part_index = 0

    for ts in timestamps:
        if not current["entries"]:
            current["title"] = ts["desc"][:80]
            current["start"] = ts["time"]
            current["bytes"] = 0

        candidate = current["bytes"] + ts["bytes"] + 1
        if current["entries"]:
            candidate += _header_bytes(part_index + 1, current["title"])

        if current["entries"] and candidate > byte_limit:
            part_index += 1
            parts.append(current)
            current = {"entries": [], "bytes": 0,
                       "title": ts["desc"][:80], "start": ts["time"]}

        current["entries"].append(ts)
        current["bytes"] += ts["bytes"] + 1

    if current["entries"]:
        part_index += 1
        parts.append(current)

    return parts


def format_markdown(parts: list, doc_title: str) -> str:
    """Format parts into the summarizer-guide separator format."""
    out = [f"# {doc_title}", ""]
    for i, p in enumerate(parts, 1):
        out.append("═════════════════════════════════════════════════════════")
        out.append(f" ส่วนที่ {i}: {p['title']} (⏱ เริ่ม: {p['start']})")
        out.append("═════════════════════════════════════════════════════════")
        for entry in p["entries"]:
            out.append(entry["raw"])
        out.append("")
    return "\n".join(out)


def write_parts_json(parts: list, path: Path):
    """Write parts as JSON for reassembly with assemble_timestamps.py."""
    out = []
    for p in parts:
        body_lines = [e["raw"] for e in p["entries"]]
        out.append({
            "title": p["title"],
            "start": p["start"],
            "body": "\n".join(body_lines),
        })
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] Wrote parts.json with {len(out)} sections → {path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Pack timestamps into byte-limited parts.")
    ap.add_argument("input", type=Path, help="Timestamp list file")
    ap.add_argument("--byte-limit", type=int, default=3500, help="Target bytes per part")
    ap.add_argument("--output", "-o", type=Path, default=None, help="Output markdown path")
    ap.add_argument("--title", default="วิดีโอสตรีม ANIBON", help="Document title")
    ap.add_argument("--parts-json", type=Path, default=None, help="Output parts.json path")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"[!] File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    raw = args.input.read_text(encoding="utf-8").splitlines()
    timestamps = parse_timestamps(raw)

    if not timestamps:
        print("[!] No valid timestamps found.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Parsed {len(timestamps)} timestamps.", file=sys.stderr)
    parts = pack_parts(timestamps, args.byte_limit)
    print(f"[*] Packed into {len(parts)} parts (limit {args.byte_limit}B).", file=sys.stderr)

    for p in parts:
        print(f"    {p['start']} — {p['bytes']:>5}B  {p['title'][:60]}", file=sys.stderr)

    output = args.output or args.input.parent / f"{args.input.stem}_packed.md"
    text = format_markdown(parts, args.title)
    output.write_text(text, encoding="utf-8")
    print(f"[*] Output → {output}", file=sys.stderr)

    parts_path = args.parts_json or args.input.parent / f"{args.input.stem}_parts.json"
    write_parts_json(parts, parts_path)


if __name__ == "__main__":
    main()
