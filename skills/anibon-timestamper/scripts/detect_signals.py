#!/usr/bin/env python3
"""Detect topic signals in chunks → match knowledge files + auto-discover unknowns.

Pipeline:
  1. Load knowledge.json (keyword → file mapping)
  2. For each chunk: match known keywords → produce signals.json
  3. If --discover: find unknown high-freq words → web search → classify → add to knowledge.json
  4. If discoveries made: git commit knowledge.json

Usage:
  # Basic: match known keywords only
  python3 detect_signals.py --chunks ~/youtube_VFoRJ0YbxFw_workspace/chunks/ \
      --knowledge ~/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/knowledge.json \
      --output signals.json

  # With auto-discovery
  python3 detect_signals.py --chunks ... --knowledge ... --output signals.json --discover

  # Dry run (no writes, no git)
  python3 detect_signals.py --chunks ... --knowledge ... --output - --discover --dry-run

Knowledge JSON format:
  {
    "entries": {
      "keyword": {"kind": "game", "file": "skills/reference/Wuthering_Waves.md"},
      ...
    },
    "_discovered": {}
  }

Git: uses --git-dir from skill root. Only commits if changes made.
"""

import sys, json, os, re, time, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── config ─────────────────────────────────────────────────────────────
MIN_FREQ = 3          # min word freq in chunk to be discovery candidate
MIN_LEN = 4           # min word length for discovery
WIKI_DELAY = 1.0      # seconds between wiki API calls
CATEGORY_KEYWORDS = {
    "game": ["video game", "gacha", "rpg", "fps", "gaming", "console", "mobile game",
             "nintendo", "playstation", "xbox", "steam", "gameplay", "playable",
             "entertainment", "comic", "franchise", "game series", "dark souls",
             "battle royale", "gacha game", "open-world", "expansion", "dlc",
             "mmo", "strategy game", "simulation game", "role-playing", "fighting game",
             "video game series", "video game character", "game developer"],
    "anime": ["anime", "manga", "อนิเมะ", "มังงะ", "light novel",
              "anime series", "manga series", "voice actor",
              "episode", "television series", "ova", "shonen", "seinen",
              "series", "anime film", "japanese manga", "film series",
              "anime television", "chinese animation"],
    "character": ["character", "ตัวละคร", "fictional character", "video game character", "playable",
                  "main character", "villain", "hero", "protagonist", "antagonist"],
    "tokusatsu": ["tokusatsu", "kamen rider", "super sentai", "ultraman", "kaiju", "godzilla"],
}

# Words that should never trigger discovery (common words, fillers, noise)
STOPWORDS = set("""
a an the in on at to for of with by from as and or but not is are was were be been
has have had do does did will would could should may might can shall
this that these those it its they them their he him his she her we us our you your
all any each every some many few much more most such only own same
about above after again against during before between below beyond
here there where when why how what which who whom
just really very quite almost nearly already still even
also too well back down up off out over under
into onto upon within without through across around along
get got make made take took ive dont youre didnt thats
ive youre didnt thats theyre were not would could should
will shall need must maybe perhaps anyway
please thank thanks yes no ok okay hey hi hello
so then now here because but if though while
actually basically essentially literally probably maybe
thing things way ways case point part
kind sort type like gonna want need try
new old good bad big small long short high low
right wrong true false real sure mean
think know see go come say tell ask feel
look find show give take put set let help keep
use work play talk run move start stop
people person man woman child world life day year
time hour minute second week month
say says said tell told ask asked
think thought know knew see saw seen
go goes went gone come came
make made take took taken
called named known used based
able sorry
day days year years time times
life love hope hate fear joy sad
red blue green white black dark light
open close begin end start stop
early late fast slow hard soft
bigger smaller better worse
side top bottom front back
left right center middle
first second third next last
another other same different
always never sometimes often
soon later earlier already
still yet already
disc wing road wonder
bright flame storm blade frost
shadow steel iron gold silver
stone rock fire water wind
wind flame blade force
order chaos light dark
เอ่อ อ่า อือ ฮะ ฮ้า อืม เออ อิ อุ โอ๊ะ เห้ย เฮ้
ครับ ค่ะ คะ จ้า ฮะ ฮา นะ จ้ะ จ๊ะ
คือ ว่า ซึ่ง ที่ อัน โดย ตาม แต่ และ หรือ เพราะ หาก
เป็น อยู่ คือ มี ใช้ ไป มา ให้ ดู รู้ เห็น เอา
ได้ ถูก ต้อง เคย จะ กําลัง แล้ว เลย เอง กัน
ไม่ ใช่ ก็ ไง นะ ซิ สิ เถอะ เถิด
อย่าง แบบ เหมือน ราว  คล้าย เหมือนกับ
นี้ นั้น โน่น ไหน ใคร อะไร ทําไม อย่างไร
เลย มาก น้อย เร็ว ช้า ดี ร้าย ใหญ่ เล็ก ยาว สั้น สูง ต่ํา
""".strip().split())
WIKI_CACHE = {}       # word → result (avoid duplicate lookups)
# ── end config ─────────────────────────────────────────────────────────


def load_knowledge(path):
    """Load knowledge.json. Returns entries dict + _discovered dict."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", {}), data.get("_discovered", {})


def save_knowledge(path, entries, discovered):
    """Write knowledge.json, preserving version/updated fields."""
    # Load existing to preserve version/updated
    try:
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {"version": 2, "updated": "", "note": ""}
    
    existing["updated"] = time.strftime("%Y-%m-%d")
    existing["entries"] = dict(sorted(entries.items()))
    existing["_discovered"] = discovered
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return True


def _load_chunk_json(path: Path):
    """Load a single JSON chunk. Returns (name, start_sec, full_text)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    texts = [it.get("text", "").strip() for it in data.get("items", []) if it.get("text")]
    return path.stem, data.get("start_sec", 0), " ".join(texts)


def _load_chunk_xml(path: Path):
    """Load a single XML chunk. Returns (name, start_sec, full_text)."""
    tree = ET.parse(path)
    root = tree.getroot()
    texts = []
    for item in root.iter("item"):
        t = (item.text or "").strip()
        if t:
            texts.append(t)
    start_sec = int(root.get("start_sec", 0))
    return path.stem, start_sec, " ".join(texts)


def _chunk_sort_key(f: Path) -> int:
    """Extract chunk index from filename (chunk_03.json → 3)."""
    try:
        return int(f.stem.split("_")[-1])
    except (ValueError, IndexError):
        return 0


def load_chunks(path):
    """Yield (name, start_sec, full_text) for each chunk.

    Supports:
    - Directory of JSON files (preferred) or XML files
    - Single JSON or XML file
    - Mixed dir: ONLY one format (JSON wins if both exist)
    """
    p = Path(path)
    if p.is_file():
        if p.suffix == ".xml":
            yield _load_chunk_xml(p)
        else:
            yield _load_chunk_json(p)
        return

    # Prefer JSON; fall back to XML
    candidates = sorted(p.glob("chunk_*.json"), key=_chunk_sort_key)
    fmt = "json"
    if not candidates:
        candidates = sorted(p.glob("chunk_*.xml"), key=_chunk_sort_key)
        fmt = "xml"

    loader = _load_chunk_xml if fmt == "xml" else _load_chunk_json
    for f in candidates:
        yield loader(f)


def tokenize(text):
    """Simple word tokenizer. Extracts alphanumeric + Thai words."""
    # Match English words, Thai words, numbers
    tokens = re.findall(r"[\u0e00-\u0e7f]+|[a-zA-Z][a-zA-Z0-9'_-]*", text.lower())
    return [t for t in tokens if len(t) >= 2]


def extract_candidates(chunk_text):
    """Extract potential discovery candidates: high-freq words not in entries."""
    tokens = tokenize(chunk_text)
    freq = Counter(tokens)
    
    candidates = []
    for word, count in freq.items():
        if len(word) >= MIN_LEN and count >= MIN_FREQ and word not in STOPWORDS:
            candidates.append((word, count))
    
    return sorted(candidates, key=lambda x: -x[1])


class WikiClassifier:
    """Wikipedia-based word classifier. Caches results."""
    
    def __init__(self, delay=WIKI_DELAY):
        self.delay = delay
        self.last_call = 0
    
    def classify(self, word):
        """Search Wikipedia → return (category, confidence, snippet) or None."""
        if not word:
            return None
        word_lower = word.lower()
        
        # Check cache
        if word_lower in WIKI_CACHE:
            return WIKI_CACHE[word_lower]
        
        # Try English wiki first, then Thai
        result = self._search_wikipedia(word_lower, "en")
        if not result or result[2] == "":
            result = self._search_wikipedia(word_lower, "th")
        
        WIKI_CACHE[word_lower] = result
        return result
    
    def _search_wikipedia(self, word, lang="en"):
        """Search Wikipedia API → (category, confidence, snippet) or None."""
        # Rate limit
        now = time.time()
        if now - self.last_call < self.delay:
            time.sleep(self.delay - (now - self.last_call))
        self.last_call = time.time()
        
        params = {
            "action": "query",
            "list": "search",
            "srsearch": word,
            "srlimit": 5,
            "format": "json",
            "utf8": 1,
        }
        import urllib.parse
        url = f"https://{lang}.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"
        
        try:
            req = Request(url, headers={"User-Agent": "detect_signals/1.0"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            results = data.get("query", {}).get("search", [])
            if not results:
                return None
            
            # Skip disambiguation pages (generic words)
            non_disambig = [r for r in results 
                          if "(disambiguation)" not in r.get("title", "").lower()]
            if non_disambig:
                results = non_disambig
            
            # Combine snippets from top results
            full_snippet = " ".join(r.get("snippet", "") for r in results[:5])
            full_snippet = re.sub(r"<[^>]+>", "", full_snippet)
            
            # Extract titles for stronger signal
            titles = [r.get("title", "") for r in results[:5]]
            
            # Classify using titles + snippets
            category = self._categorize(titles, full_snippet, word)
            if category:
                return (category, 0.7, full_snippet[:300])
            
            return None
        except (URLError, HTTPError, OSError, json.JSONDecodeError):
            return None
    
    def _categorize(self, titles, snippet, word):
        """Classify word using Wikipedia titles + snippet.
        
        STRONG signal: title has "(video game)", "(anime)", "(character)" suffix.
        WEAK signal: snippet mentions game/anime near the searched word.
        Returns category (str) or None.
        """
        snippet_lower = snippet.lower()
        word_lower = word.lower()
        word_variants = {word_lower, word_lower + 's', word_lower.rstrip('s')}
        
        # ── Phase 1: Title suffix check (strongest signal) ──
        for title in titles:
            tl = title.lower()
            if "(video game)" in tl or "(game)" in tl or "video game" in tl:
                return "game"
            if "(anime)" in tl or "(tv series)" in tl or "(manga)" in tl:
                return "anime"
            if "(character)" in tl:
                return "character"
        
        # ── Phase 2: Check if word appears as whole word in snippet ──
        if not any(re.search(r'(?<![a-z])' + re.escape(v) + r'(?![a-z])', snippet_lower) 
                   for v in word_variants if v):
            return None
        
        # ── Phase 3: Snippet proximity analysis ──
        # Check if category keywords appear near the searched word
        kw_patterns = {cat: [re.compile(re.escape(kw), re.IGNORECASE) for kw in kws]
                      for cat, kws in CATEGORY_KEYWORDS.items()}
        word_pattern = re.compile(r'(?<![a-z])(' + '|'.join(re.escape(v) for v in word_variants if v) + r')(?![a-z])')
        
        # Find all word positions
        word_positions = [m.start() for m in word_pattern.finditer(snippet_lower)]
        
        scores = {}
        for cat, patterns in kw_patterns.items():
            score = 0
            for pat in patterns:
                for m in pat.finditer(snippet_lower):
                    kw_pos = m.start()
                    # Find nearest word position
                    closest = min((abs(kw_pos - wp) for wp in word_positions), default=999)
                    if closest < 120:
                        score += 3
                    elif closest < 400:
                        score += 2
                    else:
                        score += 1
            if score > 0:
                scores[cat] = score
        
        if not scores:
            return None
        
        # Check if this is a generic word (exact title match, common concept)
        is_generic = any(tl == word_lower or tl == word_lower + 's' 
                        for tl in (t.lower() for t in titles))
        
        best_cat = max(scores, key=scores.get)
        best_score = scores[best_cat]
        
        # Stricter threshold for generic words
        min_score = 4 if is_generic else 3
        if best_score < min_score:
            return None
        
        return best_cat


def match_chunk(chunk_text, entries):
    """Match chunk text against knowledge entries. Returns (kind_counts, files_to_inject)."""
    text_lower = chunk_text.lower()
    tokens = tokenize(chunk_text)
    
    matched = {}  # file → count
    matched_kinds = Counter()  # kind → count
    
    # Check each keyword (fast for dict with 100-200 entries)
    for keyword, info in entries.items():
        if keyword in text_lower:
            filepath = info.get("file")
            kind = info.get("kind", "unknown")
            if filepath:
                matched[filepath] = matched.get(filepath, 0) + 1
                matched_kinds[kind] += 1
    
    return matched, matched_kinds


def format_signals(matched, matched_kinds):
    """Format match info into output structure."""
    # Sort by match count (highest first)
    sorted_files = sorted(matched.items(), key=lambda x: -x[1])
    
    return {
        "matched_files": [{"file": f, "count": c} for f, c in sorted_files],
        "signal_score": {
            "game": matched_kinds.get("game", 0),
            "anime": matched_kinds.get("anime", 0),
            "stream_type": matched_kinds.get("stream_type", 0),
            "domain": matched_kinds.get("domain", 0),
        }
    }


def git_commit(dry_run=False):
    """Git add + commit knowledge.json if changes exist."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "knowledge.json"],
            capture_output=True, text=True, timeout=10,
        )
        if not result.stdout.strip():
            return False  # no changes
        
        if dry_run:
            print("  [git] would commit knowledge.json (dry run)", file=sys.stderr)
            return True
        
        subprocess.run(["git", "add", "knowledge.json"], check=True, timeout=10)
        
        # Count new entries
        subprocess.run(
            ["git", "commit", "-m", "auto-discover: new signals from stream analysis"],
            check=True, timeout=30,
        )
        print("  [git] committed knowledge.json", file=sys.stderr)
        return True
    except subprocess.TimeoutExpired:
        print("  [git] timeout", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"  [git] error: {e}", file=sys.stderr)
        return False


def discover_parallel(unknown_words, workers=8, delay=0.2):
    """Classify unknown words in parallel via Wikipedia API.
    
    Returns: {word: (category, confidence, snippet)}
    """
    classifier = WikiClassifier(delay=delay)
    results = {}
    
    # Use thread pool for parallel web lookups
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(classifier.classify, w): w for w in unknown_words}
        for future in as_completed(futures):
            word = futures[future]
            try:
                result = future.result()
                if result:
                    cat, conf, snippet = result
                    results[word] = result
                    print(f"  [discover] '{word}' → {cat} (conf={conf})", file=sys.stderr)
            except Exception as e:
                pass  # skip failed lookups
    
    return results


def main():
    import argparse
    ap = argparse.ArgumentParser(
        prog="detect_signals",
        description="Match chunk topics to knowledge files. Optionally discover unknown words via web."
    )
    ap.add_argument("--chunks", required=True, help="Path to chunks dir or single chunk JSON")
    ap.add_argument("--knowledge", required=True, help="Path to knowledge.json")
    ap.add_argument("--output", default="-", help="Output path for signals.json ('-' for stdout)")
    ap.add_argument("--git-dir", help="Git repo root (default: same dir as knowledge.json)")
    ap.add_argument("--discover", action="store_true", help="Enable web discovery of unknown words")
    ap.add_argument("--dry-run", action="store_true", help="No file writes, no git commit")
    ap.add_argument("--threshold", type=int, default=1, help="Min keyword mentions to include a knowledge file")
    ap.add_argument("--workers", type=int, default=8, help="Parallel workers for web discovery (default=8)")
    args = ap.parse_args()
    
    # Resolve paths
    knowledge_path = Path(args.knowledge).expanduser().resolve()
    chunks_path = Path(args.chunks).expanduser().resolve()
    git_root = Path(args.git_dir).expanduser().resolve() if args.git_dir else knowledge_path.parent
    
    # Load knowledge
    if not knowledge_path.exists():
        print(f"Error: knowledge.json not found at {knowledge_path}", file=sys.stderr)
        sys.exit(1)
    
    entries, discovered = load_knowledge(knowledge_path)
    print(f"Loaded {len(entries)} entries, {len(discovered)} discovered", file=sys.stderr)
    
    # ── Phase 1: Load chunks + match known signals (sequential, fast) ──
    print("Phase 1: Matching known keywords...", file=sys.stderr)
    chunk_data = []  # (name, start_sec, text) for each chunk
    results = {}
    total_matched = 0
    global_candidates = set()  # unique candidate words across all chunks
    
    for chunk_name, start_sec, chunk_text in load_chunks(chunks_path):
        chunk_data.append((chunk_name, start_sec, chunk_text))
        
        matched, matched_kinds = match_chunk(chunk_text, entries)
        result = format_signals(matched, matched_kinds)
        results[chunk_name] = result
        if matched:
            total_matched += 1
        
        # Collect discovery candidates
        if args.discover:
            cands = extract_candidates(chunk_text)
            unknown = [w for w, c in cands if w not in entries and w not in discovered]
            global_candidates.update(unknown)
    
    print(f"  {len(chunk_data)} chunks, {total_matched} with signals", file=sys.stderr)
    
    # ── Phase 2: Parallel web discovery ──
    new_entries = {}
    if args.discover and global_candidates:
        print(f"Phase 2: Web discovery for {len(global_candidates)} unique candidates ({args.workers} workers)...",
              file=sys.stderr)
        
        discovered_map = discover_parallel(
            list(global_candidates)[:50],  # cap at 50 per run
            workers=args.workers,
            delay=0.2  # shorter delay with parallel workers
        )
        
        for word, (category, confidence, snippet) in discovered_map.items():
            new_entries[word] = {
                "kind": category,
                "file": None,
                "_discovered_by": "web",
                "_confidence": confidence,
                "_snippet": snippet[:150],
                "_added": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
    
    # ── Phase 3: Write output ──
    output = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chunks_processed": len(results),
        "chunks_with_signals": total_matched,
        "discover_enabled": args.discover,
        "discoveries": len(new_entries),
        "chunks": results,
    }
    
    if args.output == "-":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Wrote signals to {out_path}", file=sys.stderr)
    
    # ── Update knowledge.json + git commit ──
    if new_entries and not args.dry_run:
        entries.update(new_entries)
        discovered.update(new_entries)
        save_knowledge(knowledge_path, entries, discovered)
        print(f"Added {len(new_entries)} new words to {knowledge_path}", file=sys.stderr)
        
        try:
            subprocess.run(
                ["git", "-C", str(git_root), "add", "knowledge.json"],
                check=True, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "-C", str(git_root), "commit", "-m",
                 f"auto-discover: {len(new_entries)} new signal words"],
                check=True, capture_output=True, timeout=30,
            )
            print(f"  committed to git", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            print(f"  git: {e.stderr.decode() if e.stderr else e}", file=sys.stderr)
    elif new_entries and args.dry_run:
        print(f"[dry-run] would add {len(new_entries)} new entries + git commit", file=sys.stderr)
        for word, info in new_entries.items():
            print(f"  {word} → {info['kind']}", file=sys.stderr)
    
    # Summary
    print(f"\nSummary: {len(results)} chunks, {total_matched} with signals, "
          f"{len(new_entries)} discoveries", file=sys.stderr)


if __name__ == "__main__":
    main()
