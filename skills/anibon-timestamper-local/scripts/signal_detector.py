#!/usr/bin/env python3
"""Signal detector and domain knowledge resolver for local timestamper.

Scans transcript chunks against knowledge.json using corpus-level IDF (rarity)
matching, normalizes phonetic entities with default_mappings.json, and provides
domain-specific tags, prompt hints, and first-verbs.
"""
from __future__ import annotations


import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Optional

_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from anibon.cleaner import compile_mapping_entries
from anibon.resources import resource_path


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


GAME_SPECIAL_WORDS: dict[str, list[str]] = {
    "Chaos_Zero_Nightmare.md": [
        "chaos zero nightmare", "chaos zero", "czn", "คาเซน่า", "คาเซนา",
        "เคอส", "เคออส", "ฝันร้าย",
        "epiphany", "trauma code", "ทรอม่าโค้ด", "omega code", "โอเมก้าโค้ด",
        "memory fragment", "เมมโมรี่แฟรกเมนต์", "พเนอร์", "พาร์ทเนอร์",
        "rossweisse", "รอสไวส์", "รอซึวสึ", "sereniel", "เซรนิว", "เซรณี", "เซเรเนียล",
        "nebia", "เนเบีย", "เนบีย", "renoir", "เรนัวร์", "เลนัว",
    ],
    "Wuthering_Waves.md": [
        "wuthering waves", "wuthering", "wuwa", "เวฟ", "rover", "jinhsi", "changli", "yinlin",
        "echo", "tacet field", "sonance sphere",
    ],
    "Zenless_Zone_Zero.md": [
        "zenless zone zero", "zenless", "zzz", "new eridu", "bangboo",
        "hollow zero", "proxies", "proxy", "inter-knot",
    ],
    "Blue_Archive.md": [
        "blue archive", "kivotos", "schale", "sensei", "halo festival", "total assault",
    ],
    "Honkai_Star_Rail.md": [
        "honkai star rail", "star rail", "hsr", "astral express", "trailblazer",
        "stellaron", "simulated universe",
    ],
    "Genshin_Impact.md": [
        "genshin impact", "genshin", "teyvat", "archon", "primogem",
        "spiral abyss", "paimon",
    ],
    "Fate_Grand_Order.md": [
        "fate grand order", "fgo", "chaldea", "servant", "noble phantasm", "saint quartz",
    ],
    "Deadlock.md": [
        "deadlock", "patron", "trooper", "mid boss", "flex slot", "spirit power",
    ],
    "Sekiro_Shadows_Die_Twice.md": [
        "sekiro", "shadows die twice", "kusabimaru", "posture", "shinobi", "dragonrot",
    ],
    "Eternal_Return.md": [
        "eternal return", "lumia island",
    ],
    "Yu_Gi_Oh.md": [
        "yu-gi-oh", "yugioh", "master duel", "duel monsters",
    ],
    "Pokemon.md": [
        "pokemon", "โปเกมอน", "pikachu", "pokedex",
    ],
    "Monster_Hunter_Wilds.md": [
        "monster hunter wilds", "monster hunter", "mh wilds", "seikret", "focus mode",
    ],
}

COMMON_CHARACTER_NAMES_BLACKLIST: set[str] = {
    # Japanese common given names / popular gacha shared names
    "yuki", "ยูกิ", "rin", "ริน", "mika", "มิกะ", "hoshino", "shiroko", "arona",
    "lucy", "alice", "yvonne", "kuro", "emma", "chizuru", "miyabi", "yanagi",
    "dante", "faust", "morgan", "arthur", "nero", "jeanne", "sakura", "ren",
    "haru", "aoi", "sora", "hikari", "tsubasa", "kaito", "shiki", "shirou",
    "shin", "kai", "jin", "rei", "maya", "sara", "elena", "maria", "clara",
}

AMBIGUOUS_SINGLE_TOKENS: set[str] = {
    "blue", "thai", "japan", "dark", "super", "grand", "star", "night", "zero",
    "shadow", "shadows", "impact", "zone", "order", "return", "hunter", "wilds",
    "fair", "convention", "book", "stream", "online", "project", "chronicle",
}

GENERIC_GAMING_STANDING_WORDS: set[str] = {
    "บอส", "กาชา", "เกลือ", "หลุดเรท", "โรล", "ตู้", "การันตี", "เพชร", "เหรียญ",
    "ดาเมจ", "คริ", "atk", "def", "hp", "sp", "mp", "บัฟ", "ดีบัฟ", "สเตตัส",
    "คอมโบ", "สตรีค", "แพตช์", "อัปเดต", "เนิร์ฟ", "เนิฟ", "บั๊ก", "แล็ก", "ปิง",
    "solo", "parry", "dodge", "dash", "ultimate", "ult", "สกิล", "ท่าไม้ตาย",
    "gacha", "boss", "damage", "crit", "buff", "debuff", "nerf", "patch", "roll",
}

DUPE_TIER_RE = re.compile(
    r"\b(?:[CEce][0-6]|[Ss][0-6]|[Rr][1-5]|[Mm][0-6])\b|"
    r"(?:ระดับ|ขั้น|ดาว|ก๊อปปี้|ปลด)\s*[0-6]"
)


def filter_standing_gaming_words(text: str) -> tuple[str, list[str]]:
    """Extract and strip generic gaming standing words and dupe/eidolon tier codes from text.

    Returns (cleaned_text, detected_standing_words).
    """
    found_standing = []
    # 1. Dupe tier regex
    for m in DUPE_TIER_RE.finditer(text):
        found_standing.append(m.group(0).lower().strip())
    cleaned = DUPE_TIER_RE.sub(" ", text)

    # 2. Generic gaming words
    for gw in sorted(GENERIC_GAMING_STANDING_WORDS, key=len, reverse=True):
        if re.search(r"^[a-zA-Z0-9]+$", gw):
            pattern = re.compile(rf"\b{re.escape(gw)}\b", re.IGNORECASE)
        else:
            pattern = re.compile(rf"{re.escape(gw)}", re.IGNORECASE)
        if pattern.search(cleaned):
            found_standing.append(gw.lower())
            cleaned = pattern.sub(" ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, list(dict.fromkeys(found_standing))


def discover_reference_games(refs_dir: Optional[Path] = None) -> dict[str, str]:
    """Scan markdown knowledge files and return mapping of lowercase keywords -> relative file path."""
    if refs_dir is None:
        script_dir = Path(__file__).resolve().parent
        refs_dir = script_dir.parent.parent / "anibon-world-identity" / "references"
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

    # Strip blocked single tokens, common character names, and generic words from Stage 1
    blocked_stage1 = AMBIGUOUS_SINGLE_TOKENS | COMMON_CHARACTER_NAMES_BLACKLIST | GENERIC_GAMING_STANDING_WORDS
    for blocked in list(discovered.keys()):
        if blocked in blocked_stage1 or any(blocked == b.lower() for b in blocked_stage1):
            discovered.pop(blocked, None)

    return discovered


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


_get_compiled_mappings = compile_mapping_entries


def normalize_transcript(text: str, mappings: list[dict]) -> str:
    """Normalize phonetically garbled names and clean noise in transcript text."""
    if not text:
        return ""

    # Denoise before applying entity replacements
    normalized = clean_transcript_noise(text)

    if not mappings:
        return normalized

    for pattern, replacement in _get_compiled_mappings(mappings):
        normalized = pattern.sub(replacement, normalized)
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
    entries = load_knowledge(knowledge_path) or {}

    # Merge dynamically discovered game references
    discovered_refs = discover_reference_games()
    for kw, ref_file in discovered_refs.items():
        if kw not in entries:
            entries[kw] = {"kind": "game", "file": ref_file}

    if not entries:
        return {}

    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        return {}

    # Extract metadata signals from stream info if available
    meta_signals = extract_metadata_signals(workspace)

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

    # Stream-level anchor: chunks with no game match inherit the stream's dominant game,
    # so gameplay chunks without spoken title keywords still get the right reference.
    game_totals = {}
    for kw, meta in entries.items():
        if meta.get("kind") == "game" and meta.get("file"):
            kw_l = kw.lower()
            game_totals[meta["file"]] = game_totals.get(meta["file"], 0.0) + meta_signals.get(kw_l, 0.0) * 10
    for s in signals.values():
        for m in s["matched_keywords"].values():
            if m["kind"] == "game" and m["file"]:
                game_totals[m["file"]] = game_totals.get(m["file"], 0.0) + m["count"] * m["weight"]
    dominant = max(game_totals, key=game_totals.get) if game_totals else None
    if dominant and game_totals[dominant] >= 0.4 * sum(game_totals.values()):
        for s in signals.values():
            # A single passing mention ("ยูกิ x1", "fgo x1") must not override the stream's game.
            has_game = any(m["kind"] == "game" and (m["count"] >= 3 or m["file"] == dominant)
                           for m in s["matched_keywords"].values())
            if not has_game:
                s["best_file"] = dominant
                s["primary_topic"] = Path(dominant).stem.replace("_", " ") + " (stream anchor)"
                s["weighted_files"] = [{"file": dominant, "score": 0.0}] + s["weighted_files"][:2]

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
