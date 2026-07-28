#!/usr/bin/env python3
"""Detect topic boundaries between adjacent chunks using n-gram similarity + signal fallback.

Pipeline:
  1. Load chunks (JSON or XML) + signals.json
  2. For each adjacent pair: compute character 3-gram Jaccard similarity
  3. If similarity < SIM_THRESHOLD (0.3) AND at least one chunk has non-zero signal → mark boundary
  4. Fallback: if both chunks have flat (zero) signals, use start_sec gap > 600s as boundary
  5. Merge consecutive close boundaries (within 2 chunks)
  6. Output topics.json with {start, end, label} per section

Output topics.json:
  [
    {"start": "00:00:00", "end": "00:35:00", "label": "...(auto)"},
    {"start": "00:35:00", "end": "01:10:00", "label": "...(auto)"},
  ]

Usage:
    python detect_boundaries.py --chunks chunks/ --signals signals.json
        [--threshold 0.3] [--output topics.json] [--generate-labels]
"""
import re
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

# ── Config ──────────────────────────────────────────────────────────
SIM_THRESHOLD = 0.3       # Jaccard similarity below this = boundary
TIME_GAP_THRESHOLD = 600  # seconds: gap > this when signals flat = boundary
NGRAM_N = 3               # character n-gram size
MERGE_DISTANCE = 2        # merge boundaries within this many chunks
MIN_SECTION_CHUNKS = 3    # minimum chunks per section (ignore smaller sections)
DEFAULT_SECTION_CHUNKS = 6  # chunks per section when signals flat and no gap data


# ── Helpers ──────────────────────────────────────────────────────────

def _seconds_to_hms(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _chunk_sort_key(f: Path) -> int:
    try:
        return int(f.stem.split("_")[-1])
    except (ValueError, IndexError):
        return 0


def load_chunks(path: Path):
    """Yield (name, start_sec, text) for each chunk in directory.
    Supports JSON and XML formats. Prefers JSON.
    """
    p = Path(path)
    if not p.is_dir():
        # Single file
        if p.suffix == ".xml":
            yield _load_chunk_xml(p)
        else:
            yield _load_chunk_json(p)
        return

    candidates = sorted(p.glob("chunk_*.json"), key=_chunk_sort_key)
    fmt = "json"
    if not candidates:
        candidates = sorted(p.glob("chunk_*.xml"), key=_chunk_sort_key)
        fmt = "xml"

    loader = _load_chunk_xml if fmt == "xml" else _load_chunk_json
    for f in candidates:
        yield loader(f)


def _load_chunk_json(path: Path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    texts = [it.get("text", "").strip() for it in data.get("items", []) if it.get("text")]
    return path.stem, data.get("start_sec", 0), " ".join(texts)


def _load_chunk_xml(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    texts = []
    for item in root.iter("item"):
        t = (item.text or "").strip()
        if t:
            texts.append(t)
    start_sec = int(root.get("start_sec", 0))
    return path.stem, start_sec, " ".join(texts)


# ── N-gram similarity ────────────────────────────────────────────────

def _char_ngrams(text: str, n: int = NGRAM_N) -> set:
    """Generate character n-grams from lowercase text.
    Works correctly for both Thai and English text.
    """
    cleaned = text.lower()
    # Remove whitespace clusters for better cross-chunk comparison
    cleaned = re.sub(r"\s+", " ", cleaned)
    return {cleaned[i:i + n] for i in range(len(cleaned) - n + 1)}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Character n-gram Jaccard similarity between two texts.
    Value in [0, 1]. Higher = more similar.
    Works on Thai without word segmentation.
    """
    grams_a = _char_ngrams(text_a)
    grams_b = _char_ngrams(text_b)
    if not grams_a or not grams_b:
        return 0.0
    intersection = grams_a & grams_b
    union = grams_a | grams_b
    return len(intersection) / len(union)


# ── Signal loading ───────────────────────────────────────────────────

def load_signals(path: Path) -> dict:
    """Load signals.json. Returns the 'chunks' dict or whole data."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("chunks", data)


def _total_signal_score(signal: dict) -> int:
    """Sum of all signal scores for a chunk."""
    score = signal.get("signal_score", {})
    return sum(score.values())


def _dominant_game_signal(signal: dict) -> str:
    """Extract dominant game name from matched_files in signal."""
    files = signal.get("matched_files", [])
    if not files:
        return ""
    # Take the file with highest count, strip path to game name
    best = max(files, key=lambda f: f.get("count", 0))
    return best.get("file", "").replace(".md", "").split("/")[-1].replace("_", " ")


# ── Boundary detection ──────────────────────────────────────────────

def detect_boundaries(
    chunks: list,
    signals: dict,
    threshold: float = SIM_THRESHOLD,
    time_gap_threshold: int = TIME_GAP_THRESHOLD,
):
    """Detect topic boundaries between adjacent chunks.
    
    Args:
        chunks: list of (name, start_sec, text)
        signals: {chunk_name: {signal_score: {...}, matched_files: [...]}}
        threshold: similarity below this = boundary
        time_gap_threshold: start_sec gap above this = boundary (fallback)
    
    Returns:
        list of boundary indices (index = AFTER chunk_i, so boundary
        between chunk_i and chunk_i+1 is stored as i+1)
    """
    boundaries = []
    
    for i in range(len(chunks) - 1):
        name_a, start_a, text_a = chunks[i]
        name_b, start_b, text_b = chunks[i + 1]
        
        sig_a = signals.get(name_a, {})
        sig_b = signals.get(name_b, {})
        score_a = _total_signal_score(sig_a)
        score_b = _total_signal_score(sig_b)
        
        sim = jaccard_similarity(text_a, text_b)
        
        is_boundary = False
        reason = ""
        
        if score_a > 0 or score_b > 0:
            # At least one chunk has signal → use n-gram similarity
            if sim < threshold:
                is_boundary = True
                reason = f"sim={sim:.3f} < {threshold} (signal-based)"
        else:
            # Both chunks have flat (zero) signals → use time gap
            gap = start_b - start_a
            if gap > time_gap_threshold:
                is_boundary = True
                reason = f"gap={gap}s > {time_gap_threshold}s (flat-signal fallback)"
        
        if is_boundary:
            boundaries.append({
                "index": i + 1,
                "start_sec": start_b,  # boundary at start of next chunk
                "reason": reason,
                "sim": round(sim, 3),
            })
    
    # Merge boundaries within MERGE_DISTANCE chunks
    merged = []
    for b in boundaries:
        if merged and b["index"] - merged[-1]["index"] <= MERGE_DISTANCE:
            # Keep the later boundary (more conservative split)
            merged[-1] = b
        else:
            merged.append(b)
    
    return merged


# ── Section building ────────────────────────────────────────────────

def build_sections(
    chunks: list,
    boundaries: list,
    signals: dict,
    generate_labels: bool = False,
):
    """Build section list from chunk list and boundary indices.
    
    Returns:
        list of {start, end, label} dicts
    """
    sections = []
    boundary_indices = {b["index"] for b in boundaries}
    
    # If no boundaries detected even with fallback, use default chunking
    if not boundaries:
        for i in range(0, len(chunks), DEFAULT_SECTION_CHUNKS):
            end_idx = min(i + DEFAULT_SECTION_CHUNKS, len(chunks))
            chunk_a = chunks[i]
            chunk_end = chunks[end_idx - 1] if end_idx > i else chunk_a
            
            label = _make_label(chunks[i:end_idx], signals, generate_labels)
            sections.append({
                "start": _seconds_to_hms(chunk_a[1]),
                "end": _seconds_to_hms(chunk_end[1] + 300),  # +5min for chunk duration
                "label": label,
            })
        return sections
    
    # Build sections from boundaries
    current_start = chunks[0][1]
    current_start_name = chunks[0][0]
    section_chunks = []
    
    for i, (name, start_sec, text) in enumerate(chunks):
        section_chunks.append((name, start_sec, text))
        
        if i in boundary_indices:
            # End current section at this boundary
            prev_chunk = chunks[i - 1] if i > 0 else chunks[i]
            label = _make_label(section_chunks, signals, generate_labels)
            
            # Only add section if it meets minimum size
            if len(section_chunks) >= MIN_SECTION_CHUNKS:
                sections.append({
                    "start": _seconds_to_hms(current_start),
                    "end": _seconds_to_hms(start_sec),
                    "label": label,
                })
                current_start = start_sec
            
            section_chunks = []
    
    # Last section
    if section_chunks:
        label = _make_label(section_chunks, signals, generate_labels)
        end_sec = section_chunks[-1][1] + 300
        if len(section_chunks) >= MIN_SECTION_CHUNKS or not sections:
            sections.append({
                "start": _seconds_to_hms(current_start),
                "end": _seconds_to_hms(end_sec),
                "label": label,
            })
    
    # If no sections qualified (all too small), merge everything
    if not sections:
        label = _make_label(chunks, signals, generate_labels)
        sections.append({
            "start": _seconds_to_hms(chunks[0][1]),
            "end": _seconds_to_hms(chunks[-1][1] + 300),
            "label": label,
        })
    
    return sections


def _make_label(
    section_chunks: list,
    signals: dict,
    generate_labels: bool,
) -> str:
    """Generate a label for a section of chunks.
    
    If --generate-labels: dominant game + top keyword.
    Otherwise: "(auto) topic <N>".
    """
    if not generate_labels or not section_chunks:
        return "(auto)"
    
    # Collect specific game references (skills/reference/) vs generic stream types
    specific_games = Counter()
    generic_types = Counter()
    
    for name, _, _ in section_chunks:
        sig = signals.get(name, {})
        for mf in sig.get("matched_files", []):
            fpath = mf.get("file", "")
            cnt = mf.get("count", 0)
            if "skills/reference/" in fpath:
                # Game-specific knowledge file
                game = fpath.replace(".md", "").split("/")[-1]
                specific_games[game] += cnt
            elif "references/stream/" in fpath:
                # Generic stream type
                gtype = fpath.replace(".md", "").split("/")[-1]
                generic_types[gtype] += cnt
    
    # Build label
    parts = []
    if specific_games:
        dominant = specific_games.most_common(1)[0][0]
        parts.append(dominant.replace("_", " "))
    elif generic_types:
        # Fall back to most specific stream type (prefer non-gaming)
        preferred = [t for t in ["event-stream", "donation-classifier", "talk-stream",
                                  "story-enrichment", "gaming-stream"]
                     if t in generic_types]
        if preferred:
            parts.append(preferred[0].replace("-", " "))
        else:
            parts.append(generic_types.most_common(1)[0][0].replace("-", " "))
    
    return " | ".join(parts) if parts else "(auto)"


_STOPWORDS = {
    "ครับ", "ค่ะ", "นะคะ", "ครับผม", "อันนี้", "แบบนี้", "อย่างนี้",
    "แล้วก็", "คือว่า", "นี่คือ", "อะไร", "อย่างไร", "ทําไม", "เพราะว่า",
    "สําหรับ", "เกี่ยวกับ", "ระหว่าง", "หลังจาก", "ก่อนที่",
    "the", "this", "that", "and", "but", "for", "with", "from",
    "have", "been", "very", "just", "like", "will", "would",
}


# ── Main ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Detect topic boundaries between chunks.")
    ap.add_argument("--chunks", required=True,
                    help="Path to chunks directory")
    ap.add_argument("--signals", required=True,
                    help="Path to signals.json from detect_signals.py")
    ap.add_argument("--output", "-o", type=Path, default=None,
                    help="Output topics.json path (default: signals dir + topics.json)")
    ap.add_argument("--threshold", type=float, default=SIM_THRESHOLD,
                    help=f"N-gram Jaccard threshold (default: {SIM_THRESHOLD})")
    ap.add_argument("--generate-labels", action="store_true",
                    help="Auto-generate section labels from dominant game + keywords")
    ap.add_argument("--time-gap", type=int, default=TIME_GAP_THRESHOLD,
                    help=f"Time gap threshold for flat-signal fallback (default: {TIME_GAP_THRESHOLD}s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print boundaries without writing")
    args = ap.parse_args()

    chunks_path = Path(args.chunks).expanduser().resolve()
    signals_path = Path(args.signals).expanduser().resolve()

    if not chunks_path.exists():
        print(f"[!] Chunks not found: {chunks_path}", file=sys.stderr)
        sys.exit(1)
    if not signals_path.exists():
        print(f"[!] Signals not found: {signals_path}", file=sys.stderr)
        sys.exit(1)

    # Load
    chunks = list(load_chunks(chunks_path))
    signals = load_signals(signals_path)
    print(f"[*] Loaded {len(chunks)} chunks, {len(signals)} signal entries", file=sys.stderr)

    # Detect boundaries
    boundaries = detect_boundaries(
        chunks, signals,
        threshold=args.threshold,
        time_gap_threshold=args.time_gap,
    )
    print(f"[*] Found {len(boundaries)} topic boundaries", file=sys.stderr)

    # Build sections
    sections = build_sections(chunks, boundaries, signals, args.generate_labels)

    # Report
    print(f"[*] Built {len(sections)} sections:", file=sys.stderr)
    for s in sections:
        label_display = s["label"][:60] if s["label"] else "(no label)"
        print(f"    {s['start']} → {s['end']}: {label_display}", file=sys.stderr)

    if not sections:
        print("[!] No sections generated.", file=sys.stderr)
        sys.exit(0)

    # Write output
    if args.dry_run:
        print(json.dumps(sections, ensure_ascii=False, indent=2))
    else:
        output = args.output or signals_path.parent / "topics.json"
        output.write_text(
            json.dumps(sections, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[*] Output → {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
