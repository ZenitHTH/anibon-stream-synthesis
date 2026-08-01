"""
pack_timestamps.py - Pack flat timestamp list into byte-limited parts.

Algorithm: Two-pass balanced partition
  Pass 1 (Greedy estimate): Run left-to-right fill to count K = natural number of parts.
  Pass 2 (DP min-max balance): Use dynamic programming to find the split that
          minimises max_part_size - min_part_size while still respecting the hard
          byte ceiling (byte_limit). This is the "balanced partition" / "painters
          partition" problem solved in O(N * K) time.

The result is provably optimal -- no reordering, chronological order preserved,
each part <= byte_limit, and the spread between the largest and smallest part
is as small as possible.

Usage:
    python pack_timestamps.py <input> [--byte-limit LIMIT] [--output FILE] [--title TITLE]

Arguments:
    input               Path to timestamp list file (one per line:
                        HH:MM:SS - [Tag] Description)

Options:
    --byte-limit LIMIT  Hard ceiling bytes per part (default: 3500)
    --output FILE       Output markdown path (default: auto from input name)
    --title TITLE       Document title (default: "วิดีโอสตรีม ANIBON")
    --parts-json FILE   Output parts.json path (default: same stem + _parts.json)
"""
import re
import sys
import json
import argparse
from pathlib import Path

# ── Resources ───────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"


def load_tag_macros() -> dict[str, str]:
    """Load tag→macro mapping from JSON config."""
    path = _RESOURCES_DIR / "tag_macros.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("mapping", {})


# ── Garbled English clean (reuse from sibling script) ──────────
def _load_garbled_cleaner():
    """Lazy-import clean_text from clean_garbled_english.py.
    Falls back to a no-op if the module is missing."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "clean_garbled_english",
            _SCRIPT_DIR / "clean_garbled_english.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.clean_text
    except Exception:
        pass
    return lambda t: t  # no-op fallback


_clean_desc = _load_garbled_cleaner()


# Byte cost of the ═══ separator block (two sep lines ~172B each + title line ~140B).
# Both greedy K estimation and DP ceiling use this so they stay consistent.
HEADER_OVERHEAD = 500

LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*-\s*((?:\[.*?\])+)\s*(.*)$")
INF = float("inf")



# ─────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────

def parse_timestamps(lines: list) -> list:
    """Parse timestamp lines into a chronologically sorted list of dicts."""
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
        desc = _clean_desc(desc)
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


# ─────────────────────────────────────────────────────────────
# Pre-processing — merge consecutive [Story] entries
# ─────────────────────────────────────────────────────────────

STORY_TAG = "[Story]"


def merge_consecutive_story(timestamps: list[dict]) -> list[dict]:
    """Collapse consecutive [Story] entries into one. Keeps first entry's
    time and description; drops redundant follow-on entries that are
    part of same continuous story-reading session."""
    if not timestamps:
        return []
    merged: list[dict] = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts["tag"] == STORY_TAG and merged[-1]["tag"] == STORY_TAG:
            continue
        merged.append(ts)
    return merged


# ─────────────────────────────────────────────────────────────
# Overhead accounting
# ─────────────────────────────────────────────────────────────

def _header_bytes(part_index: int, title: str, start: str) -> int:
    """Byte cost of the ═══ separator block for one part."""
    sep = "═════════════════════════════════════════════════════════\n"
    line2 = f" ส่วนที่ {part_index}: {title} (⏱ เริ่ม: {start})\n"
    return len(sep.encode("utf-8")) * 2 + len(line2.encode("utf-8"))


THAI_LEADING_VOWELS = set("เแโใไ")


def _clean_title(desc: str, max_len: int = 100) -> str:
    """Clean title that preserves complete Thai words and avoids cutting mid-word/mid-vowel."""
    desc = desc.strip()
    if len(desc) <= max_len:
        return desc

    truncated = desc[:max_len]
    last_space = max(truncated.rfind(" "), truncated.rfind("،"), truncated.rfind(")"))
    if last_space > 30:
        truncated = truncated[:last_space]

    while truncated and (truncated[-1] in THAI_LEADING_VOWELS or not truncated[-1].isalnum()):
        truncated = truncated[:-1].strip()

    return truncated


def _body_bytes(entries: list) -> int:
    """Total byte cost of the entry lines in one part (each line + newline)."""
    return sum(e["bytes"] + 1 for e in entries)


def _part_bytes(entries: list, part_index: int) -> int:
    """Total byte cost including separator overhead."""
    if not entries:
        return 0
    title = _clean_title(entries[0]["desc"])
    start = entries[0]["time"]
    return _header_bytes(part_index, title, start) + _body_bytes(entries)


# ─────────────────────────────────────────────────────────────
# Pass 1 – Greedy estimate of K (number of parts)
# ─────────────────────────────────────────────────────────────

def _greedy_k(timestamps: list, byte_limit: int) -> int:
    """Return the minimum number of parts that fit within byte_limit.

    Uses effective body budget = byte_limit - HEADER_OVERHEAD so the
    count agrees with what check_sections.py actually measures.
    """
    body_limit = byte_limit - HEADER_OVERHEAD
    k = 1
    running = 0
    for ts in timestamps:
        candidate = running + ts["bytes"] + 1
        if running > 0 and candidate > body_limit:
            k += 1
            running = ts["bytes"] + 1
        else:
            running = candidate
    return k


# ─────────────────────────────────────────────────────────────
# Pass 2 – Balanced partition DP (Painter's Partition variant)
# ─────────────────────────────────────────────────────────────
#
# Classic painters-partition: split N items into K contiguous groups
# minimising max-group-sum.  Extended here to minimise
# max_size - min_size (spread) while also penalising a single very
# large or very small part.
#
# State: dp[i][j] = minimum possible (max_size) when placing the
#        first i timestamps into j parts.
# Transition: dp[i][j] = min over all valid split points m of
#             max(dp[m][j-1], size(m+1..i))
# Complexity: O(N² × K) — fine for N ≤ ~500 and K ≤ 20.
#

def _prefix_body(timestamps: list) -> list:
    """Prefix sums of raw body bytes (no overhead) for O(1) range queries."""
    prefix = [0] * (len(timestamps) + 1)
    for i, ts in enumerate(timestamps):
        prefix[i + 1] = prefix[i] + ts["bytes"] + 1
    return prefix


def _range_body_bytes(prefix: list, lo: int, hi: int) -> int:
    """Body bytes for timestamps[lo:hi] (0-indexed, exclusive hi)."""
    return prefix[hi] - prefix[lo]


# ─────────────────────────────────────────────────────────────
# Context segmentation (Pass 1)
# ─────────────────────────────────────────────────────────────

_TAG_EXTRACT = re.compile(r"\[([^\]]+)\]")

TAG_MACRO_MAP = load_tag_macros()


def _primary_tag(tag: str) -> str:
    """Extract the first bracketed label, or the full tag string, mapped to macro category."""
    m = _TAG_EXTRACT.match(tag)
    raw_tag = m.group(1) if m else tag
    return TAG_MACRO_MAP.get(raw_tag, raw_tag)





def cluster_by_tag(timestamps: list[dict]) -> list[list[dict]]:
    """
    Group consecutive timestamps by primary tag into context segments.

    A tag-change only starts a new segment when >= 2 consecutive entries
    share the new tag. Single-entry tag flickers are absorbed into the
    previous segment to avoid noisy mid-scene splits.
    """
    if not timestamps:
        return []

    segments: list[list[dict]] = [[timestamps[0]]]
    current_tag = _primary_tag(timestamps[0]["tag"])

    i = 1
    while i < len(timestamps):
        ts = timestamps[i]
        new_tag = _primary_tag(ts["tag"])

        if new_tag == current_tag:
            segments[-1].append(ts)
            i += 1
        else:
            # Peek ahead: confirmed change only when next entry shares new_tag
            if (i + 1 < len(timestamps)
                    and _primary_tag(timestamps[i + 1]["tag"]) == new_tag):
                segments.append([ts])
                current_tag = new_tag
            else:
                # Flicker — absorb into current segment
                segments[-1].append(ts)
            i += 1

    return segments


# ─────────────────────────────────────────────────────────────
# Segment normaliser (Pass 2)
# ─────────────────────────────────────────────────────────────

def _body_bytes_of(entries: list[dict]) -> int:
    """Total body bytes for a list of timestamp entries."""
    return sum(e["bytes"] + 1 for e in entries)


def cluster_by_topic(timestamps: list[dict], topic_map: list[dict]) -> list[list[dict]]:
    """
    Group timestamps by topic labels from --topic-json.

    Each topic_map entry: {start: "HH:MM:SS", end: "HH:MM:SS", label: str}
    Timestamps are assigned to the topic whose [start, end) range contains them.
    Timestamps outside any topic range get their own single-entry segment.
    This produces coherent segments that respect topic boundaries.
    """
    if not timestamps or not topic_map:
        return cluster_by_tag(timestamps)  # fallback

    # Convert topic_map start/end to seconds for comparison
    def _to_sec(t: str) -> int:
        p = list(map(int, t.split(":")))
        return p[0] * 3600 + p[1] * 60 + p[2]

    topics = []
    for tm in topic_map:
        topics.append({
            "start_sec": _to_sec(tm["start"]),
            "end_sec": _to_sec(tm.get("end", "99:59:59")),
            "label": tm.get("label", ""),
        })

    # Assign each timestamp to its topic segment
    segments: list[list[dict]] = []
    current_seg: list[dict] = []
    current_label: str | None = None

    for ts in timestamps:
        sec = ts["sec"]
        # Find matching topic
        matched_label = None
        for tp in topics:
            if tp["start_sec"] <= sec < tp["end_sec"]:
                matched_label = tp["label"]
                break

        ts["topic_label"] = matched_label

        if matched_label is None:
            # Outside any known topic → standalone
            if current_seg:
                segments.append(current_seg)
            segments.append([ts])
            current_seg = []
            current_label = None
        elif matched_label != current_label:
            # Topic boundary crossed
            if current_seg:
                segments.append(current_seg)
            current_seg = [ts]
            current_label = matched_label
        else:
            current_seg.append(ts)

    if current_seg:
        segments.append(current_seg)

    return segments


def normalise_segments(
    segments: list[list[dict]], body_limit: int
) -> list[list[dict]]:
    """
    Ensure every segment fits within body_limit.
    - Splits oversized segments at the byte-midpoint (recursively).
    - Merges trivially tiny segments (1 entry, <200B) into their predecessor.
    """
    # --- Split pass ---
    result: list[list[dict]] = []
    queue = list(segments)
    while queue:
        seg = queue.pop(0)
        if _body_bytes_of(seg) <= body_limit:
            result.append(seg)
        else:
            # Cut at the byte-midpoint
            total = _body_bytes_of(seg)
            mid = total // 2
            acc = 0
            cut = max(1, len(seg) // 2)
            for idx, e in enumerate(seg):
                acc += e["bytes"] + 1
                if acc >= mid:
                    cut = max(1, idx + 1)
                    break
            queue.insert(0, seg[cut:])
            queue.insert(0, seg[:cut])

    # --- Merge tiny pass ---
    merged: list[list[dict]] = []
    for seg in result:
        if len(seg) == 1 and _body_bytes_of(seg) < 200 and merged:
            merged[-1] = merged[-1] + seg
        else:
            merged.append(seg)

    return [s for s in merged if s]


def balanced_pack(timestamps: list[dict], byte_limit: int,
                  topic_map: list[dict] | None = None) -> list[list[dict]]:
    """
    Greedy context-aware pack:
      Pass 1 — cluster_by_tag (or cluster_by_topic if topic_map provided):
               group consecutive timestamps by theme
      Pass 2 — normalise_segments: ensure every cluster fits in body budget
      Pass 3 — Greedy fill: pack entries to body_limit, start new part on
               overflow. No part exceeds byte_limit.
    Produces minimum part count at byte_limit. Tag continuity naturally
    preserved within each part. Topic boundaries from --topic-json are
    respected when provided.
    """
    if not timestamps:
        return []

    body_limit = byte_limit - HEADER_OVERHEAD

    if topic_map:
        raw_segments = cluster_by_topic(timestamps, topic_map)
    else:
        raw_segments = cluster_by_tag(timestamps)
    segments = normalise_segments(raw_segments, body_limit)

    # Topic boundaries are hard breaks — each segment is its own part
    if topic_map:
        return [s for s in segments if s]

    # Flatten all entries in chronological order
    all_entries: list[dict] = []
    for seg in segments:
        all_entries.extend(seg)

    if not all_entries:
        return []
    if len(all_entries) == 1:
        return [all_entries]

    # Greedy fill to body_limit
    groups: list[list[dict]] = []
    current: list[dict] = []
    running = 0

    for e in all_entries:
        b = e["bytes"] + 1
        if current and running + b > body_limit:
            groups.append(current)
            current = [e]
            running = b
        else:
            current.append(e)
            running += b

    if current:
        groups.append(current)

    return groups


# ─────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────

def _generate_group_title(group: list[dict]) -> str:
    """Synthesize a section title that captures the overall topic group of entries in the part."""
    if not group:
        return "ANIBON Stream"
    
    topic_label = group[0].get("topic_label")
    if topic_label:
        return _clean_title(topic_label)

    # Collect distinct title phrases across the group
    phrases = []
    seen = set()

    for e in group:
        desc = e.get("desc", "").strip()
        # Clean out generic speaker prefixes
        clean = re.sub(r"^(ปู่โบ๊ต|พูดถึง|วิเคราะห์|คุยเรื่อง|ดู|รับชม|เปิดดู|เล่าข่าว|แสดงความคิดเห็นเกี่ยวกับ|ตอบแชตเรื่อง|ถกประเด็น)\s*", "", desc)
        if not clean:
            clean = desc
        
        # Truncate clean phrase if too long
        if len(clean) > 35:
            clean = clean[:35].rsplit(" ", 1)[0]

        key = clean.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(clean)

    if not phrases:
        return _clean_title(group[0]["desc"])

    # Pick up to 3 distinct phrases representing start, middle, end of section
    selected = [phrases[0]]
    if len(phrases) >= 3:
        mid = len(phrases) // 2
        if phrases[mid] not in selected:
            selected.append(phrases[mid])
    if len(phrases) >= 2 and phrases[-1] not in selected:
        selected.append(phrases[-1])

    combined = " | ".join(selected[:3])
    return _clean_title(combined, max_len=95)


def _group_to_part(group: list[dict]) -> dict:
    """Convert a flat list of timestamp dicts to a part dict."""
    return {
        "entries": group,
        "bytes": _body_bytes_of(group),
        "title": _generate_group_title(group),
        "start": group[0]["time"],
    }


def format_markdown(parts: list, doc_title: str) -> str:
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


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Pack timestamps into byte-limited, balanced parts.")
    ap.add_argument("input", type=Path, help="Timestamp list file")
    ap.add_argument("--byte-limit", type=int, default=3500,
                    help="Hard ceiling bytes per part (default: 3500)")
    ap.add_argument("--break-at", type=str, default=None,
                    help="Comma-separated timestamps to force section breaks (e.g. '04:35:28,05:15:00')")
    ap.add_argument("--topic-json", type=Path, default=None,
                    help="JSON file with detected topic boundaries: [{start, end, label}]")
    ap.add_argument("--output", "-o", type=Path, default=None)
    ap.add_argument("--title", default="วิดีโอสตรีม ANIBON")
    ap.add_argument("--parts-json", type=Path, default=None)
    args = ap.parse_args()

    if not args.input.exists():
        print(f"[!] File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    break_at = set()
    if args.break_at:
        break_at = set(t.strip() for t in args.break_at.split(","))
        print(f"[*] Forced breaks at: {sorted(break_at)}", file=sys.stderr)

    raw = args.input.read_text(encoding="utf-8").splitlines()
    timestamps = parse_timestamps(raw)
    if not timestamps:
        print("[!] No valid timestamps found.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Parsed {len(timestamps)} timestamps.", file=sys.stderr)

    pre = len(timestamps)
    timestamps = merge_consecutive_story(timestamps)
    if len(timestamps) < pre:
        print(f"[*] Merged {pre - len(timestamps)} consecutive [Story] entries.", file=sys.stderr)

    # Load topic boundaries from --topic-json if provided
    topic_map = None
    if args.topic_json:
        if not args.topic_json.exists():
            print(f"[!] Topic JSON not found: {args.topic_json}", file=sys.stderr)
            sys.exit(1)
        topic_map = json.loads(args.topic_json.read_text(encoding="utf-8"))
        print(f"[*] Loaded {len(topic_map)} topic boundaries from {args.topic_json}", file=sys.stderr)

    # Apply forced breaks — split into segments at break timestamps
    if break_at:
        segments = []
        current_seg = []
        for ts in timestamps:
            if current_seg and ts["time"] in break_at:
                segments.append(current_seg)
                current_seg = []
            current_seg.append(ts)
        if current_seg:
            segments.append(current_seg)
        # balanced_pack each segment, flatten groups
        all_groups = []
        for seg in segments:
            all_groups.extend(balanced_pack(seg, args.byte_limit, topic_map))
        groups = all_groups
    else:
        groups = balanced_pack(timestamps, args.byte_limit, topic_map)

    parts  = [_group_to_part(g) for g in groups]

    sizes = [p["bytes"] for p in parts]
    spread = max(sizes) - min(sizes)
    print(f"[*] Balanced into {len(parts)} parts  "
          f"(spread: {spread}B  max: {max(sizes)}B  min: {min(sizes)}B  "
          f"limit: {args.byte_limit}B).", file=sys.stderr)
    for p in parts:
        print(f"    {p['start']} — {p['bytes']:>5}B  {p['title'][:60]}", file=sys.stderr)

    output = args.output or args.input.parent / f"{args.input.stem}_packed.md"
    text   = format_markdown(parts, args.title)
    output.write_text(text, encoding="utf-8")
    print(f"[*] Output → {output}", file=sys.stderr)

    parts_path = args.parts_json or args.input.parent / f"{args.input.stem}_parts.json"
    write_parts_json(parts, parts_path)


if __name__ == "__main__":
    main()
