"""Prompt building for local LLM timestamping.

Supports:
- Recursive rolling summary prompts with 1-3 timestamps array and continuity flags
- Group batching prompts (~16-20 min windows)
- World Identity markdown lore injection
- Multi-modal context (LiveChat, 555 mood, visual activity) & Web search snippets
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from common.time import fmt_ts, parse_ts
from common.timestamps import TAGS
from common import config as _cfg
from common.resources import plugin_root
from process.enrichment_prompt import format_enrichment_context
from process.signals import get_domain_guidance

_ROOT = plugin_root()
_WI_CANDIDATES = [
    _ROOT / "skills" / "anibon-world-identity" / "references",
    _ROOT / "references",
]
WORLD_IDENTITY_DIR: Optional[Path] = next((p for p in _WI_CANDIDATES if p.is_dir()), None)


def _chunk_range(items: list, chunk: Optional[dict] = None) -> Tuple[str, str]:
    if not items:
        if chunk and int(chunk.get("end_sec", 0) or 0) > int(chunk.get("start_sec", 0) or 0):
            return fmt_ts(int(chunk["start_sec"])), fmt_ts(int(chunk["end_sec"]))
        return "00:00:00", "00:00:00"
    start = items[0].get("start", 0)
    last = items[-1]
    end = last.get("start", 0) + last.get("duration", 5)
    return fmt_ts(start), fmt_ts(end)


def load_world_identity_context(
    signal: Optional[dict],
    world_identity_dir: Optional[Path] = None,
) -> str:
    """Return a World Identity reference snippet for the detected game domain."""
    ref_dir = world_identity_dir or WORLD_IDENTITY_DIR
    if not ref_dir or not signal:
        return ""

    candidate_files = []
    if signal.get("best_file"):
        candidate_files.append(signal["best_file"])
    for wf in signal.get("weighted_files", []):
        f = wf.get("file") if isinstance(wf, dict) else wf
        if f and f not in candidate_files:
            candidate_files.append(f)

    if not candidate_files:
        return ""

    from process.knowledge.reader import resolve_reference_file

    search_dirs = [world_identity_dir] if (world_identity_dir and Path(world_identity_dir).is_dir()) else []
    if WORLD_IDENTITY_DIR and WORLD_IDENTITY_DIR.is_dir() and WORLD_IDENTITY_DIR not in search_dirs:
        search_dirs.append(WORLD_IDENTITY_DIR)

    candidate = None
    for target in candidate_files:
        c = resolve_reference_file(target, search_dirs)
        if c and c.is_file():
            candidate = c
            break

    if not candidate or not candidate.exists():
        return ""

    try:
        text = candidate.read_text(encoding="utf-8")
    except Exception:
        return ""

    limit = _cfg.WI_SNIPPET_LIMIT
    snippet = text[:limit] if limit > 0 else text
    if len(snippet) < len(text):
        snippet += "\n... (truncated)"

    extra = ""
    if "pokemon" in candidate.stem.lower():
        pokemon_db = ref_dir / "Pokemon DATA" / "pokemon.db"
        if pokemon_db.exists():
            extra = (
                f"\n> **Pokémon DB**: `{pokemon_db}` — cross-check Thai/EN names before writing.\n"
                "> Thai name MUST come first: แบกซ์แคลิเบอร์ (Baxcalibur), not bare English.\n"
            )

    return f"## WORLD IDENTITY REFERENCE: {candidate.stem}\n{snippet}{extra}"


def build_candidate_weights_block(signal: Optional[dict]) -> str:
    """Format Stage-1 candidate game weights, matched special words, and standing-word guards."""
    if not signal:
        return ""

    candidates = signal.get("candidates", [])
    special_kws = signal.get("special_keywords", [])
    standing_kws = signal.get("standing_keywords", [])

    lines = ["## CANDIDATE DOMAIN WEIGHTS (STAGE 1 SIGNAL DETECTION)"]

    if candidates:
        lines.append("Active candidate games ranked by temporal chaining weight:")
        for cand in candidates[:3]:
            file_name = cand.get("file", "")
            topic = cand.get("topic")
            if not topic:
                stem = Path(file_name).stem if file_name else "Unknown"
                topic = stem.replace("-", " ").replace("_", " ").title()
            w = cand.get("weight", 0.0)
            prob_pct = int(round(cand.get("prob", 0.0) * 100))
            kws = cand.get("keywords") or special_kws
            kw_str = f" [matched special words: {', '.join(kws)}]" if kws else ""
            lines.append(f"- {topic}: weight={w} ({prob_pct}%){kw_str}")
    elif signal.get("primary_topic"):
        lines.append(f"- {signal['primary_topic']}: confidence={int(round(signal.get('confidence', 0.0)*100))}%")

    if special_kws and not any("matched special words" in l for l in lines):
        lines.append(f"- Detected Special Words: {', '.join(special_kws)}")

    lines.append("")
    lines.append("### GENERIC GAMING STANDING WORDS & COMMON NAMES GUARD")
    lines.append(
        "1. Standing Dupe Codes & Generic Terms:\n"
        "   - Terms like E0-E6, C0-C6, S0-S6, R1-R5, M0-M6, 'กาชา', 'ตู้', 'หลุดเรท', 'เกลือ', 'บอส', 'ดาเมจ', 'parry', 'solo'\n"
        "     are universal gamer vocabulary. NEVER infer a game (e.g. Zenless Zone Zero, Wuthering Waves) based solely on these codes!\n"
        "2. Common Character Given Names:\n"
        "   - Shared names (e.g. Yuki, Rin, Mika, Yvonne, Lucy, Alice, Kuro, Emma) belong to multiple anime/games.\n"
        "     Strictly adhere to the dominant candidate game above and the VERIFIED DOMAIN ENTITIES table below."
    )
    if standing_kws:
        lines.append(f"   - (Detected in this chunk: {', '.join(standing_kws)})")

    return "\n".join(lines)


def build_chunk_entity_context(
    chunk_text: str,
    glossary: Optional[dict] = None,
    max_tokens: int = 0,
    allowed_sources: Optional[Set[str]] = None,
) -> str:
    """Filter entity glossary to entities relevant to the current chunk text.

    Scans for English and Thai names/aliases in chunk_text and outputs a
    compact Markdown block under ## VERIFIED DOMAIN ENTITIES (WORLD IDENTITY).
    Capped to avoid prompt token explosion on local 16GB GPUs.
    """
    if not chunk_text or not glossary:
        return ""
    max_tokens = max_tokens or _cfg.ENTITY_CONTEXT_MAX_TOKENS
    max_count = _cfg.ENTITY_MAX_COUNT or 10**9

    text_lower = chunk_text.lower()
    matched_lines = []
    seen = set()

    for name, meta in glossary.items():
        if not isinstance(meta, dict):
            continue

        matching_source = None
        if allowed_sources is not None:
            raw_sources = meta.get("sources")
            if not raw_sources:
                single = meta.get("source_file") or meta.get("file") or meta.get("source")
                raw_sources = [single] if single else []
            source_candidates = [Path(s).name for s in raw_sources if s]
            if not source_candidates or not any(s in allowed_sources for s in source_candidates):
                continue
            matching_source = next((s for s in source_candidates if s in allowed_sources), None)

        active_meta = meta
        if matching_source and "variants" in meta and matching_source in meta["variants"]:
            active_meta = meta["variants"][matching_source]

        en = str(active_meta.get("en") or (name if not re.search(r"[\u0E00-\u0E7F]", name) else "")).strip()
        th = str(active_meta.get("th") or (name if re.search(r"[\u0E00-\u0E7F]", name) else "")).strip()
        alias_th = str(active_meta.get("alias_th", "")).strip()

        hit = False
        if en and len(en) >= 3 and en.lower() in text_lower:
            hit = True
        elif th and len(th) >= 3 and th.lower() in text_lower:
            hit = True
        elif alias_th and len(alias_th) >= 3 and alias_th.lower() in text_lower:
            hit = True
        elif name and len(name) >= 3 and name.lower() in text_lower:
            hit = True

        if hit:
            key_id = en or th or name
            if key_id in seen:
                continue
            seen.add(key_id)

            label = f"{en} ({th})" if (en and th) else (en or th or name)
            role = active_meta.get("role") or active_meta.get("class")
            desc = active_meta.get("description", "")
            extra = f" [{role}]" if role else (f" - {desc}" if desc else "")
            matched_lines.append(f"- {label}{extra}")

            if len(matched_lines) >= max_count:
                break

    # Also resolve JIT domain entities (phonetic bridge + SQLite)
    if allowed_sources is None or any(db_game in s.lower() for s in allowed_sources for db_game in ("fgo", "fate", "pokemon", "ygo", "yu-gi-oh")):
        try:
            from process.knowledge.domain_db import resolve_entities_for_chunk
            jit_entities = resolve_entities_for_chunk(chunk_text, max_entities=10)
            for entity_label in jit_entities:
                if entity_label not in seen:
                    seen.add(entity_label)
                    matched_lines.append(f"- {entity_label}")
                    if len(matched_lines) >= max_count:
                        break
        except Exception:
            pass

    if not matched_lines:
        return ""

    char_limit = max_tokens * 4
    selected_lines = []
    curr_len = 0
    for line in matched_lines:
        if curr_len + len(line) + 1 > char_limit and selected_lines:
            break
        selected_lines.append(line)
        curr_len += len(line) + 1

    return "## VERIFIED DOMAIN ENTITIES (WORLD IDENTITY):\n" + "\n".join(selected_lines)


_KNOWN_OPENING_PREFIXES = (
    "วิเคราะห์", "วิพากษ์", "อึ้ง!", "อึ้ง", "พูดถึง", "ส่อง", "ชำแหละ", "เม้าท์มอย",
    "เจาะลึก", "กางทฤษฎี", "ถกประเด็น", "เทียบ", "แซว", "เหวอ!", "เหวอ",
    "ฮาลั่น!", "จวกยับ", "สับเละ", "สรุป", "รีวิว", "เปิดประเด็น",
)


def _extract_recent_opening_verbs(recent_timestamps: List[str]) -> List[str]:
    """Extract opening verb prefixes from recent timestamp lines."""
    used: List[str] = []
    for ts in recent_timestamps[-4:]:
        m = re.match(r"^\d{2}:\d{2}:\d{2}\s*-\s*(?:\[[^\]]+\])+\s*(.+)$", ts.strip())
        if not m:
            continue
        desc = m.group(1).strip()
        for prefix in _KNOWN_OPENING_PREFIXES:
            if desc.startswith(prefix) and prefix not in used:
                used.append(prefix)
                break
    return used


def _compute_gap_predicate(
    recent_timestamps: Optional[List[str]],
    chunk_start_ts: str = "00:00:00",
    threshold_min: int = 8,
) -> str:
    """Compute observable gap predicate when elapsed time since last timestamp >= threshold_min."""
    if not recent_timestamps or not chunk_start_ts:
        return ""
    last_line = next((ts.strip() for ts in reversed(recent_timestamps) if ts and ts.strip()), "")
    if len(last_line) < 8:
        return ""
    last_ts = last_line[:8]
    last_sec = parse_ts(last_ts)
    start_sec = parse_ts(chunk_start_ts)
    if last_sec is None or start_sec is None or start_sec <= last_sec:
        return ""
    elapsed_min = (start_sec - last_sec) // 60
    if elapsed_min < threshold_min:
        return ""
    return (
        f"\nGAP PREDICATE: {elapsed_min} minutes elapsed since last timestamp ({last_ts}) >= {threshold_min} min threshold "
        "-> REQUIRED: Emit 1 timestamp in this chunk marking the current tactical adjustment, boss phase, exploration progress, or sub-topic so the timeline never has a >10 min gap."
    )


def _format_recent_timestamps(
    recent_timestamps: Optional[List[str]],
    chunk_start_ts: str = "00:00:00",
) -> str:
    """Format recent emitted timestamps block to avoid duplicate stamps and repeated verbs."""
    if not recent_timestamps:
        return ""
    stamps = "\n".join(f"- {ts}" for ts in recent_timestamps if ts)
    if not stamps:
        return ""
    used_verbs = _extract_recent_opening_verbs(recent_timestamps)
    ban_note = (
        f"\nBANNED OPENING WORDS FOR THIS CHUNK (already used recently): {', '.join(used_verbs)} — You MUST start with a different verb or lead directly with the noun/topic!"
        if used_verbs else ""
    )
    gap_note = _compute_gap_predicate(recent_timestamps, chunk_start_ts)
    return f"Recent Emitted Timestamps (DO NOT re-stamp the same ongoing topic):\n{stamps}{ban_note}{gap_note}\n"


def _format_previous_topic_section(
    chunk_idx: int,
    current_topic: str,
    rolling_summary: str,
    recent_timestamps: Optional[List[str]] = None,
    chunk_start_ts: str = "00:00:00",
) -> str:
    """Format previous topic state, rolling summary chain, and recent timestamps."""
    if not current_topic:
        preroll = (
            "PRE-ROLL STANDBY / OPENING RULE (CHUNK 00 - CRITICAL):\n"
            "- If the opening minutes before Pu Boat's first coherent Thai greeting contain only waiting-screen BGM, lyrics, or isolated noise tokens (e.g. 'เฮ', 'ป', 'อา'), emit `00:00:00 - [Intro] เปิดไลฟ์เตรียมความพร้อมและสแตนด์บายก่อนเข้าสู่ช่วงเนื้อหาหลัก`.\n"
            "- NEVER hallucinate 'เปิดคลิปอนิเมะสั้น' or spoken topics from pre-roll waiting music; stamp the first `[Talk]`/`[Greeting]` at the exact timestamp where coherent spoken Thai begins.\n"
        )
        return f"## PREVIOUS TOPIC STATE\n(No previous topic — livestream is starting)\n{preroll}"
    prev_idx = max(0, chunk_idx - 1)
    lines = [
        f"## PREVIOUS TOPIC STATE (Chunk {prev_idx:02d})",
        f"Active Topic: {current_topic}",
        f"Rolling Context Chain (last 15m): {rolling_summary}",
    ]
    ts_block = _format_recent_timestamps(recent_timestamps, chunk_start_ts=chunk_start_ts)
    if ts_block:
        lines.append(ts_block.strip())
    return "\n".join(lines) + "\n"



def _build_chunk_media_block(chunk: dict, livechat: str = "") -> str:
    """Build automated media separation ground-truth block for a chunk."""
    from process.media.separator import build_media_separation_prompt_block
    from process.media.types import ChunkMediaInput
    items = chunk.get("items", [])
    raw_lines = tuple(
        f"({it.get('timestamp', '')}) {it.get('raw_text') or it.get('text', '')}"
        for it in items
        if (it.get("raw_text") or it.get("text"))
    )
    if not raw_lines:
        return ""
    chat_lines = tuple(livechat.splitlines()) if livechat else ()
    return build_media_separation_prompt_block(
        ChunkMediaInput(raw_lines=raw_lines, livechat_lines=chat_lines)
    )


def coalesce_chunk_items(items: list, max_lines: Optional[int] = None) -> List[str]:
    """Merge adjacent ASR fragments to reduce line count without dropping spoken words."""
    clean = [
        (it.get("timestamp", fmt_ts(it.get("start", 0))), it.get("text", "").strip())
        for it in items if it.get("text", "").strip()
    ]
    max_lines = _cfg.COMPACT_CHUNK_MAX_LINES if max_lines is None else max_lines
    if not clean or max_lines <= 0 or len(clean) <= max_lines:
        return [f"({ts}) {txt}" for ts, txt in clean]
    per_line = max(2, (len(clean) + max_lines - 1) // max_lines)
    return [
        f"({clean[i][0]}) " + " ".join(txt for _, txt in clean[i : i + per_line])
        for i in range(0, len(clean), per_line)
    ]


def _format_keyframe_section(keyframes: list) -> str:
    """Format keyframe list and multimodal IMAGE RULES, adding webcam grid guidance when present."""
    kf_lines = [
        f"- {item[3] if len(item) > 3 and item[3] else 'STORYBOARD SCREEN'} Frame {i+1} at timestamp [{item[0]}]"
        for i, item in enumerate(keyframes)
    ]
    has_wc = any("WEBCAM" in str(item[3]).upper() for item in keyframes if len(item) > 3)
    wc_rule = (
        "\n- WEBCAM STORYBOARD (panels read left-to-right top-to-bottom): inspect Pu Boat's facial expression, "
        "hand gestures, camera play, or bed/desk posture alongside STORYBOARD SCREEN to name physical actions/emotions truthfully "
        "and anchor [Reaction] to the exact panel timestamp where the reaction begins."
        if has_wc else ""
    )
    return (
        "KEYFRAMES (each image is labeled with its timestamp):\n"
        + "\n".join(kf_lines)
        + "\nIMAGE RULES:\n"
        + "- Deictic speech ('อันนี้', 'ตัวนี้', 'ดูนี่', 'ในจอ'): name the on-screen subject from the matching frame; use that frame's timestamp.\n"
        + "- Pure visual event -> frame timestamp. Spoken topic shift -> first spoken sentence.\n"
        + "- Showcase/livestream chapter or season titles belong to the showcased game. Confirm game via player title/channel badge.\n"
        + "- STRICT VISUAL HUD & BOSS NAME GROUNDING: copy legible on-screen text exactly (weapon cards, banners, boss HP bars, e.g. Rapier, Lothaire, Slaughtermill). Never invent names."
        + wc_rule
    )


def build_recursive_prompt(
    chunk: dict,
    current_topic: str,
    rolling_summary: str,
    lang: str = "th",
    signal: Optional[dict] = None,
    livechat: str = "",
    activity: str = "",
    mood: str = "",
    world_identity_ref: str = "",
    web_context: str = "",
    vision_context: str = "",
    entity_context: str = "",
    glossary: Optional[dict] = None,
    keyframes: Optional[list] = None,
    recent_timestamps: Optional[List[str]] = None,
    enrichment: Optional[dict] = None,
) -> str:
    """Build prompt for recursive rolling summary state-machine."""
    items = chunk.get("items", [])
    start_ts, end_ts = _chunk_range(items, chunk)
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    lines = coalesce_chunk_items(items)
    transcript_block = "\n".join(lines) if lines else "(no transcript data)"

    extra_tags, domain_block = get_domain_guidance(signal)
    all_tags = list(TAGS)
    for t in extra_tags:
        if t not in all_tags:
            all_tags.append(t)
    tags_list = "  ".join(all_tags)

    domain_section = f"{domain_block}\n" if domain_block else ""
    candidate_weights_block = build_candidate_weights_block(signal)
    candidate_weights_section = f"{candidate_weights_block}\n\n" if candidate_weights_block else ""
    world_identity_section = f"{world_identity_ref}\n" if world_identity_ref else ""

    allowed_sources = None
    if signal:
        allowed = set()
        for cand in signal.get("candidates", []):
            if cand.get("prob", 0.0) >= 0.15:
                f = cand.get("file")
                if f:
                    allowed.add(Path(f).name)
        if signal.get("best_file"):
            allowed.add(Path(signal["best_file"]).name)
        if allowed:
            allowed_sources = allowed

    if not entity_context and glossary:
        entity_context = build_chunk_entity_context(transcript_block, glossary, allowed_sources=allowed_sources)
    entity_section = f"{entity_context}\n" if entity_context else ""

    context_extras = []
    if keyframes:
        context_extras.append(_format_keyframe_section(keyframes))
    if mood:
        context_extras.append(f"Viewer Reaction: {mood}")
    if activity:
        context_extras.append(f"Screen/Webcam State: {activity}")
    if vision_context:
        context_extras.append(f"On-Screen Vision Analysis: {vision_context}")
    if livechat:
        context_extras.append(f"LiveChat Highlights:\n{livechat}")
    if web_context:
        context_extras.append(f"VERIFIED EXTERNAL CONTEXT:\n{web_context}")
    media_block = _build_chunk_media_block(chunk, livechat)
    if media_block:
        context_extras.append(media_block)
    enr_block = format_enrichment_context(enrichment)
    if enr_block:
        context_extras.append(enr_block)

    context_block = ("\n## CONTEXT METRICS\n" + "\n".join(context_extras) + "\n") if context_extras else ""

    topic_section = _format_previous_topic_section(
        chunk.get("_idx", 0),
        current_topic,
        rolling_summary,
        recent_timestamps,
        chunk_start_ts=start_ts,
    )

    prompt = f"""\
You are an expert livestream editor analyzing Chunk {chunk.get('_idx', 0):02d} ({start_ts} - {end_ts}) of a Thai livestream by Pu Boat (Anibon Official).

{topic_section}{context_block}{domain_section}{candidate_weights_section}{world_identity_section}{entity_section}
## YOUR TASK
Analyze Chunk {chunk.get('_idx', 0):02d} ({start_ts} - {end_ts}) against the Previous Topic State.

1. is_continuation: true = same subject/game/activity thread. false = new subject, game, or major pivot (even mid-chunk). Explicit Q&A frames ("เดี๋ยวตอบคำถามนี้", "คำถามสุดท้าย") = shift.

2. timestamps:
   - TOPIC START ANCHOR (LEAD-IN RULE - CRITICAL): HH:MM:SS = the first sentence where Pu Boat starts the new topic ("เดี๋ยวพูดเรื่อง...", "มาดู...", "อีกเรื่องนึง..."). Scan backward from the keyword; never stamp mid-discussion.
   - BUDGET: 1 per chunk by default, 2 max.
   - GAP RULE: if GAP PREDICATE is shown above -> emit exactly 1 stamp (tactical shift, boss phase, progress, or new sub-angle). Otherwise, if this is an ongoing continuation -> [].
   - WORTH A STAMP only if: (a) Pu Boat dwells on it > 1-2 min, or (b) a milestone happens (boss start, victory/defeat, gacha, donation). Passing remarks (< 30s, chat reads, 1-3 sentence mentions) -> skip. Same-thread points -> wrap into one stamp.
   - REACTION VISUAL ONSET: keep separate `[Reaction]` lines when distinct reveals, crashes, physical camera gags (leaning into camera, slumping on desk, showing items, or getting up to lie on the bed behind the chair), or emotional swings occur even 45–120s apart. When a webcam frame captures acute jaw-drop/startle matching a sudden vocal exclamation or audio peak, anchor `HH:MM:SS` directly on that shock onset rather than the follow-up explanation 20–30s later; match genuine anger (`หัวร้อน`/`เดือดจัด`/`สับแหลก`) vs stunned silence (`ชะงักนิ่ง`) vs playful camera/bed acting (`แซว`/`ขำ`/`เล่นกล้อง`/`ลงไปนอนเตียง`).
   - BOSS FIGHTS / VICTORY GUARD (STRICT): stamp boss start ([Boss] ปะทะบอส <Name>), major weapon/phase change, and final outcome only. No stamps for repeated deaths/retries. '[Victory]', 'จนจบการต่อสู้', 'เอาชนะสำเร็จ' require explicit proof (victory banner, reward drop, leaving arena); until then use [Boss]/[Gameplay].
   - Tags: {tags_list} (allowed tags only).
   - HEADLINE RECIPE (3 REQUIRED SLOTS IN ORDER — 8-16 words (50-95 Thai characters)):
     `HH:MM:SS - [Tag] <Verb> <Specific entity> <Concrete takeaway>`
     * Verb: rotate. STRICT VERB DIVERSITY: never repeat the previous stamp's opening verb.
       - Neutral/playful: ส่อง, ชำแหละ, เจาะลึก, เม้าท์มอย, ถกประเด็น, เทียบ, แซว, ทดสอบ, ปะทะ, สำรวจ, วิพากษ์
       - EMOTIONAL TONE MATCHING (CRITICAL): if Pu Boat is genuinely angry, swearing, tilted, or rage-quitting, use หัวร้อน, เดือดจัด, สับแหลก, โวย, บ่นยับ, จวก, หัวเสีย, อารมณ์เสีย, ฟิวส์ขาด, เทเกม — never แซว/เม้าท์มอย/ถกประเด็น/เจาะลึก.
     * Entity: the exact weapon/item/boss/location/character/topic (e.g. พัดขนนกยูง, หุ่น 21). Character + power together; both titles when comparing two works. No pronouns ("เกมนี้", "ค่ายนี้").
     * Takeaway: the outcome or critique (e.g. 'ปะทะบอส Red Archer พร้อมจับจังหวะแพร์รี่และหลบธนูไฟ').
     * Plain line: no 'ใน <ActiveGame>' suffix, NEVER prepend 'เฝ้า <Game/Action> พร้อม...', no filler ('เรื่องการ...', 'พร้อมกับ...'), no inner brackets.
   - FULL LIST REVEAL: describe multi-item reveals accurately across chunks; don't truncate counts.
   - ACTIVE GAME & WATCHPARTY GROUND TRUTH (CRITICAL): the active game/show comes from Active Topic, CANDIDATE DOMAIN WEIGHTS, and WORLD IDENTITY REFERENCE. A passing comparison or joke about another title (Sekiro, Where Winds Meet, Ultraman) is NOT a switch — keep the active title as subject.
   - BROADCAST HIATUS VS. STREAMER SCHEDULE GUARD: 'งดฉาย'/'งดออกอากาศ' = show broadcast break -> 'แจ้งข่าวการงดฉาย...'. Only 'งดไลฟ์'/'งดสตรีม' = Pu Boat's schedule.
   - GROUNDING: every name, chapter/Canto number, and entity must appear in the transcript or WORLD IDENTITY REFERENCE (watch ASR phonetic ghosts/homophones — e.g. `"MP"/"MP4"` when discussing skill charge in combat games = `NP`/`NP4`, truncated names/words must never be emitted half-cut, and phonetic noise must never become unrelated names). Attribute quotes to the named speaker. Unsure -> [Talk] + plain description.
   - STREAMER IDENTITY: 'ปู่โบ๊ต' only — ห้ามสะกดว่า 'ปู่บอท', 'บอท', 'โบต'. Don't start a line with 'ปู่โบ๊ต'.
   - NO HALLUCINATED SUBTITLES CONSTRAINT: ห้ามแปลคำทับศัพท์ภาษาไทยเป็นภาษาอังกฤษโดยพลการ, ห้าม auto-correct (เช่น 'Trickcal' -> 'Critical'), ห้ามเติมสร้อยชื่อ (เช่น ': Rise of a Legend'), ห้ามแทรกคำประเภทในชื่อทางการ, ห้ามตัดคำแหว่ง. ไม่อยู่ใน VERIFIED DOMAIN ENTITIES -> เขียนทับศัพท์ไทย.
   - Pokémon: 'ชื่อไทย (English Name)'.
   - LIVECHAT: not literal ("เบื่อว่ะ" after a gacha win = envy/celebration; trash-unit hype = banter).
   - DUAL TRACK: track gameplay state AND spoken topic in updated_summary; stamps name only the primary spoken topic or gameplay milestone. Spoken discourse beats casual crafting/inventory. Memes get canonical source: 'เพลงอิมาเดโมะ (Ao no Sumika - JJK)'.

3. garbled_notes: real phonetic garbles only (e.g. "ดองซam") as ["word @ HH:MM:SS"]; not normal loanwords (FGO, YouTube). No guessed fixes. [] if none.
4. chunk_summary: 1 short Thai sentence.
5. updated_summary: 1-2 sentences, < 50 words.
6. new_topic_title: 5-8 word Thai title if a new topic starts, else null.

OUTPUT STRICTLY AS JSON:
{{
  "is_continuation": false,
  "timestamps": [
    "HH:MM:SS - [Tag] Description"
  ],
  "garbled_notes": [
    "garbled_token @ HH:MM:SS"
  ],
  "chunk_summary": "...",
  "updated_summary": "...",
  "new_topic_title": "..."
}}

## CHUNK TRANSCRIPT ({start_ts} - {end_ts})
{transcript_block}
"""
    return prompt.strip()


def build_group_prompt(
    chunks: List[dict],
    group_idx: int,
    prev_tail: str,
    lang: str,
    signals_map: dict,
    workspace: Path,
    world_identity_dir: Optional[Path] = None,
    livechat_loader=None,
    activity_loader=None,
    mood_loader=None,
    glossary: Optional[dict] = None,
    enrichment_loader=None,
) -> str:
    """Build group prompt combining 3-5 chunks (~15-25 min) with continuity awareness."""
    group_start = _chunk_range(chunks[0].get("items", []), chunks[0])[0]
    group_end = _chunk_range(chunks[-1].get("items", []), chunks[-1])[1]
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    if prev_tail:
        masked = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*", "", prev_tail).strip()
        prev_section = f"Previous Group Topic (context only):\n[context] {masked}\n"
    else:
        prev_section = "(First group — starting livestream.)\n"

    transcript_blocks = []
    collected_domain_blocks = []
    collected_media_blocks = []
    extra_tags_collected = set()
    best_group_signal: Optional[dict] = None
    best_group_score: float = 0.0

    for ch in chunks:
        idx_str = f"chunk_{ch.get('_idx', 0):02d}"
        c_items = ch.get("items", [])
        c_start, c_end = _chunk_range(c_items, ch)

        sig = signals_map.get(idx_str)
        if sig:
            ex_tags, d_block = get_domain_guidance(sig)
            extra_tags_collected.update(ex_tags)
            if d_block and d_block not in collected_domain_blocks:
                collected_domain_blocks.append(d_block)
            score = sig.get("confidence", 0.0)
            if score > best_group_score and sig.get("best_file"):
                best_group_score = score
                best_group_signal = sig

        lc = livechat_loader(workspace, idx_str) if livechat_loader else ""
        act = activity_loader(workspace, idx_str) if activity_loader else ""
        mood = mood_loader(workspace, idx_str) if mood_loader else ""
        enr = enrichment_loader(workspace, idx_str) if enrichment_loader else None
        enr_block = format_enrichment_context(enr)

        mb = _build_chunk_media_block(ch, lc)
        if mb and mb not in collected_media_blocks:
            collected_media_blocks.append(mb)

        lines = coalesce_chunk_items(c_items)
        ch_text = "\n".join(lines) if lines else "(silent or empty)"
        if enr_block:
            ch_text = f"{enr_block}\n{ch_text}"

        meta_info = []
        if mood:
            meta_info.append(f"Mood: {mood}")
        if act:
            meta_info.append(f"Screen: {act}")
        meta_header = f" [{', '.join(meta_info)}]" if meta_info else ""

        transcript_blocks.append(f"=== {idx_str} ({c_start} - {c_end}){meta_header} ===\n{ch_text}")

    full_group_transcript = "\n\n".join(transcript_blocks)

    all_tags = list(TAGS)
    for t in sorted(extra_tags_collected):
        if t not in all_tags:
            all_tags.append(t)
    tags_list = "  ".join(all_tags)

    domain_guidance = "\n".join(collected_domain_blocks)
    if domain_guidance:
        domain_guidance = f"\n## DOMAIN LORE GUIDANCE\n{domain_guidance}\n"

    media_guidance = "\n\n".join(collected_media_blocks)
    media_section = f"\n{media_guidance}\n" if media_guidance else ""

    wi_ref = load_world_identity_context(best_group_signal, world_identity_dir)
    world_identity_section = f"{wi_ref}\n" if wi_ref else ""

    cand_weights_block = build_candidate_weights_block(best_group_signal)
    candidate_weights_section = f"{cand_weights_block}\n\n" if cand_weights_block else ""

    allowed_sources = None
    if best_group_signal:
        allowed = set()
        for cand in best_group_signal.get("candidates", []):
            if cand.get("prob", 0.0) >= 0.15:
                f = cand.get("file")
                if f:
                    allowed.add(Path(f).name)
        if best_group_signal.get("best_file"):
            allowed.add(Path(best_group_signal["best_file"]).name)
        if allowed:
            allowed_sources = allowed

    entity_ctx = build_chunk_entity_context(full_group_transcript, glossary, allowed_sources=allowed_sources) if glossary else ""
    entity_section = f"{entity_ctx}\n" if entity_ctx else ""

    prompt = f"""\
You are an expert timestamper processing Group {group_idx} (chunks {chunks[0].get('_idx', 0):02d} to {chunks[-1].get('_idx', 0):02d}) of a Thai livestream by Pu Boat (Anibon Official).
Group Time Range: {group_start} - {group_end} (~{len(chunks)*4} minutes)

{prev_section}{domain_guidance}{media_section}{candidate_weights_section}{world_identity_section}{entity_section}
## YOUR TASK

Read the entire group transcript. Output 2 to 4 notable timestamps for major topics or moments in this group.

Format — one line per timestamp:
HH:MM:SS - [Tag] Description

Rules:
- HH:MM:SS MUST literally appear in the transcript within ({group_start} - {group_end}).
- TOPIC START ANCHOR (LEAD-IN RULE - CRITICAL):
  * Always anchor `HH:MM:SS` to the EXACT FIRST opening sentence or transition cue where Pu Boat begins introducing or pivoting to the new topic/activity (e.g. "เดี๋ยวพูดเรื่อง...", "มาดู...", "อีกเรื่องนึง...").
  * NEVER stamp mid-discussion or 20-60s later when the main keyword appears mid-sentence. Scan backward from the keyword to mark the true start of the topic.
- INFORMATIVE HEADLINE DISCIPLINE: Description in {lang_note}. Substantive and descriptive Caveman headline: **8-16 words (50-95 Thai characters)**. Active voice, capturing the specific angle/takeaway with proper nouns. Zero filler clauses ('เรื่องการ...', 'พร้อมกับ...', 'ที่ทำให้...'), and NEVER prepend 'เฝ้าสำรวจ/เฝ้าด่าน <Game> พร้อม...' or append repetitive 'ใน <Game>' suffixes.
- HEADLINE RECIPE (3 REQUIRED SLOTS IN ORDER):
  `HH:MM:SS - [Tag] <Action Verb> + <Specific In-Game Entity/Weapon/Boss/Mechanic OR Spoken Subject> + <Concrete Takeaway/Effect>`
  * Slot 2 MUST name the specific weapon, item, skill, boss, stage, or topic (e.g. 'พัดขนนกยูง', 'เควสคุณยายสมองเสื่อม', 'บอสร่างสอง', 'โหมดเนื้อเรื่อง'). Naming the specific entity satisfies the proper-noun rule without repeating the stream's main game title at the end of the line.
  * Good: `02:02:27 - [Gameplay] ทดสอบอาวุธลับพัดขนนกยูงยิงตอดระยะไกลแต่ดาเมจเบาจึงสลับกลับไปใช้ขวานไฟ`
  * Bad: `02:02:27 - [Gameplay] ทดสอบอาวุธลับยิงไกลแต่ดาเมจเบาใน Phantom Blade Zero` (omits specific item 'พัดขนนกยูง' and pads with 'ใน <Game>').
- Tags: {tags_list} (Strictly use allowed tags; do NOT invent new tags).
- CONTINUITY & DEDUPLICATION RULE:
  * If consecutive chunks discuss the same topic or review the same game/subject, emit ONLY ONE timestamp when the topic starts.
  * Do NOT emit micro-stamps for minor conversational pauses within the same topic.
  * Emit timestamps ONLY for true topic shifts, reactions, donations, or gameplay transitions.
  * REACTION VISUAL ONSET: Keep separate `[Reaction]` lines when distinct reveals, crashes, physical camera gags (leaning into camera, slumping on desk, showing items, or getting up to lie on the bed behind the chair), or emotional swings occur even 45–120s apart. Anchor `HH:MM:SS` to initial reaction/reveal onset; match genuine anger (`หัวร้อน`/`เดือดจัด`/`สับแหลก`) vs stunned silence (`ชะงักนิ่ง`) vs playful camera/bed acting (`แซว`/`ขำ`/`เล่นกล้อง`/`ลงไปนอนเตียง`).
  * STRICT PASSING MENTIONS FILTER: Do NOT stamp brief passing remarks or 1-3 sentence off-hand mentions where Pu Boat merely touches upon a subject without deep dive or substantive analysis (e.g. reading a chat comment, casual mentions of other games/consoles, fleeting remarks). Timestamp ONLY when speaker actively dwells and analyzes the topic for >1-2 minutes or several paragraphs.
  * PASSIVE GAMEPLAY GUARD: When casual crafting/inventory occurs in a sandbox game (e.g. Minecraft), spoken discussion strictly trumps casual in-game actions. Never stamp minor recipe crafting or item checking over substantive discourse, roasts, or songs.
  * Explicit Q&A question frames ("เดี๋ยวตอบคำถามนี้", "ปู่ปู่ว่า...", "คำถามสุดท้าย") count as topic switches.
- PROPER NOUN IN EVERY STAMP: Every timestamp must name its specific proper noun (e.g. actual game title, anime title, or character name from context). Never use vague pronouns ("เกมนี้", "คนนี้"). The summarizer must NEVER drop proper nouns to fit limits; trim adjectives or emotional filler instead.
- FULL LIST REVEAL RULE: If streamer reveals a multi-item list or update across chunks, do not prematurely truncate count; describe the accurate ongoing reveal.
- ACTIVE GAME GROUND TRUTH (CRITICAL): The primary game of this livestream is defined by the CANDIDATE DOMAIN WEIGHTS and WORLD IDENTITY REFERENCE above. If the streamer mentions another game merely in passing or makes a comparative remark (e.g. comparing combat/AI/farm to 'Where Winds Meet', 'Black Myth: Wukong', or 'Sekiro'), DO NOT hallucinate that the streamer switched games! The streamer remains in the active game. Specifically, for Phantom Blade Zero streams, NEVER label ongoing gameplay or boss encounters as 'Where Winds Meet'.
- ANTI-HALLUCINATION & WORLD IDENTITY GROUNDING: Every game/character name, story Canto/Chapter number, and entity MUST appear in or be verified against transcript text or the WORLD IDENTITY REFERENCE above. If the stream covers a story chapter (e.g. Limbus Company Canto X vs Canto VI/VII), NEVER hallucinate or regress chapter numbers based on older training data; strictly adhere to the WORLD IDENTITY REFERENCE timeline and transcript evidence. Beware of ASR phoneme ghosts or mishearing (e.g. "บัวใคร" = Blue Archive). If unsure or single-mention noise, use [Talk] with event description only. Never guess names or chapter numbers.
- STREAMER IDENTITY: สตรีมเมอร์คือ 'ปู่โบ๊ต' (Boat) เท่านั้น ห้ามสะกดว่า 'ปู่บอท', 'บอท', หรือ 'โบต' ห้ามขึ้นต้นบรรทัด Timestamp หรือหัวข้อด้วยคำว่า 'ปู่โบ๊ต' (ผู้ชมรู้อยู่แล้วว่าเป็นไลฟ์ปู่โบ๊ต) และห้ามขึ้นต้นด้วยคำกริยาเดิมซ้ำๆ ติดกัน (เช่น 'พูดถึง...', 'วิเคราะห์...' ซ้ำทุกบรรทัด) ให้เขียนแบบ Caveman กระชับ ตรงประเด็น ขึ้นต้นด้วยกริยาหลากหลายหรือชื่อเรื่อง/ประเด็นทันที
- ANTI-GUESSING CONSTRAINT: ห้ามแปลคำทับศัพท์ภาษาไทยเป็นภาษาอังกฤษโดยพลการเด็ดขาด หากไม่มีใน VERIFIED DOMAIN ENTITIES ให้เขียนทับศัพท์ภาษาไทยหรือบรรยายการกระทำเป็นภาษาไทย ห้ามแต่งชื่อภาษาอังกฤษใหม่
- POKÉMON NAMING RULE: หากมีการพูดถึงโปเกมอน ให้เขียนในรูปแบบ 'ชื่อไทย (English Name)' หรือชื่อทางการไทยเสมอ
- THAI LIVECHAT PSYCHOLOGY: Do not interpret viewer chat literally ("เบื่อว่ะ/กด dislike ละ" upon winning gacha = playful envy/celebration; 1-star hype = meme banter).
- First-verb guidance: แซว, ฮาลั่น!, เม้าท์มอย, ชำแหละ, จวกยับ, สับแหลก, วิเคราะห์, อึ้ง!, เหวอ, โวย, เดือดจัด, หัวร้อน, ฟิวส์ขาด (match true speaker emotion — never use 'แซว'/'ถกประเด็น'/'เจาะลึก' when speaker is genuinely angry or tilted).
- Output ONLY 2 to 4 timestamp lines in chronological order. Immediately STOP after the last timestamp. Do NOT repeat or output a second list. No preamble, no explanation.

## GROUP TRANSCRIPT ({group_start} - {group_end})
{full_group_transcript}
"""
    return prompt.strip()
