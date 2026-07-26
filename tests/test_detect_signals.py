#!/usr/bin/env python3
"""Self-check for detect_signals.py. No test framework."""
import json, sys, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from detect_signals import tokenize, compute_idf, chunk_signals, split_signal, jaccard, match_knowledge

errors = 0

def check(label, ok):
    global errors
    if ok:
        print(f"  PASS: {label}")
    else:
        print(f"  FAIL: {label}")
        errors += 1

# Test 1: Thai particle filtering
toks = tokenize("ครับ ผม FGO เลย นะ")
check("particle filtering", toks == ["ผม", "FGO"])

# Test 2: IDF rarity ordering
corpus = [
    {"name": "a", "tokens": ["FGO", "FGO", "กาชา"]},
    {"name": "b", "tokens": ["FGO", "AI", "AI"]},
]
idf = compute_idf(corpus)
check("IDF: FGO common -> lower IDF", idf["FGO"] < idf["กาชา"])
check("IDF: same rarity -> same IDF", idf["AI"] == idf["กาชา"])

# Test 3: TF-IDF ranks rare + frequent terms higher
# Solomon appears in 0 docs (idf=ln(2/1)=0.69) → passes idf>1 filter? No
# Let's use a term that IS rare enough
# Add a corpus with 10 docs where only 1 has "Solomon"
corpus3 = [{"name": f"chunk_{i}", "tokens": ["FGO"] if i < 9 else ["Solomon"]} for i in range(10)]
idf3 = compute_idf(corpus3)
check("IDF: Solomon rarer than FGO", idf3["Solomon"] > idf3["FGO"])
tokens3 = ["FGO", "FGO", "FGO", "FGO", "Solomon"]
scores3 = chunk_signals(tokens3, idf3, top_n=3)
terms3 = [t for t,_ in scores3]
check("TF-IDF: rare+repeated term (Solomon) in top 3", "Solomon" in terms3)

# Test 4: jaccard similarity
check("jaccard identical sets", jaccard({"a","b","c"}, {"a","b","c"}) == 1.0)
check("jaccard disjoint sets", jaccard({"a","b"}, {"c","d"}) == 0.0)
check("jaccard empty set", jaccard(set(), {"a"}) == 0.0)
check("jaccard half overlap", jaccard({"a","b"}, {"b","c"}) == 1/3)

# Test 5: split_signal returns at least one segment
items = [{"text": f"test word {i}"} for i in range(30)]
segs = split_signal(items, idf)
check("split_signal returns segments", len(segs) >= 1)

# Test 6: match_knowledge finds fgo-knowledge.md for "FGO"
terms = [("FGO", 0.5), ("test", 0.1)]
ref_dir = Path(__file__).resolve().parent.parent / "skills" / "anibon-timestamper" / "references"
matched = match_knowledge(terms, [str(ref_dir)])
fgo_match = any("fgo" in m.lower() for m in matched)
check("knowledge matching: FGO -> fgo-knowledge.md", fgo_match)

# Test 7: empty knowledge for unknown terms
terms_unknown = [("xyzzy_unknown", 0.5)]
matched_unknown = match_knowledge(terms_unknown, [str(ref_dir)])
check("knowledge matching: unknown term -> no match", len(matched_unknown) == 0)

# Test 8: short terms (< 3 chars) are ignored
terms_short = [("FG", 0.5)]
matched_short = match_knowledge(terms_short, [str(ref_dir)])
check("knowledge matching: short term ignored", len(matched_short) == 0)

print(f"\n{'ALL PASSED' if errors == 0 else f'{errors} FAILURES'}")
sys.exit(0 if errors == 0 else 1)
