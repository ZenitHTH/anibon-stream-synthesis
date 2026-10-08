#!/usr/bin/env python3
"""Signal detector and domain knowledge resolver for local timestamper.

Scans transcript chunks against knowledge.json using corpus-level IDF (rarity)
matching, normalizes phonetic entities with default_mappings.json, and provides
domain-specific tags, prompt hints, and first-verbs.
"""

import json
import math
import os
import re
from pathlib import Path
from typing import Optional


def load_knowledge(knowledge_path: Optional[Path] = None) -> dict:
    """Load knowledge.json entries mapping keywords -> domain files."""
    if knowledge_path and knowledge_path.exists():
        p = knowledge_path
    else:
        # Fallback to local resources or sibling timestamper resources
        script_dir = Path(__file__).resolve().parent
        candidates = [
            script_dir.parent / "resources" / "knowledge.json",
            script_dir.parent.parent / "anibon-timestamper" / "resources" / "knowledge.json",
        ]
        p = next((c for c in candidates if c.exists()), None)

    if not p or not p.exists():
        return {}

    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", {})


def load_mappings(mappings_path: Optional[Path] = None) -> list[dict]:
    """Load phonetic entity mappings from default_mappings.json."""
    if mappings_path and mappings_path.exists():
        p = mappings_path
    else:
        script_dir = Path(__file__).resolve().parent
        candidates = [
            script_dir.parent / "resources" / "default_mappings.json",
            script_dir.parent.parent / "anibon-timestamper" / "resources" / "default_mappings.json",
        ]
        p = next((c for c in candidates if c.exists()), None)

    if not p or not p.exists():
        return []

    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


def load_garbled_replacements(path: Optional[Path] = None) -> list[dict]:
    """Load confirmed ground-truth corrections from garbled_replacements.json.

    garbled_replacements.json format (inverse of default_mappings):
        { "correct_name": ["garbled_variant1", "garbled_variant2", ...], ... }

    Returns a list[dict] in the same shape as load_mappings() output so that
    normalize_transcript() can consume both sources with a single call:
        [{"correct": "...", "patterns": ["...", ...]}, ...]
    """
    if path and path.exists():
        p = path
    else:
        script_dir = Path(__file__).resolve().parent
        home = Path.home()
        candidates = [
            # master plugin resources (most up-to-date)
            script_dir.parent.parent.parent / "resources" / "garbled_replacements.json",
            script_dir.parent.parent / "anibon-timestamper" / "resources" / "garbled_replacements.json",
            # common local paths used by whisper_dispatcher
            home / ".gemini" / "config" / "plugins" / "anibon-stream-synthesis" / "resources" / "garbled_replacements.json",
        ]
        p = next((c for c in candidates if c.exists()), None)

    if not p or not p.exists():
        return []

    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    mappings_dict = data.get("mappings", {})
    if not isinstance(mappings_dict, dict):
        return []

    result = []
    for correct, garbled_variants in mappings_dict.items():
        if isinstance(garbled_variants, list) and garbled_variants:
            result.append({"correct": correct, "patterns": garbled_variants})
    return result


# Non-speech sound brackets and filler tokens commonly injected by YouTube ASR
_NOISE_BRACKET_RE = re.compile(
    r"\[(?:เพลง|ดนตรี|เสียงดนตรี|เสียงปรบมือ|เสียงหัวเราะ|หัวเราะ|เสียงเอฟเฟกต์|Music|Applause|Laughter|Cheering)\]|"
    r"\((?:เพลง|ดนตรี|เสียงดนตรี|เสียงปรบมือ|เสียงหัวเราะ|หัวเราะ|เสียงเอฟเฟกต์|Music|Applause|Laughter|Cheering)\)",
    flags=re.IGNORECASE,
)
_SPEAKER_MARKER_RE = re.compile(r"(?:^|\s)(?:>>+|>>>+)\s*")
_MUSIC_NOTES_RE = re.compile(r"[♪♫♬♩]+")
_MULTI_SPACE_RE = re.compile(r"\s+")
_EXTENDED_CHAR_REPEAT_RE = re.compile(r"(.)\1{7,}")


def clean_transcript_noise(text: str) -> str:
    """Clean ASR artifacts, non-speech sound tags, speaker markers, and character loops.

    Removes:
    - YouTube ASR speaker change markers (>>, >>>)
    - Bracketed non-speech sound descriptions ([เพลง], [ดนตรี], [เสียงปรบมือ], [Applause], etc.)
    - Music note symbols (♪, ♫, etc.)
    - Runaway character repetitions (e.g. 55555555555555 -> 555)
    - Extra whitespace
    """
    if not text:
        return ""

    # 1. Strip speaker markers
    cleaned = _SPEAKER_MARKER_RE.sub(" ", text)

    # 2. Strip non-speech brackets
    cleaned = _NOISE_BRACKET_RE.sub(" ", cleaned)

    # 3. Strip music notes
    cleaned = _MUSIC_NOTES_RE.sub(" ", cleaned)

    # 4. Collapse extreme character stutter/loops (>7 repeats down to 3)
    cleaned = _EXTENDED_CHAR_REPEAT_RE.sub(r"\1\1\1", cleaned)

    # 5. Normalize whitespace
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def normalize_transcript(text: str, mappings: list[dict]) -> str:
    """Normalize phonetically garbled names and clean noise in transcript text."""
    if not text:
        return ""

    # Denoise before applying entity replacements
    normalized = clean_transcript_noise(text)

    if not mappings:
        return normalized

    for item in mappings:
        correct = item.get("correct")
        patterns = item.get("patterns", [])
        if not correct or not patterns:
            continue
        for pat in patterns:
            if not pat:
                continue
            # Replace pattern case-insensitively
            normalized = re.sub(re.escape(pat), correct, normalized, flags=re.IGNORECASE)
    return normalized


def extract_chunk_text(path: Path) -> tuple[int, str]:
    """Extract (start_sec, clean_text) from a chunk file (.txt, .json, or .xml)."""
    text = ""
    start_sec = 0

    if path.suffix == ".txt":
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        # Find first timestamp (HH:MM:SS)
        m = re.search(r"\((\d{2}):(\d{2}):(\d{2})\)", raw)
        if m:
            start_sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        # Strip timestamps for keyword matching
        text = re.sub(r"\(\d{2}:\d{2}:\d{2}\)", "", raw)

    elif path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        start_sec = int(data.get("start_sec", 0))
        text = " ".join(it.get("text", "").strip() for it in data.get("items", []) if it.get("text"))

    elif path.suffix == ".xml":
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
        start_sec = int(root.get("start_sec", 0))
        text = " ".join((it.text or "").strip() for it in root.iter("item") if it.text)

    # Denoise text before signal detection
    clean_text = clean_transcript_noise(text)
    return start_sec, clean_text


def detect_signals_for_chunks(workspace: Path, knowledge_path: Optional[Path] = None) -> dict:
    """Run corpus-level TF-IDF signal detection on workspace chunks and return signals map."""
    entries = load_knowledge(knowledge_path)
    if not entries:
        return {}

    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        return {}

    def sort_key(p: Path):
        m = re.search(r"chunk_(\d+)", p.stem)
        return int(m.group(1)) if m else 0

    chunk_files = sorted(
        list(chunks_dir.glob("chunk_*.txt")) or
        list(chunks_dir.glob("chunk_*.json")) or
        list(chunks_dir.glob("chunk_*.xml")),
        key=sort_key
    )

    if not chunk_files:
        return {}

    # Extract text from all chunks
    loaded_chunks = []
    for cf in chunk_files:
        start_sec, raw_text = extract_chunk_text(cf)
        loaded_chunks.append({
            "id": cf.stem,
            "path": cf,
            "start_sec": start_sec,
            "text": raw_text.lower(),
        })

    n_chunks = len(loaded_chunks)

    # 1. Compute Document Frequency (df) for each keyword in knowledge.json
    df_counts = {}
    for kw in entries:
        kw_l = kw.lower()
        count = sum(1 for c in loaded_chunks if kw_l in c["text"])
        if count > 0:
            df_counts[kw_l] = count

    # 2. Compute IDF weight = log(N / df)
    idf_weights = {}
    for kw_l, df in df_counts.items():
        idf_weights[kw_l] = math.log((n_chunks + 1.0) / (df + 0.5)) + 1.0

    # 3. Score each chunk
    signals = {}
    for c in loaded_chunks:
        cid = c["id"]
        text = c["text"]

        matched_files = {}
        file_kinds = {}
        kind_weighted = {}
        matched_keywords = {}

        for kw, meta in entries.items():
            kw_l = kw.lower()
            if kw_l in df_counts and kw_l in text:
                occurrences = text.count(kw_l)
                weight = idf_weights.get(kw_l, 1.0)
                score = occurrences * weight
                kind = meta.get("kind", "topic")
                file_ref = meta.get("file")

                matched_keywords[kw] = {
                    "count": occurrences,
                    "kind": kind,
                    "file": file_ref,
                    "weight": round(weight, 4),
                }

                if file_ref:
                    matched_files[file_ref] = matched_files.get(file_ref, 0.0) + score
                    file_kinds.setdefault(file_ref, set()).add(kind)
                kind_weighted[kind] = kind_weighted.get(kind, 0.0) + score

        # Rank files: prioritize specific content (game, tokusatsu, anime, etc.) over generic stream_type
        specific_kinds = {"game", "tokusatsu", "anime", "event", "publisher", "bookstore", "vlog_theme"}

        def file_rank_key(item):
            f = item["file"]
            kinds = file_kinds.get(f, set())
            is_specific = 1 if (kinds & specific_kinds) and "stream_type" not in kinds else 0
            return (is_specific, item["score"])

        sorted_files = sorted(
            [{"file": f, "score": round(s, 4)} for f, s in matched_files.items()],
            key=file_rank_key,
            reverse=True
        )

        best_file = sorted_files[0]["file"] if sorted_files else None
        total_score = sum(matched_files.values())
        confidence = (sorted_files[0]["score"] / total_score) if sorted_files and total_score > 0 else 0.0

        primary_topic = "General Livestream"
        if best_file:
            stem = Path(best_file).stem
            primary_topic = stem.replace("-", " ").replace("_", " ").title()

        signals[cid] = {
            "start_sec": c["start_sec"],
            "primary_topic": primary_topic,
            "best_file": best_file,
            "confidence": round(confidence, 4),
            "matched_keywords": matched_keywords,
            "weighted_files": sorted_files[:3],
        }

    # Save to workspace/signals.json
    out_path = workspace / "signals.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)

    return signals


def get_domain_guidance(signal: Optional[dict]) -> tuple[list[str], str]:
    """Return (extra_tags, domain_instruction_block) based on detected domain signal."""
    if not signal:
        return [], ""

    best_file = (signal.get("best_file") or "").lower()
    primary_topic = (signal.get("primary_topic") or "").lower()
    matched_kws = signal.get("matched_keywords", {})

    # Detect Tokusatsu (require specific franchise name, or tokusatsu best_file, or 2+ tokusatsu markers)
    specific_toku = {
        "คาเมนไรเดอร์", "มาสค์ไรเดอร์", "คาเมน ไรเดอร์", "เซนไต", "ซุปเปอร์เซนไต",
        "อุลตร้าแมน", "gavv", "geats", "gotchard", "boonboomger", "king-ohger",
        "เฮนชิน", "เข็มขัดแปลงร่าง", "เข็มขัดไรเดอร์", "แปลงร่าง", "โทคุซัตสึ", "โทคุสะสึ", "ไคจู"
    }
    has_specific = any(k in specific_toku for k in matched_kws)
    toku_score = sum(matched_kws[k].get("count", 1) for k in matched_kws if matched_kws[k].get("kind") == "tokusatsu")

    is_tokusatsu = (
        "tokusatsu" in best_file or
        "tokusatsu" in primary_topic or
        has_specific or
        toku_score >= 3
    )

    if is_tokusatsu:
        tags = ["[WatchParty]", "[Reaction]", "[Lore]", "[Review]", "[Tierlist]"]
        block = """\
## DETECTED DOMAIN: TOKUSATSU (มาสค์ไรเดอร์ / ขบวนการเซนไต / อุลตร้าแมน)
- Format: Watch Party or Franchise Lore Discussion.
- Key Terms & Characters:
  * Kamen Rider Gavv (ไรเดอร์กาฟ), Gotchard (ก็อตชาร์ด), Geats (กีทส์), Boonboomger (บูนบูมเจอร์)
  * Henshin (เฮนชิน/แปลงร่าง), Rider Belt (เข็มขัดแปลงร่าง), Final Form (ร่างพัฒนา/ร่างสุดยอด), DX Toys
- Focus: Highlight streamer's intense reactions, shock, or laugh at on-screen fight/transformation scenes.
- FIRST-VERBS: กรี๊ดลั่น!, เหวอ!, อึ้งฟอร์มใหม่, ชำแหละเนื้อเรื่อง, จัดอันดับสูท, บ่นราคาของเล่น, ปั่น
"""
        return tags, block

    # Detect Gaming / Gacha
    is_gaming = (
        "gaming" in best_file or
        "fgo" in best_file or
        "game" in primary_topic or
        any(k in ["gacha", "boss", "limbus", "genshin", "arknights", "กาชา"] for k in matched_kws)
    )

    if is_gaming:
        tags = ["[Gameplay]", "[Gacha]", "[Boss]", "[Story]", "[Tierlist]"]
        block = """\
## DETECTED DOMAIN: GAMING & GACHA
- Format: Gameplay, Gacha pull, or Game Lore discussion.
- Focus: Distinguish between gacha summons, tough boss encounters, and story dialogue.
- FIRST-VERBS: เปิดกาชา, ลุ้นตัวทอง, สู้บอส, ผ่านด่าน, หัวร้อน!, ช็อกกาชาเกลือ, เจาะลึกสตอรี่
"""
        return tags, block

    # Detect Anime / Pop-culture
    is_anime = "anime" in best_file or "anime" in primary_topic
    if is_anime:
        tags = ["[WatchParty]", "[Reaction]", "[Review]", "[Talk]"]
        block = """\
## DETECTED DOMAIN: ANIME & MANGA
- Format: Anime discussion, review, or seasonal watch party.
- FIRST-VERBS: ป้ายยา, สับเละ, อวยยับ, วิเคราะห์อนิเมชั่น, ชวนคุยตอนล่าสุด
"""
        return tags, block

    # Detect Politics / News / Serious Talk
    is_talk = "talk" in best_file or "talk" in primary_topic
    if is_talk:
        tags = ["[News]", "[Talk]", "[Chat]"]
        block = """\
## DETECTED DOMAIN: POLITICS, SOCIETY & NEWS
- Format: Political critique, social news, or legal/agency commentary.
- FIRST-VERBS: ชำแหละ, จวกยับ, สับเละ, บ่นอุบ, โวยวาย, วิเคราะห์, กางตัวเลข, เตือน
"""
        return tags, block

    return [], ""
