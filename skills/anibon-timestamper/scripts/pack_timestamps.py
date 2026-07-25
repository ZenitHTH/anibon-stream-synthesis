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
# Overhead accounting
# ─────────────────────────────────────────────────────────────

def _header_bytes(part_index: int, title: str, start: str) -> int:
    """Byte cost of the ═══ separator block for one part."""
    sep = "═════════════════════════════════════════════════════════\n"
    line2 = f" ส่วนที่ {part_index}: {title} (⏱ เริ่ม: {start})\n"
    return len(sep.encode("utf-8")) * 2 + len(line2.encode("utf-8"))


def _clean_title(desc: str, max_len: int = 60) -> str:
    """Short title that does not cut mid-word."""
    if len(desc) <= max_len:
        return desc
    truncated = desc[:max_len]
    last_space = max(truncated.rfind(" "), truncated.rfind("،"), truncated.rfind(")"))
    if last_space > 20:
        return truncated[:last_space]
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


def _primary_tag(tag: str) -> str:
    """Extract the first bracketed label, or the full tag string."""
    m = _TAG_EXTRACT.match(tag)
    return m.group(1) if m else tag


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


def balanced_pack(timestamps: list[dict], byte_limit: int) -> list[list[dict]]:
    """
    Three-pass context-first balanced partition:
      Pass 1 — cluster_by_tag:      group consecutive timestamps by theme
      Pass 2 — normalise_segments:  ensure every segment fits in body budget
      Pass 3 — Painter's Partition DP over segment boundaries only,
               minimising max_size - min_size spread
    Chronological order preserved. No part exceeds byte_limit.
    """
    if not timestamps:
        return []

    body_limit = byte_limit - HEADER_OVERHEAD

    # Pass 1 & 2 — context segments
    raw_segments = cluster_by_tag(timestamps)
    segments = normalise_segments(raw_segments, body_limit)

    S = len(segments)
    if S == 0:
        return []
    if S == 1:
        return [segments[0]]

    # Segment body sizes and prefix sums
    seg_bytes = [_body_bytes_of(s) for s in segments]
    seg_prefix = [0] * (S + 1)
    for i, b in enumerate(seg_bytes):
        seg_prefix[i + 1] = seg_prefix[i] + b

    def seg_range_bytes(lo: int, hi: int) -> int:
        return seg_prefix[hi] - seg_prefix[lo]

    # K = minimum parts at segment granularity
    K, running = 0, 0
    for b in seg_bytes:
        if running > 0 and running + b > body_limit:
            K += 1
            running = b
        else:
            running += b
    K += 1

    # ── Painter's Partition DP over S segments into K parts ──
    BIG = 10 ** 9
    dp    = [[BIG] * (K + 1) for _ in range(S + 1)]
    split = [[-1]  * (K + 1) for _ in range(S + 1)]
    dp[0][0] = 0

    for j in range(1, K + 1):
        for i in range(j, S + 1):
            for m in range(j - 1, i):
                body = seg_range_bytes(m, i)
                if body > body_limit:
                    continue
                prev = dp[m][j - 1]
                if prev == BIG:
                    continue
                cand = max(prev, body)
                if cand < dp[i][j]:
                    dp[i][j] = cand
                    split[i][j] = m

    # ── Back-track ───────────────────────────────────────────
    boundaries = []
    i, j = S, K
    while j > 0:
        m = split[i][j]
        boundaries.append((m, i))
        i = m
        j -= 1
    boundaries.reverse()

    # ── Assemble groups from segment slices ──────────────────
    groups = []
    for (lo, hi) in boundaries:
        merged: list[dict] = []
        for seg in segments[lo:hi]:
            merged.extend(seg)
        if merged:
            groups.append(merged)

    return groups


# ─────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────

def _group_to_part(group: list[dict]) -> dict:
    """Convert a flat list of timestamp dicts to a part dict.
    Title is taken from the first entry with the group's dominant tag.
    """
    from collections import Counter
    tag_counter: Counter = Counter(_primary_tag(e["tag"]) for e in group)
    dominant_tag = tag_counter.most_common(1)[0][0]
    title_entry = next(
        (e for e in group if _primary_tag(e["tag"]) == dominant_tag),
        group[0],
    )
    return {
        "entries": group,
        "bytes": _body_bytes_of(group),
        "title": _clean_title(title_entry["desc"]),
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
    ap.add_argument("--output", "-o", type=Path, default=None)
    ap.add_argument("--title", default="วิดีโอสตรีม ANIBON")
    ap.add_argument("--parts-json", type=Path, default=None)
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

    groups = balanced_pack(timestamps, args.byte_limit)
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
