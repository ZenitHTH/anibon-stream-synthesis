#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit a merged timestamp list for time gaps.

Enforces the SKILL.md "NO GAPS" iron rule (max N min between timestamps
unless verified silent). Prints each gap over the threshold plus the
chunk(s) covering it, so the orchestrator knows which chunk to re-spawn
a fill agent for. Exit 0 = no gaps, 1 = gaps found.
"""

import sys, re, argparse
from pathlib import Path

LINE_RE = re.compile(r"^(\d\d):(\d\d):(\d\d)\s*-")


def _sec(h: int, m: int, s: int) -> int:
    return h * 3600 + m * 60 + s


def parse_timestamps(text: str):
    """Return sorted [(seconds, line), ...] from timestamp lines."""
    out = []
    for ln in text.splitlines():
        m = LINE_RE.match(ln.strip())
        if m:
            h, mi, s = map(int, m.groups())
            out.append((_sec(h, mi, s), ln.strip()))
    out.sort(key=lambda x: x[0])
    return out


def find_gaps(ts, max_gap_sec=600):
    """Return [(gap_sec, prev_line, next_line)] for gaps over threshold."""
    gaps = []
    for i in range(1, len(ts)):
        g = ts[i][0] - ts[i - 1][0]
        if g > max_gap_sec:
            gaps.append((g, ts[i - 1][1], ts[i][1]))
    return gaps


def chunk_for_ts(ts_str: str, chunk_span_sec: int = 300) -> str:
    """Map an HH:MM:SS to the chunk id covering it (start = n*span)."""
    m = LINE_RE.match(ts_str)
    h, mi, s = map(int, m.groups())
    return f"chunk_{_sec(h, mi, s) // chunk_span_sec:02d}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="merged timestamp list file (merge_timestamps.py output)")
    ap.add_argument("--max-gap", type=int, default=600,
                    help="max allowed seconds between timestamps (default 600 = 10 min)")
    ap.add_argument("--chunk-span", type=int, default=300,
                    help="seconds per transcript chunk, for gap->chunk mapping (default 300)")
    ap.add_argument("--chunks-dir", help="optional: verify suggested chunk exists (glob chunk_*.xml)")
    args = ap.parse_args(argv)

    text = Path(args.input).read_text(encoding="utf-8")
    ts = parse_timestamps(text)
    if len(ts) < 2:
        print(f"Only {len(ts)} timestamp(s) found in {args.input}.")
        return 0

    gaps = find_gaps(ts, args.max_gap)
    if not gaps:
        print(f"✅ No gaps > {args.max_gap // 60} min. ({len(ts)} stamps checked)")
        return 0

    print(f"⚠️  {len(gaps)} gap(s) over {args.max_gap // 60} min found:")
    for g, prev, nxt in gaps:
        lo = prev[:8]
        hi = nxt[:8]
        nxt_c = chunk_for_ts(nxt, args.chunk_span)
        print(f"  {g // 60:3d}m  {lo} -> {hi}  (fill around {nxt_c})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
