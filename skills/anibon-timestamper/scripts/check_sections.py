import sys, re
from pathlib import Path

# ponytail: replaces manual copy-paste-count workflow for section size checking.
#
# WHY BYTES, NOT CHARS:
#   YouTube's comment input counts characters using JavaScript's string length,
#   which counts each UTF-16 code unit. Thai characters are U+0E00–U+0E7F and
#   each occupies 1 UTF-16 code unit (same as ASCII). However, YouTube's *server*
#   validation stores text in UTF-8 bytes and has historically enforced an 8 KB
#   byte cap per comment. For practical safety we measure the FULL BLOCK
#   (header + body, as the user pastes it) in UTF-8 bytes.
#
#   Thai character ≈ 3 bytes in UTF-8, so 5,000 chars of dense Thai ≈ 15,000 bytes
#   which WAY exceeds YouTube's server limit. Empirically, a paste that fails
#   always has a UTF-8 byte size > ~5,000 bytes. We therefore use bytes as the
#   primary metric and set conservative thresholds.
#
# THRESHOLDS (bytes of the FULL pasted block):
#   LIMIT = 4500 bytes  → hard cap (❌ OVER — cannot paste)
#   WARN  = 3500 bytes  → warn early (⚠️ WARN — risky, split recommended)
#
# The FULL block includes: the two ═══ separator lines, the 📌 header line,
# the ⏱ metadata line, and all timestamp body lines below it.

LIMIT = 4500   # bytes — YouTube Thai comment hard cap (empirical)
WARN  = 3500   # bytes — warn early to leave safe margin

BLOCK_RE = re.compile(r'((?:═+|-+)\n📌[^\n]+\n[^\n]+\n(?:═+|-+)\n*)(.*?)(?=(?:═+|-+)\n📌|\Z)', re.DOTALL)


def _full_blocks(text: str) -> list[dict]:
    """Extract full pasted blocks (separator header + body)."""
    results = []
    for header, body in BLOCK_RE.findall(text):
        full = header + body
        label = next((l for l in header.splitlines() if l.startswith("📌")), header[:60])
        results.append({"label": label, "full": full, "body": body})
    return results


def suggest_split(body: str) -> str | None:
    """Find the timestamp line closest to the byte-midpoint of a too-long body."""
    total_bytes = len(body.encode("utf-8"))
    if total_bytes == 0:
        return None
    midpoint = total_bytes / 2
    
    ts_lines = []
    current_bytes = 0
    
    for line in body.splitlines(keepends=True):
        if re.match(r'\d{2}:\d{2}:\d{2}', line.strip()):
            ts = line.split(" - ")[0].strip()
            ts_lines.append((current_bytes, ts))
        current_bytes += len(line.encode("utf-8"))
        
    if len(ts_lines) < 2:
        return None
        
    best_ts = min(ts_lines, key=lambda x: abs(x[0] - midpoint))[1]
    return best_ts


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="Timestamp .md file")
    args = ap.parse_args()
    
    path = Path(args.file)
    if not path.exists():
        print(f"[!] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    blocks = _full_blocks(text)

    if not blocks:
        print("[!] No sections found. Make sure the file uses the ═══ separator format.")
        # ponytail: non-timestamp files have no ═══ blocks; exit 0 so hook doesn't block unrelated writes
        sys.exit(0)

    any_fail = False
    suggestions = []
    print(f"\n{'Status':10} {'Bytes':>6}  {'Chars':>6}  Section")
    print("─" * 80)
    
    for r in blocks:
        nbytes = len(r["full"].strip().encode("utf-8"))
        nchars = len(r["full"].strip())
        
        if nbytes > LIMIT:
            status = "❌ OVER  "
            any_fail = True
            label = "❌ "
        elif nbytes > WARN:
            status = "⚠️  WARN "
            any_fail = True
            label = "⚠️ "
        else:
            status = "✅ OK    "
            
        print(f"{status}  {nbytes:5}B  {nchars:5}c  {r['label'][:55]}")
        
        if nbytes > WARN:
            mid_ts = suggest_split(r["body"])
            tip = f"split at ≈ {mid_ts}" if mid_ts else "section too short to split"
            suggestions.append(f"  {label}{r['label'][:55]}\n     → {tip}  ({nbytes} bytes, {nchars} chars)")

    if any_fail:
        print("\n── Suggested split points ──────────────────────────────────────────────")
        for sug in suggestions:
            print(sug)
        sys.exit(1)
    else:
        print("\n✅ All sections are within the YouTube comment byte limit.")

if __name__ == "__main__":
    main()
