from __future__ import annotations

import sys, re, json
from pathlib import Path

# ── Resources path ───────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"


def load_asr_garbled_patterns() -> list[tuple[re.Pattern, str]]:
    """Load ASR garbled patterns from JSON config."""
    path = _RESOURCES_DIR / "asr_garbled_patterns.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    compiled = []
    for entry in data.get("patterns", []):
        compiled.append((re.compile(entry["pattern"]), entry["message"]))
    return compiled


# ── ASR Garbled Pattern Scan ─────────────────────────────────────
# Known garbled patterns that should have been caught by
# clean_garbled_english.py. Warn if any appear in the output.
ASR_GARBLED_PATTERNS = load_asr_garbled_patterns()



# ponytail: section size checking based on timestamp line count.
#
# WHY LINE COUNT OVER BYTES:
#   Thai characters take ~3 bytes in UTF-8, making byte counting distort section
#   balance (a concise 18-stamp section can reach 4,000 bytes).
#   We evaluate sections by timestamp line count for human readability.
#
# THRESHOLDS (timestamp lines in body):
#   LINE_LIMIT = 25 lines → hard cap (❌ OVER — must split)
#   LINE_WARN  = 20 lines → warn early (⚠️ WARN — consider splitting)

LINE_LIMIT = 25  # max timestamps per part (❌ OVER)
LINE_WARN  = 20  # warning threshold per part (⚠️ WARN)

BLOCK_RE = re.compile(r'(═+\n(?:(?!═+)[\s\S])*?ส่วนที่(?:(?!═+)[\s\S])*?\n═+\n*)(.*?)(?=═+\n(?:(?!═+)[\s\S])*?ส่วนที่|\Z)', re.DOTALL)


def _full_blocks(text: str) -> list[dict]:
    """Extract full pasted blocks (separator header + body)."""
    results = []
    for header, body in BLOCK_RE.findall(text):
        full = header + body
        label = next((l for l in header.splitlines() if l.startswith("📌")), header[:60])
        results.append({"label": label, "full": full, "body": body})
    return results


def _count_timestamps(body: str) -> int:
    """Count timestamp lines in section body."""
    return sum(1 for line in body.splitlines() if re.match(r"\d{2}:\d{2}:\d{2}", line.strip()))


def suggest_split(body: str) -> str | None:
    """Find the timestamp line closest to the line-midpoint of a too-long body."""
    ts_lines = [
        line.split(" - ")[0].strip()
        for line in body.splitlines()
        if re.match(r"\d{2}:\d{2}:\d{2}", line.strip())
    ]
    if len(ts_lines) < 2:
        return None
    return ts_lines[len(ts_lines) // 2]


def _evaluate_section_status(line_count: int) -> tuple[str, str, bool]:
    """Determine section status label and failure flag based on line count."""
    if line_count > LINE_LIMIT:
        return "❌ OVER  ", "❌ ", True
    if line_count > LINE_WARN:
        return "⚠️  WARN ", "⚠️ ", True
    return "✅ OK    ", "✅ ", False


_OPENING_VERBS = ("วิเคราะห์", "อึ้ง!", "พูดถึง", "ส่อง", "ชำแหละ", "เม้าท์มอย", "เจาะลึก", "กางทฤษฎี", "ถกประเด็น", "เทียบ", "แซว")


def check_verb_diversity(text: str) -> list[str]:
    """Audit timestamp descriptions for consecutive (>=3) or excessive (>20%) repeated opening verbs."""
    descs = [m.group(1).strip() for m in re.finditer(r"^\d{2}:\d{2}:\d{2}\s*-\s*(?:\[[^\]]+\])+\s*(.+)$", text, re.M)]
    if len(descs) < 5:
        return []
    verbs = [next((v for v in _OPENING_VERBS if d.startswith(v)), "") for d in descs]
    warnings = [f"  ⚠️  Opening verb '{v}' used {verbs.count(v)}/{len(descs)} times (>20%)"
                for v in _OPENING_VERBS if verbs.count(v) / len(descs) > 0.20]
    for i in range(len(verbs) - 2):
        if verbs[i] and verbs[i] == verbs[i + 1] == verbs[i + 2]:
            warnings.append(f"  ⚠️  Consecutive verb repetition (3× '{verbs[i]}') around stamp #{i+1}")
            break
    return warnings


def _scan_asr_garbles(text: str) -> list[str]:
    """Scan text for known ASR garbled patterns. Returns list of warnings."""
    warnings = []
    for pattern, msg in ASR_GARBLED_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            warnings.append(f"  ⚠️  Found {len(matches)}× {msg}")
    return warnings


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default=None, help="Timestamp .md file")
    ap.add_argument("--file", dest="file_flag", default=None, help="Timestamp .md file (from hooks)")
    ap.add_argument("--no-garbled-check", action="store_true",
                    help="Skip ASR garbled pattern scan")
    args = ap.parse_args()
    
    file_target = args.file_flag or args.file
    if not file_target:
        sys.exit(0)

    path = Path(file_target)
    if not path.exists():
        # PreToolUse hook fires before write_file creates the target file; exit 0 to allow creation
        sys.exit(0)

    text = path.read_text(encoding="utf-8")
    blocks = _full_blocks(text)

    if not blocks:
        print("[!] No sections found. Make sure the file uses the ═══ separator format.")
        # ponytail: non-timestamp files have no ═══ blocks; exit 0 so hook doesn't block unrelated writes
        sys.exit(0)

    any_fail = False
    suggestions = []
    print(f"\n{'Status':10} {'Lines':>5}  {'Bytes':>6}  Section")
    print("─" * 80)

    for r in blocks:
        nlines = _count_timestamps(r["body"])
        nbytes = len(r["full"].strip().encode("utf-8"))
        status, label, is_over = _evaluate_section_status(nlines)

        if is_over:
            any_fail = True
            mid_ts = suggest_split(r["body"])
            tip = f"split at ≈ {mid_ts}" if mid_ts else "section too short to split"
            suggestions.append(f"  {label}{r['label'][:55]}\n     → {tip}  ({nlines} lines, {nbytes} bytes)")

        print(f"{status}  {nlines:4}L  {nbytes:5}B  {r['label'][:55]}")

    if any_fail:
        print("\n── Suggested split points ──────────────────────────────────────────────")
        for sug in suggestions:
            print(sug)
        sys.exit(1)
    else:
        print("\n✅ All sections are within the timestamp line count limit (≤ 20 lines).")

    # ── ASR garbled scan ──────────────────────────────────────────────
    if not args.no_garbled_check:
        asr_warnings = _scan_asr_garbles(text)
        if asr_warnings:
            print("\n⚠️  ASR Garbled Patterns Detected (run clean_garbled_english.py):")
            for w in asr_warnings:
                print(w)
            print()
        else:
            print("✅ No ASR garbled patterns found.")

    # ── Header truncation scan ─────────────────────────────────────────
    header_warnings = []
    header_re = re.compile(r"ส่วนที่\s*\d+:\s*(.*?)(?:\s*\(⏱.*?\))?$", re.MULTILINE)
    for m in header_re.finditer(text):
        title = m.group(1).strip()
        if re.search(r"(\s(และ|หรือ|กับ|เรื่อง|ใน|ที่)|[เแโใไ็]|และ[ก-ฮ]|แล)$", title):
            header_warnings.append(f"  ⚠️  Header appears truncated/cut-off: '{title}'")
    if header_warnings:
        print("\n⚠️  Truncated Section Headers Detected:")
        for hw in header_warnings:
            print(hw)
        print()
    else:
        print("✅ All section headers are complete and clean.")

    verb_warnings = check_verb_diversity(text)
    if verb_warnings:
        print("\n⚠️  Repetitive Opening Verbs Detected:")
        for vw in verb_warnings:
            print(vw)
    else:
        print("✅ Lexical verb diversity passed.")

if __name__ == "__main__":
    main()
