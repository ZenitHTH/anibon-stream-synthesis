import sys, re
from pathlib import Path

# ponytail: replaces manual copy-paste-count workflow for section size checking.
# Ceiling: assumes ═══ separator blocks. Upgrade path: support --- fallback format.

LIMIT = 5000   # YouTube Thai comment hard cap
WARN  = 4500   # warn early to leave margin

SEP = re.compile(r'═+\n(📌[^\n]+)\n([^\n]+)\n═+')


def check(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    parts = SEP.split(text)
    # parts = [pre, header1, meta1, body1, header2, meta2, body2, ...]
    results = []
    # skip parts[0] (content before first separator)
    for i in range(1, len(parts) - 2, 3):
        header = parts[i].strip()
        body   = parts[i + 2]
        size   = len(body)
        results.append({"header": header, "size": size})
    return results


def suggest_split(body: str) -> str | None:
    """Find the timestamp closest to the midpoint of a too-long section."""
    lines = [l for l in body.splitlines() if re.match(r'\d{2}:\d{2}:\d{2}', l.strip())]
    if len(lines) < 2:
        return None
    mid_idx = len(lines) // 2
    return lines[mid_idx].split(" - ")[0].strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_sections.py <timestamp_file.md>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[!] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    parts = SEP.split(text)
    results = []
    for i in range(1, len(parts) - 2, 3):
        results.append({"header": parts[i].strip(), "body": parts[i + 2], "size": len(parts[i + 2])})

    any_fail = False
    print(f"\n{'Status':6} {'Chars':>6}  Section")
    print("─" * 70)
    for r in results:
        size = r["size"]
        if size > LIMIT:
            status = "❌ OVER"
            any_fail = True
        elif size > WARN:
            status = "⚠️ WARN "
            any_fail = True
        else:
            status = "✅ OK  "
        print(f"{status}  {size:5}  {r['header'][:55]}")

    if any_fail:
        print("\n── Suggested split points ──────────────────────────────────────")
        for r in results:
            if r["size"] > WARN:
                mid_ts = suggest_split(r["body"])
                label = "⚠️ " if r["size"] <= LIMIT else "❌ "
                tip = f"split at ≈ {mid_ts}" if mid_ts else "section too short to split"
                print(f"  {label}{r['header'][:50]}")
                print(f"     → {tip}  ({r['size']} chars)")
    else:
        print("\n✅ All sections are within the YouTube comment limit.")


if __name__ == "__main__":
    main()
