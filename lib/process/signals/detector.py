#!/usr/bin/env python3
"""Signal detector and domain knowledge resolver for anibon-stream-synthesis.

Shared library module providing:
- Two-stage domain and game identification (Stage 1 franchise/special words vs Stage 2 scoped characters)
- Temporal chaining weights across sequential chunks
- Corpus-level IDF keyword scoring
- Phonetic entity normalization and noise cleaning
- Metadata ingestion from stream info.json
"""
from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Optional

from common.cleaner import compile_mapping_entries
from common.resources import plugin_root, resource_path
from process.signals.constants import (
    AMBIGUOUS_SINGLE_TOKENS,
    ANIME_INSTRUCTION_BLOCK,
    ANIME_TAGS,
    COMMON_CHARACTER_NAMES_BLACKLIST,
    DUPE_TIER_RE,
    EXTENDED_CHAR_REPEAT_RE,
    GAME_SPECIAL_WORDS,
    GAMING_INSTRUCTION_BLOCK,
    GAMING_MATCH_MARKERS,
    GAMING_TAGS,
    GENERIC_GAMING_STANDING_WORDS,
    MULTI_SPACE_RE,
    MUSIC_NOTES_RE,
    NOISE_BRACKET_RE,
    SPEAKER_MARKER_RE,
    SPECIFIC_KINDS,
    SPECIFIC_TOKU_KEYWORDS,
    STAGE1_BLOCKED_EXTRA,
    TALK_INSTRUCTION_BLOCK,
    TALK_TAGS,
    TOKUSATSU_INSTRUCTION_BLOCK,
    TOKUSATSU_TAGS,
    _EXTENDED_CHAR_REPEAT_RE,
    _MULTI_SPACE_RE,
    _MUSIC_NOTES_RE,
    _NOISE_BRACKET_RE,
    _SPEAKER_MARKER_RE,
)

# ── Resource Loaders ───────────────────────────────────────────────────────


def load_knowledge(knowledge_path: Optional[Path] = None) -> dict:
    """Load knowledge.json entries mapping keywords -> domain files."""
    p = knowledge_path if (knowledge_path and Path(knowledge_path).exists()) else resource_path("knowledge.json")
    if not p or not Path(p).exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", {})


def load_mappings(mappings_path: Optional[Path] = None) -> list[dict]:
    """Load phonetic entity mappings from default_mappings.json."""
    p = mappings_path if (mappings_path and Path(mappings_path).exists()) else resource_path("default_mappings.json")
    if not p or not Path(p).exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


def load_garbled_replacements(path: Optional[Path] = None) -> list[dict]:
    """Load confirmed ground-truth corrections from garbled_replacements.json."""
    p = path if (path and Path(path).exists()) else resource_path("garbled_replacements.json")
    if not p or not Path(p).exists():
        return []

    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    mappings_dict = data.get("mappings", {})
    result = []
    if isinstance(mappings_dict, dict):
        for correct, garbled_variants in mappings_dict.items():
            if isinstance(garbled_variants, list) and garbled_variants:
                result.append({"correct": correct, "patterns": garbled_variants})
            elif isinstance(garbled_variants, str):
                result.append({"correct": garbled_variants, "patterns": [correct]})

    for k, v in data.items():
        if k in ("version", "description", "note", "mappings", "replacements"):
            continue
        if isinstance(v, str):
            result.append({"correct": v, "patterns": [k]})
        elif isinstance(v, list) and v:
            result.append({"correct": k, "patterns": v})

    return result


# ── Text Cleaning & Normalization ──────────────────────────────────────────


def clean_transcript_noise(text: str) -> str:
    """Clean ASR artifacts, non-speech sound tags, speaker markers, and character loops."""
    if not text:
        return ""

    cleaned = SPEAKER_MARKER_RE.sub(" ", text)
    cleaned = NOISE_BRACKET_RE.sub(" ", cleaned)
    cleaned = MUSIC_NOTES_RE.sub(" ", cleaned)
    cleaned = EXTENDED_CHAR_REPEAT_RE.sub(r"\1\1\1", cleaned)
    return MULTI_SPACE_RE.sub(" ", cleaned).strip()


_get_compiled_mappings = compile_mapping_entries


def normalize_transcript(text: str, mappings: list[dict]) -> str:
    """Normalize phonetically garbled names and clean noise in transcript text."""
    if not text:
        return ""

    normalized = clean_transcript_noise(text)
    if not mappings:
        return normalized

    for pattern, replacement in _get_compiled_mappings(mappings):
        normalized = pattern.sub(replacement, normalized)
    return normalized


def filter_standing_gaming_words(text: str) -> tuple[str, list[str]]:
    """Extract and strip generic gaming standing words and dupe/eidolon tier codes from text.

    Returns (cleaned_text, detected_standing_words).
    """
    found_standing = []
    # 1. Dupe tier codes (C0-C6, E0-E6, 3-6 ดาว, etc.)
    for m in DUPE_TIER_RE.finditer(text):
        found_standing.append(m.group(0).lower().strip())
    cleaned = DUPE_TIER_RE.sub(" ", text)

    # 2. Generic gaming vocabulary
    for gw in sorted(GENERIC_GAMING_STANDING_WORDS, key=len, reverse=True):
        pattern = (
            re.compile(rf"\b{re.escape(gw)}\b", re.IGNORECASE)
            if re.search(r"^[a-zA-Z0-9]+$", gw)
            else re.compile(rf"{re.escape(gw)}", re.IGNORECASE)
        )
        if pattern.search(cleaned):
            found_standing.append(gw.lower())
            cleaned = pattern.sub(" ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, list(dict.fromkeys(found_standing))


def extract_chunk_text(path: Path) -> tuple[int, str]:
    """Extract (start_sec, clean_text) from a chunk file (.txt, .json, or .xml)."""
    text = ""
    start_sec = 0

    if path.suffix == ".txt":
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        m = re.search(r"\((\d{2}):(\d{2}):(\d{2})\)", raw)
        if m:
            start_sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        text = re.sub(r"\(\d{2}:\d{2}:\d{2}\)", "", raw)

    elif path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        start_sec = int(data.get("start_sec", 0))
        text = " ".join(it.get("text", "").strip() for it in data.get("items", []) if it.get("text"))

    elif path.suffix == ".xml":
        tree = ET.parse(path)
        root = tree.getroot()
        start_sec = int(root.get("start_sec", 0))
        text = " ".join((it.text or "").strip() for it in root.iter("item") if it.text)

    clean_text = clean_transcript_noise(text)
    return start_sec, clean_text


# ── Domain & Metadata Discovery ───────────────────────────────────────────


def discover_reference_games(refs_dir: Optional[Path] = None) -> dict[str, str]:
    """Scan markdown knowledge files and return mapping of lowercase keywords -> relative file path."""
    if refs_dir is None:
        refs_dir = plugin_root() / "skills" / "anibon-world-identity" / "references"
        if not refs_dir or not refs_dir.is_dir():
            script_dir = Path(__file__).resolve().parent
            refs_dir = script_dir.parent.parent / "skills" / "anibon-world-identity" / "references"
    if not refs_dir or not refs_dir.is_dir():
        return {}

    discovered = {}
    for f in refs_dir.glob("*.md"):
        if f.name.upper() in ("INDEX.MD", "README.MD"):
            continue
        stem = f.stem.lower()
        clean_name = stem.replace("_", " ")
        rel_path = f"../anibon-world-identity/references/{f.name}"

        # Full filename phrase (if not ambiguous)
        if clean_name not in AMBIGUOUS_SINGLE_TOKENS:
            discovered[clean_name] = rel_path

        tokens = clean_name.split()
        if len(tokens) > 1:
            first_tok = tokens[0]
            if first_tok not in AMBIGUOUS_SINGLE_TOKENS and len(first_tok) >= 4:
                discovered[first_tok] = rel_path

        # Register GAME_SPECIAL_WORDS
        if f.name in GAME_SPECIAL_WORDS:
            for special in GAME_SPECIAL_WORDS[f.name]:
                discovered[special.lower()] = rel_path

    # Register global stream/db special words that don't live in refs_dir directly
    for target_key, words in GAME_SPECIAL_WORDS.items():
        if target_key.startswith("references/stream/") or target_key.startswith("../"):
            for special in words:
                discovered[special.lower()] = target_key

    # Strip blocked single tokens, common character names, and generic words from Stage 1
    blocked_stage1 = AMBIGUOUS_SINGLE_TOKENS | COMMON_CHARACTER_NAMES_BLACKLIST | GENERIC_GAMING_STANDING_WORDS
    for blocked in list(discovered.keys()):
        if blocked in blocked_stage1 or any(blocked == b.lower() for b in blocked_stage1):
            discovered.pop(blocked, None)

    return discovered


def is_rule_doc(path: Path) -> bool:
    """Check if file is a rule/style document that shouldn't be treated as a game candidate."""
    s = str(path).replace("\\", "/").lower()
    if "references/stream" in s:
        if not s.endswith("-knowledge.md"):
            return True
    return False


def extract_metadata_signals(workspace: Path) -> dict[str, float]:
    """Extract game and topic keywords from YouTube stream metadata (info.json / video_info.json)."""
    candidates = [
        workspace / "info.json",
        workspace / "video_info.json",
    ]
    p = next((c for c in candidates if c.is_file()), None)
    if not p:
        for f in workspace.glob("*.info.json"):
            p = f
            break
    if not p or not p.is_file():
        return {}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

    text_parts = [
        data.get("title", ""),
        data.get("description", ""),
        " ".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else "",
    ]
    combined = " ".join(text_parts).lower()

    signals = {}
    for token in re.findall(r"[a-zA-Z0-9\u0E00-\u0E7F]+", combined):
        t_l = token.lower()
        if len(t_l) >= 3 or t_l in ("fgo", "czn", "ygo", "lol"):
            signals[t_l] = signals.get(t_l, 0.0) + 1.0

    return signals


# ── Signal Detection Pipeline Helpers ─────────────────────────────────────


def prune_stage1_entries(entries: dict) -> dict:
    """Prune common character names, generic standing words, and ambiguous tokens from Stage 1."""
    stage1_blocked = (
        COMMON_CHARACTER_NAMES_BLACKLIST |
        AMBIGUOUS_SINGLE_TOKENS |
        GENERIC_GAMING_STANDING_WORDS |
        STAGE1_BLOCKED_EXTRA
    )
    return {
        kw: meta for kw, meta in entries.items()
        if kw.lower() not in stage1_blocked and not any(kw.lower() == b.lower() for b in stage1_blocked)
    }


def build_pruned_entries(knowledge_path: Optional[Path] = None) -> dict:
    """Build and prune knowledge entries merged with dynamically discovered game references."""
    entries = load_knowledge(knowledge_path) or {}
    for kw, ref_file in discover_reference_games().items():
        if kw not in entries:
            entries[kw] = {"kind": "game", "file": ref_file}
    return prune_stage1_entries(entries)


def discover_workspace_chunks(chunks_dir: Path) -> list[dict]:
    """Find, sort, extract, and standing-word-filter all chunks in workspace/chunks."""
    def sort_key(p: Path) -> int:
        m = re.search(r"chunk_(\d+)", p.stem)
        return int(m.group(1)) if m else 0

    chunk_files = sorted(
        list(chunks_dir.glob("chunk_*.txt")) or
        list(chunks_dir.glob("chunk_*.json")) or
        list(chunks_dir.glob("chunk_*.xml")),
        key=sort_key,
    )
    loaded = []
    for cf in chunk_files:
        start_sec, raw_text = extract_chunk_text(cf)
        filtered_text, standing_kws = filter_standing_gaming_words(raw_text.lower())
        loaded.append({
            "id": cf.stem,
            "path": cf,
            "start_sec": start_sec,
            "raw_text": raw_text.lower(),
            "filtered_text": filtered_text,
            "standing_kws": standing_kws,
        })
    return loaded


def compute_chunk_idf_weights(loaded_chunks: list[dict], entries: dict) -> tuple[dict[str, int], dict[str, float]]:
    """Compute corpus-level Document Frequency (df) and smoothed IDF weights for chunk texts."""
    n_chunks = len(loaded_chunks)
    df_counts = {}
    for kw in entries:
        kw_l = kw.lower()
        count = sum(1 for c in loaded_chunks if kw_l in c["filtered_text"])
        if count > 0:
            df_counts[kw_l] = count

    idf_weights = {
        kw_l: math.log((n_chunks + 1.0) / (df + 0.5)) + 1.0
        for kw_l, df in df_counts.items()
    }
    return df_counts, idf_weights


def seed_metadata_chained_weights(meta_signals: dict[str, float], entries: dict) -> dict[str, float]:
    """Seed initial chained game weights from stream metadata signals (* 15.0 multiplier)."""
    chained_game_weights: dict[str, float] = {}
    for mkw, mscore in meta_signals.items():
        mkw_l = mkw.lower()
        for ekw, emeta in entries.items():
            if ekw.lower() == mkw_l and emeta.get("file"):
                if emeta.get("kind") in SPECIFIC_KINDS:
                    f_ref = emeta["file"]
                    if not is_rule_doc(Path(f_ref)):
                        chained_game_weights[f_ref] = chained_game_weights.get(f_ref, 0.0) + mscore * 15.0
    return chained_game_weights


def _score_chunk_keywords(
    text: str,
    entries: dict,
    df_counts: dict[str, int],
    idf_weights: dict[str, float],
) -> tuple[dict[str, float], dict[str, dict], list[str]]:
    """Match keywords in chunk text and calculate raw domain scores and special keywords."""
    raw_scores: dict[str, float] = {}
    matched: dict[str, dict] = {}
    special_kws: list[str] = []

    for kw, meta in entries.items():
        kw_l = kw.lower()
        if kw_l in df_counts and kw_l in text:
            occurrences = text.count(kw_l)
            weight = idf_weights.get(kw_l, 1.0)
            score = occurrences * weight
            kind = meta.get("kind", "topic")
            file_ref = meta.get("file")

            matched[kw] = {
                "count": occurrences,
                "kind": kind,
                "file": file_ref,
                "weight": round(weight, 4),
            }

            if file_ref and kind in SPECIFIC_KINDS and not is_rule_doc(Path(file_ref)):
                raw_scores[file_ref] = raw_scores.get(file_ref, 0.0) + score
                special_kws.append(kw)

    return raw_scores, matched, special_kws


def _rank_chained_candidates(
    chained_weights: dict[str, float],
) -> tuple[list[dict], Optional[str], float, str]:
    """Rank active candidate files, calculate probabilities, and determine best file and primary topic."""
    active = [(f, w) for f, w in chained_weights.items() if w > 0.01]
    sorted_cand = sorted(active, key=lambda x: x[1], reverse=True)
    total_w = sum(w for _, w in sorted_cand)

    ranked = []
    for f_name, w_val in sorted_cand:
        prob = round(w_val / total_w, 4) if total_w > 0 else 0.0
        ranked.append({"file": f_name, "weight": round(w_val, 4), "prob": prob})

    best_cand = ranked[0] if ranked else None
    best_file = best_cand["file"] if best_cand else None
    confidence = best_cand["prob"] if best_cand else 0.0

    primary_topic = ""
    if best_file:
        stem = Path(best_file).stem
        primary_topic = stem.replace("-", " ").replace("_", " ").strip().title()

    return ranked, best_file, confidence, primary_topic


def _evaluate_single_chunk_signal(
    chunk: dict,
    entries: dict,
    df_counts: dict[str, int],
    idf_weights: dict[str, float],
    chained_weights: dict[str, float],
    chain_decay: float,
) -> dict:
    """Evaluate signals for a single chunk, updating chained weights in place."""
    raw_scores, matched_kws, special_kws = _score_chunk_keywords(
        chunk["filtered_text"], entries, df_counts, idf_weights
    )

    # Propagate temporal chaining weights across chunks: W_t = alpha * W_{t-1} + S_t
    all_candidate_files = set(chained_weights.keys()) | set(raw_scores.keys())
    for f in all_candidate_files:
        prev = chained_weights.get(f, 0.0)
        curr = raw_scores.get(f, 0.0)
        chained_weights[f] = chain_decay * prev + curr

    ranked_cands, best_file, confidence, primary_topic = _rank_chained_candidates(chained_weights)

    # Compute ranked weighted files from direct chunk matches
    file_weighted = {}
    for kw_info in matched_kws.values():
        f_ref = kw_info.get("file")
        if f_ref:
            file_weighted[f_ref] = file_weighted.get(f_ref, 0.0) + kw_info["count"] * kw_info["weight"]

    weighted_files = sorted(
        [{"file": f, "score": round(s, 4)} for f, s in file_weighted.items()],
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "start_sec": chunk["start_sec"],
        "primary_topic": primary_topic,
        "best_file": best_file,
        "confidence": confidence,
        "candidates": ranked_cands,
        "special_keywords": special_kws,
        "standing_keywords": chunk["standing_kws"],
        "matched_keywords": matched_kws,
        "weighted_files": weighted_files,
    }


def detect_signals_for_chunks(
    workspace: Path,
    knowledge_path: Optional[Path] = None,
    chain_decay: float = 0.88,
) -> dict:
    """Run corpus-level TF-IDF signal detection with forward chaining weights on workspace chunks."""
    entries = build_pruned_entries(knowledge_path)
    if not entries:
        return {}

    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        return {}

    loaded_chunks = discover_workspace_chunks(chunks_dir)
    if not loaded_chunks:
        return {}

    df_counts, idf_weights = compute_chunk_idf_weights(loaded_chunks, entries)
    meta_signals = extract_metadata_signals(workspace)
    chained_weights = seed_metadata_chained_weights(meta_signals, entries)

    signals = {}
    for chunk in loaded_chunks:
        signals[chunk["id"]] = _evaluate_single_chunk_signal(
            chunk, entries, df_counts, idf_weights, chained_weights, chain_decay
        )

    return signals


# ── Domain Guidance Detectors ──────────────────────────────────────────────


def _is_tokusatsu_domain(best_file: str, primary_topic: str, matched_kws: dict) -> bool:
    """Check if chunk signal matches Tokusatsu franchise."""
    has_specific = any(k in SPECIFIC_TOKU_KEYWORDS for k in matched_kws)
    toku_score = sum(matched_kws[k].get("count", 1) for k in matched_kws if matched_kws[k].get("kind") == "tokusatsu")
    return (
        "tokusatsu" in best_file or
        "tokusatsu" in primary_topic or
        has_specific or
        toku_score >= 3
    )


def _is_gaming_domain(best_file: str, primary_topic: str, matched_kws: dict) -> bool:
    """Check if chunk signal matches Gaming / Gacha domain."""
    return (
        "gaming" in best_file or
        "fgo" in best_file or
        "game" in primary_topic or
        any(k in GAMING_MATCH_MARKERS for k in matched_kws)
    )


def _is_anime_domain(best_file: str, primary_topic: str) -> bool:
    """Check if chunk signal matches Anime / Manga domain."""
    return "anime" in best_file or "anime" in primary_topic


def _is_talk_domain(best_file: str, primary_topic: str) -> bool:
    """Check if chunk signal matches News / Society / Political critique."""
    return "talk" in best_file or "talk" in primary_topic


def get_domain_guidance(signal: Optional[dict]) -> tuple[list[str], str]:
    """Return (extra_tags, domain_instruction_block) based on detected domain signal."""
    if not signal:
        return [], ""

    best_file = (signal.get("best_file") or "").lower()
    primary_topic = (signal.get("primary_topic") or "").lower()
    matched_kws = signal.get("matched_keywords", {})

    if _is_tokusatsu_domain(best_file, primary_topic, matched_kws):
        return TOKUSATSU_TAGS, TOKUSATSU_INSTRUCTION_BLOCK
    if _is_gaming_domain(best_file, primary_topic, matched_kws):
        return GAMING_TAGS, GAMING_INSTRUCTION_BLOCK
    if _is_anime_domain(best_file, primary_topic):
        return ANIME_TAGS, ANIME_INSTRUCTION_BLOCK
    if _is_talk_domain(best_file, primary_topic):
        return TALK_TAGS, TALK_INSTRUCTION_BLOCK

    return [], ""


# ── IDF & Single-Chunk Primitives ──────────────────────────────────────────


def match_chunk(chunk_text: str, entries: dict, threshold: int = 1):
    """Match chunk text against knowledge entries."""
    matched = {}
    matched_kinds = set()
    text_lower = chunk_text.lower()

    for keyword, info in entries.items():
        kw_lower = keyword.lower()
        count = text_lower.count(kw_lower)
        if count >= threshold:
            kind = info.get("kind", "topic")
            target_file = info.get("file")
            matched_kinds.add(kind)
            matched[keyword] = {
                "count": count,
                "kind": kind,
                "file": target_file
            }

    return matched, list(matched_kinds)


def compute_idf_stats(chunks_texts: list, entries: dict) -> dict:
    """Corpus-level document frequency + inverse-document-frequency per keyword.

    df  = number of chunks containing the keyword (high = daily-use, ambient).
    idf = log(N / df)  -> rare words score high (the interesting ones).
    """
    n = len(chunks_texts)
    df_counts = {kw: 0 for kw in entries}
    for text in chunks_texts:
        tl = text.lower()
        for kw in entries:
            if kw.lower() in tl:
                df_counts[kw] += 1
    stats = {}
    for kw, df in df_counts.items():
        if df <= 0:
            continue
        stats[kw.lower()] = {
            "df": df,
            "idf": round(math.log(n / df), 4),
        }
    return stats


def _process_single_chunk(
    item: tuple,
    entries: dict,
    idf_stats: dict,
    total_chunks: int,
    threshold: int = 1,
) -> tuple[str, dict, bool]:
    """Process a single chunk tuple (chunk_name, start_sec, chunk_text).

    Scores each matched knowledge keyword by corpus rarity: rare (low df) terms
    dominate; daily-use (high df) terms are downweighted. Emits a ranked best-file
    and a primary_topic label for subagent routing.
    """
    chunk_name, start_sec, chunk_text = item
    matched, kinds = match_chunk(chunk_text, entries, threshold)
    matched_files = []
    file_weighted = {}
    kind_weighted = {}
    for kw, data in matched.items():
        file = data.get("file")
        count = data["count"]
        stat = idf_stats.get(kw.lower(), {})
        df = stat.get("df", 1)
        weight = stat.get("idf", 0.0)
        if file:
            matched_files.append({
                "keyword": kw, "file": file, "count": count,
                "df": df, "weight": round(weight, 4),
            })
            file_weighted[file] = file_weighted.get(file, 0.0) + count * weight
        kind = data.get("kind", "topic")
        kind_weighted[kind] = kind_weighted.get(kind, 0.0) + count * weight

    weighted_files = sorted(
        ({"file": f, "score": round(s, 4)} for f, s in file_weighted.items()),
        key=lambda x: x["score"], reverse=True,
    )
    total_weighted = sum(file_weighted.values())
    best = weighted_files[0] if weighted_files else None
    confidence = (best["score"] / total_weighted) if best and total_weighted > 0 else 0.0

    top_kind = max(kind_weighted.items(), key=lambda kv: kv[1])[0] if kind_weighted else ""
    primary_topic = ""
    if best:
        stem = Path(best["file"]).stem
        primary_topic = stem.replace("-", " ").replace("_", " ").strip().title()
        if top_kind and top_kind != "topic":
            primary_topic += f" ({top_kind})"

    res = {
        "start_sec": start_sec,
        "matched_keywords": matched,
        "kinds": kinds,
        "signal_score": dict(Counter([data["kind"] for data in matched.values()])),
        "matched_files": matched_files,
        "weighted_matched_files": weighted_files,
        "weighted_signal_score": {k: round(v, 4) for k, v in kind_weighted.items()},
        "best_file": best["file"] if best and best["score"] > 0 else None,
        "primary_topic": primary_topic,
        "confidence": round(confidence, 4),
        "total_chunks": total_chunks,
    }
    return chunk_name, res, bool(matched)
