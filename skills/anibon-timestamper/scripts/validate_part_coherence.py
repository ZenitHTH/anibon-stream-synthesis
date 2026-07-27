"""
validate_part_coherence.py — Check every assembled part contains ONE coherent topic.

Uses signals.json (from detect_signals.py) as the authoritative game/topic reference
instead of a hardcoded game list.

Algorithm:
1. Load signals.json → extract all known game/anime names from matched file paths
2. Read assembled .md file → extract parts (═══ separated blocks)
3. For each part, collect all timestamp tags + descriptions
4. For each timestamp, determine which chunk it falls in → get that chunk's signals
5. Check:
   a. Tag-macro diversity (TALK, GAMEPLAY, NEWS, etc.)
   b. Game diversity — does the part mention 2+ different games?
   c. Signal cross-check — do description games match chunk-level signals?
   d. Keyword coherence — do descriptions share common tokens?
   e. Tag continuity — no flips between disparate categories
6. Exit code 1 if ANY part fails coherence check

Usage:
    python validate_part_coherence.py output.md --signals signals.json

Options:
    --signals FILE   signals.json from detect_signals.py (REQUIRED for game check)
    --chunks DIR     Chunk directory for richer cross-reference
    --verbose        Print per-part details even for passing parts
"""

import re
import sys
import json
from pathlib import Path
from collections import Counter

# ── Resources ────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"


def load_tag_macros() -> dict[str, str]:
    """Load tag→macro mapping from JSON config."""
    path = _RESOURCES_DIR / "tag_macros.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("mapping", {})


def load_filename_game_map() -> dict[str, str]:
    """Load filename→game display name mapping from JSON config."""
    path = _RESOURCES_DIR / "filename_game_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("mapping", {})


# ── Constants ────────────────────────────────────────────────────

TAG_EXTRACT = re.compile(r"\[([^\]]+)\]")
TIMESTAMP_LINE_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\s*-\s*((?:\[.*?\])+)\s*(.*)$")

TAG_MACRO_MAP = load_tag_macros()
FILENAME_GAME_MAP = load_filename_game_map()

BLOCK_RE = re.compile(
    r'(═+\n\s*ส่วนที่[^\n]+\n═+\n*)(.*?)(?=═+\n\s*ส่วนที่|\Z)',
    re.DOTALL,
)


# ── Signal Loading ───────────────────────────────────────────────

def load_signals(signals_path: Path) -> dict:
    """Load signals.json and return parsed structure.

    Returns dict with:
      - game_names: set of canonical game names found across all chunks
      - chunk_signals: {chunk_name: [game_name, ...]} — games matched per chunk
    """
    data = json.loads(signals_path.read_text(encoding="utf-8"))
    chunks = data.get("chunks", {})

    game_names: set[str] = set()
    chunk_signals: dict[str, set[str]] = {}

    for ch_name, ch_data in chunks.items():
        matched_files = ch_data.get("matched_files", [])
        games_here: set[str] = set()
        for mf in matched_files:
            fpath = mf.get("file", "")
            # Extract stem from file path
            stem = Path(fpath).stem
            # Try direct map, else use stem as name
            display = FILENAME_GAME_MAP.get(stem, stem.replace("_", " "))
            game_names.add(display)
            games_here.add(display)
        chunk_signals[ch_name] = games_here

    return {
        "game_names": game_names,
        "chunk_signals": chunk_signals,
        "chunk_order": sorted(chunks.keys()),  # sorted chunk names
    }


def _chunk_index(name: str) -> int:
    """Extract numeric index from chunk_03 or chunk_03.json."""
    m = re.search(r'(\d+)', name)
    return int(m.group(1)) if m else 0


def build_time_to_chunk_map(signals: dict, chunks_dir: Path | None) -> dict[tuple[int, int], str]:
    """Build {(start_sec, end_sec): chunk_name} map from chunk files.

    If chunks_dir not provided, estimate from chunk index * 300 (5-min default).
    """
    chunk_map: dict[tuple[int, int], str] = {}
    chunk_order = signals.get("chunk_order", [])
    chunk_signals = signals.get("chunk_signals", {})

    if chunks_dir and chunks_dir.exists():
        # Load actual chunk start times from files
        for ch_name in chunk_order:
            ch_file = chunks_dir / f"{ch_name}.json"
            if not ch_file.exists():
                ch_file = chunks_dir / f"{ch_name}.xml"
            if ch_file.exists():
                raw = ch_file.read_text(encoding="utf-8")
                if ch_file.suffix == ".json":
                    data = json.loads(raw)
                else:
                    import xml.etree.ElementTree as ET
                    data = ET.parse(ch_file).getroot()
                start_sec = int(data.get("start_sec", 0)) if isinstance(data, (dict, ET.Element)) else 0
                # estimate end_sec = start + 300 (5 min default block)
                end_sec = int(data.get("end_sec", start_sec + 300)) if isinstance(data, (dict, ET.Element)) else start_sec + 300
                chunk_map[(start_sec, end_sec)] = ch_name
                continue
            # Fallback: estimate from index
            idx = _chunk_index(ch_name)
            s = idx * 300
            chunk_map[(s, s + 300)] = ch_name
    else:
        # Estimate from chunk index
        for ch_name in chunk_order:
            idx = _chunk_index(ch_name)
            s = idx * 300
            chunk_map[(s, s + 300)] = ch_name

    return chunk_map


def get_chunk_for_timestamp(sec: int, chunk_map: dict[tuple[int, int], str]) -> str | None:
    """Find which chunk a timestamp (in seconds) falls into."""
    for (start, end), name in chunk_map.items():
        if start <= sec < end:
            return name
    return None


# ── Helpers ──────────────────────────────────────────────────────

def _primary_tag(full_tag: str) -> str:
    """Map a full tag string like '[Talk]' to macro category 'TALK'."""
    m = TAG_EXTRACT.match(full_tag)
    raw_tag = m.group(1) if m else full_tag
    return TAG_MACRO_MAP.get(raw_tag, raw_tag)


def _extract_game_names_from_signals(desc: str, game_names: set[str]) -> list[str]:
    """
    Find which known game names appear in a description.
    Uses signals-derived game names (not hardcoded).
    Longer names checked first to avoid substring collisions.
    """
    desc_lower = desc.lower()
    found = []
    for name in sorted(game_names, key=len, reverse=True):
        if name.lower() in desc_lower:
            found.append(name)
            # Don't break — collect all matches
    return found


def _tokenize(desc: str) -> set[str]:
    """Extract meaningful Thai/English tokens from a description."""
    text = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'[–—\-–—,:;.?!()<>"\'\[\]{}]', ' ', text)
    tokens = set()
    for t in text.strip().split():
        t = t.strip()
        if len(t) >= 2:
            tokens.add(t.lower())
    return tokens


def _keyword_overlap(a_tokens: set[str], b_tokens: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return len(intersection) / len(union)


def _parse_time_to_sec(time_str: str) -> int:
    """Convert HH:MM:SS to seconds."""
    parts = list(map(int, time_str.split(":")))
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


# ── Part Extraction ──────────────────────────────────────────────

def extract_parts(text: str) -> list[dict]:
    """Extract parts from assembled markdown.

    Returns list of {label, header, timestamps}
    where timestamps = [{tag, desc, raw, sec}]
    """
    parts = []
    for header, body in BLOCK_RE.findall(text):
        label_line = next(
            (l for l in header.splitlines() if "ส่วนที่" in l),
            header[:60],
        )
        body_lines = [l for l in body.splitlines() if l.strip()]
        timestamps = []
        for line in body_lines:
            m = TIMESTAMP_LINE_RE.match(line.strip())
            if m:
                tag_str, desc = m.groups()
                # Extract time from the raw line
                time_match = re.match(r"(\d{2}:\d{2}:\d{2})", line.strip())
                sec = _parse_time_to_sec(time_match.group(1)) if time_match else 0
                timestamps.append({
                    "tag": tag_str.strip(),
                    "desc": desc.strip(),
                    "raw": line.strip(),
                    "sec": sec,
                })
        parts.append({
            "label": label_line.strip(),
            "header": header,
            "timestamps": timestamps,
            "count": len(timestamps),
        })
    return parts


# ── Coherence Checks ─────────────────────────────────────────────

def check_tag_diversity(part: dict) -> list[str]:
    """Flag if part contains 2+ different tag macros that suggest topic mixing."""
    flags = []
    macros = [_primary_tag(ts["tag"]) for ts in part["timestamps"]]
    macro_set = set(macros)

    if len(macro_set) <= 1:
        return []

    macro_counts = Counter(macros)
    # Allow TALK + GAMEPLAY if within same game
    if macro_set == {"TALK", "GAMEPLAY"}:
        return []

    summary = ", ".join(f"{m} ({c}x)" for m, c in macro_counts.most_common())
    flags.append(
        f"Mixed tag macros: {summary}. "
        f"Verify all stamps belong to same topic."
    )
    return flags


def check_game_diversity(part: dict, game_names: set[str]) -> list[str]:
    """Flag if part mentions 2+ different games in descriptions, using signals-derived names."""
    flags = []
    all_games: set[str] = set()
    for ts in part["timestamps"]:
        games = _extract_game_names_from_signals(ts["desc"], game_names)
        all_games.update(games)

    if len(all_games) > 1:
        games_list = sorted(all_games)
        flags.append(
            f"Multiple games in same part: {', '.join(games_list)}. "
            f"Different games MUST be in separate parts."
        )
    return flags


def check_signal_cross_reference(part: dict, chunk_map: dict, signals: dict) -> list[str]:
    """
    Cross-check each timestamp's mentioned games against the chunk-level signals.
    If a timestamp mentions a game that does NOT appear in its chunk's signals,
    flag it as potentially fabricated.
    """
    flags = []
    chunk_signals = signals.get("chunk_signals", {})
    game_names = signals.get("game_names", set())

    for ts in part["timestamps"]:
        sec = ts.get("sec", 0)
        chunk_name = get_chunk_for_timestamp(sec, chunk_map)

        if not chunk_name or chunk_name not in chunk_signals:
            continue  # Can't cross-reference

        games_in_desc = _extract_game_names_from_signals(ts["desc"], game_names)
        if not games_in_desc:
            continue  # No game name to cross-check

        allowed_games = chunk_signals[chunk_name]
        for g in games_in_desc:
            if g not in allowed_games:
                # Check if any allowed game is substring-related
                related = any(
                    g.lower() in a.lower() or a.lower() in g.lower()
                    for a in allowed_games
                )
                if not related:
                    flags.append(
                        f"Timestamp '{ts['raw'][:50]}' mentions '{g}' "
                        f"but chunk '{chunk_name}' signals show: {allowed_games}. "
                        f"Game name may be fabricated or off-topic."
                    )
    return flags


def check_keyword_coherence(part: dict) -> list[str]:
    """Flag if description keywords across timestamps show no common thread."""
    flags = []
    token_sets = [_tokenize(ts["desc"]) for ts in part["timestamps"]]

    if len(token_sets) < 2:
        return []

    first_tokens = token_sets[0]
    min_overlap = float("inf")
    for i, tokens in enumerate(token_sets[1:], 1):
        overlap = _keyword_overlap(first_tokens, tokens)
        if overlap < min_overlap:
            min_overlap = overlap

    if min_overlap < 0.10 and len(token_sets) >= 3:
        descs = [ts["desc"][:40] for ts in part["timestamps"]]
        flags.append(
            f"Low keyword overlap ({min_overlap:.0%} min). "
            f"Descriptions may span unrelated topics: {descs}"
        )
    return flags


def check_tag_order_and_continuity(part: dict) -> list[str]:
    """Flag if tags flip between disparate types without clear boundary."""
    flags = []
    if len(part["timestamps"]) < 3:
        return []

    macros = [_primary_tag(ts["tag"]) for ts in part["timestamps"]]

    flip_count = 0
    for i in range(2, len(macros)):
        if macros[i] == macros[i - 2] and macros[i] != macros[i - 1]:
            flip_count += 1

    if flip_count >= 2:
        flags.append(
            f"Tag flip pattern detected ({flip_count} flips). "
            f"Topics may be interleaved. Consider splitting."
        )
    return flags


# ── Main ─────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Validate every part in assembled .md has coherent topic.")
    ap.add_argument("file", type=Path, help="Assembled timestamp .md file")
    ap.add_argument("--signals", type=Path, default=None,
                    help="signals.json from detect_signals.py (REQUIRED for game cross-check)")
    ap.add_argument("--chunks", type=Path, default=None,
                    help="Path to chunk directory for timestamp-to-chunk mapping")
    ap.add_argument("--verbose", action="store_true",
                    help="Print per-part details even for passing parts")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"[!] File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Load signals
    signals = None
    if args.signals:
        if not args.signals.exists():
            print(f"[!] signals.json not found: {args.signals}", file=sys.stderr)
            sys.exit(1)
        signals = load_signals(args.signals)
        print(f"[*] Loaded {len(signals['game_names'])} game names from signals: "
              f"{sorted(signals['game_names'])}", file=sys.stderr)
    else:
        print("[!] No --signals provided. Game diversity check will be skipped.",
              file=sys.stderr)

    # Build chunk time map for cross-reference
    chunk_map = {}
    if signals:
        chunk_map = build_time_to_chunk_map(signals, args.chunks)
        print(f"[*] Built time→chunk map with {len(chunk_map)} entries", file=sys.stderr)

    # Extract parts from assembled file
    text = args.file.read_text(encoding="utf-8")
    parts = extract_parts(text)

    if not parts:
        print("[!] No parts found. File must use ═══ separator format.", file=sys.stderr)
        sys.exit(0)

    game_names = signals["game_names"] if signals else set()

    print(f"\n{'Status':12} {'#Stamps':>8}  Part")
    print("─" * 72)

    any_fail = False
    all_flags: list[dict] = []

    for idx, part in enumerate(parts, 1):
        flags = []
        flags.extend(check_tag_diversity(part))
        if signals:
            flags.extend(check_game_diversity(part, game_names))
            flags.extend(check_signal_cross_reference(part, chunk_map, signals))
        flags.extend(check_keyword_coherence(part))
        flags.extend(check_tag_order_and_continuity(part))

        status = "❌ FAIL" if flags else "✅ PASS"
        if flags:
            any_fail = True

        print(f"{status}  {part['count']:>5} ts  Part {idx}: {part['label'][:55]}")

        if args.verbose or flags:
            for ts in part["timestamps"]:
                print(f"         {ts['raw'][:70]}")
            for f in flags:
                print(f"         ⚠️  {f}")
            print()

        if flags:
            all_flags.append({
                "part": idx,
                "label": part["label"],
                "count": part["count"],
                "flags": flags,
            })

    print("─" * 72)
    if any_fail:
        print(f"\n❌ {len(all_flags)} part(s) failed coherence check:")
        for item in all_flags:
            print(f"   Part {item['part']} ({item['count']} stamps):")
            for f in item["flags"]:
                print(f"      ⚠️  {f}")
        print("\n-> Fix: Move off-topic stamps to correct part, or split the part.")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(parts)} parts are topic-coherent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
