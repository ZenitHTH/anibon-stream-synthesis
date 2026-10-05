"""Prompt building for local LLM timestamping.

Supports:
- Recursive rolling summary prompts with 1-3 timestamps array and continuity flags
- Group batching prompts (~16-20 min windows)
- World Identity markdown lore injection
- Multi-modal context (LiveChat, 555 mood, visual activity) & Web search snippets
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from anibon.time import fmt_ts
from anibon.timestamps import TAGS
from signal_detector import get_domain_guidance

_SCRIPT_DIR = Path(__file__).resolve().parent
_WI_CANDIDATES = [
    _SCRIPT_DIR.parent.parent / "anibon-world-identity" / "references",
    _SCRIPT_DIR.parent.parent.parent / "anibon-world-identity" / "references",
]
WORLD_IDENTITY_DIR: Optional[Path] = next((p for p in _WI_CANDIDATES if p.is_dir()), None)
_WI_SNIPPET_LIMIT = 4000


def _chunk_range(items: list) -> Tuple[str, str]:
    if not items:
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

    best_file = signal.get("best_file") or ""
    if not best_file:
        return ""

    candidate = ref_dir / Path(best_file).name
    if not candidate.exists():
        stem = Path(best_file).stem.lower()
        matches = [p for p in ref_dir.glob("*.md") if p.stem.lower() == stem]
        candidate = matches[0] if matches else None

    if not candidate or not candidate.exists():
        return ""

    try:
        text = candidate.read_text(encoding="utf-8")
    except Exception:
        return ""

    snippet = text[:_WI_SNIPPET_LIMIT]
    if len(text) > _WI_SNIPPET_LIMIT:
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


def build_recursive_prompt(
    chunk: dict,
    current_topic: str,
    rolling_summary: str,
    lang: str,
    signal: Optional[dict] = None,
    livechat: str = "",
    activity: str = "",
    mood: str = "",
    world_identity_ref: str = "",
    web_context: str = "",
    vision_context: str = "",
) -> str:
    """Build prompt for recursive rolling summary state-machine."""
    items = chunk.get("items", [])
    start_ts, end_ts = _chunk_range(items)
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    lines = [f"({it.get('timestamp', fmt_ts(it.get('start', 0)))}) {it.get('text', '').strip()}"
             for it in items if it.get("text", "").strip()]
    transcript_block = "\n".join(lines) if lines else "(no transcript data)"

    extra_tags, domain_block = get_domain_guidance(signal)
    all_tags = list(TAGS)
    for t in extra_tags:
        if t not in all_tags:
            all_tags.append(t)
    tags_list = "  ".join(all_tags)

    domain_section = f"{domain_block}\n" if domain_block else ""
    world_identity_section = f"{world_identity_ref}\n" if world_identity_ref else ""

    context_extras = []
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

    context_block = ("\n## CONTEXT METRICS\n" + "\n".join(context_extras) + "\n") if context_extras else ""

    if current_topic:
        topic_section = f"""## PREVIOUS TOPIC STATE (Chunk {chunk.get('_idx', 0) - 1:02d})
Active Topic: {current_topic}
Recent Focus: {rolling_summary}
"""
    else:
        topic_section = "## PREVIOUS TOPIC STATE\n(No previous topic — livestream is starting)\n"

    prompt = f"""\
You are an expert livestream editor analyzing Chunk {chunk.get('_idx', 0):02d} ({start_ts} - {end_ts}) of a Thai livestream by Pu Boat (Anibon Official).

{topic_section}{context_block}{domain_section}{world_identity_section}
## YOUR TASK
Analyze Chunk {chunk.get('_idx', 0):02d} ({start_ts} - {end_ts}) with respect to the Previous Topic State above.

Rules:
1. is_continuation:
   - true: Speaker is still on the same broader subject, gameplay session, or ongoing thread.
   - false: Speaker completely shifted to a brand new subject, different game, or major activity pivot.
   - Exception: Explicit Q&A question frames ("เดี๋ยวตอบคำถามนี้", "ปู่ปู่ว่า...", "คำถามสุดท้าย") count as topic shifts.

2. timestamps:
   - OUTPUT BUDGET: Provide 1 timestamp by default, 2 MAX per chunk ({start_ts} - {end_ts}).
     Do NOT micro-stamp conversational pauses or minor dialogue turns within the same game or talk topic.
   - Output an EMPTY list [] if this chunk is a continuation (same game, same activity, no major event shift like Boss/Death/Victory/Cutscene/Donation).
   - LONG-FORM TALK/NEWS EXCEPTION (CRITICAL FOR MONOLOGUES & SOCIAL CRITIQUE):
     If the speaker continues discussing the same broad news, political, or societal subject across multiple chunks (>8-10 minutes without any timestamp), you MUST NOT leave it blank as an empty continuation.
     Identify any distinct sub-angle, specific policy/news critique, concrete case study, or notable shift in focus (e.g. specific data, secondary news item, viewer debate, geographic analysis) and emit 1 timestamp marking that sub-topic (using [Talk] or [News]) so long monologues are properly indexable.
   - STRICT PASSING MENTIONS & OFF-HAND REMARKS FILTER (CRITICAL):
     DO NOT emit timestamps for brief passing remarks, 1-3 sentence off-hand mentions, or momentary tangents where Pu Boat merely touches upon a subject without deep dive or substantive analysis (e.g. merely reading a chat comment, saying "เห็นข่าวเกม X แวบๆ", "เดี๋ยวค่อยว่ากัน", casual hello to a chatter, fleeting side comments, mentioning a console/game name in passing).
     A timestamp is WARRANTED ONLY IF:
     1) Pu Boat actively dwells and spends SUBSTANTIAL focused discussion (several paragraphs, >1-2 minutes) analyzing, explaining, critiquing, or reacting deeply to that specific subject.
     2) OR an unambiguous gameplay milestone occurs (Boss encounter, Death, Victory, Gacha roll, Donation).
     If Pu Boat only mentions something briefly in passing without deep-dive discussion, you MUST IGNORE IT or output [].
   - Tags: {tags_list} (Strictly use allowed tags).
   - First-verb: แซว, ฮาลั่น!, เม้าท์มอย, ชำแหละ, จวกยับ, สับเละ, วิเคราะห์, ส่อง, อึ้ง!, เหวอ.
   - PROPER NOUN IN EVERY STAMP: Every timestamp must name its specific proper noun (e.g. Wuthering Waves, Zelda, Bleach). Never use vague pronouns ("เกมนี้", "น้องคนนั้น", "ค่ายนี้"). The summarizer must NEVER drop proper nouns to fit limits; trim adjectives or emotional filler instead.
   - FULL LIST REVEAL RULE: If streamer reveals a multi-item list or update across chunks, do not prematurely truncate count; describe the accurate ongoing reveal.
   - ANTI-HALLUCINATION & WORLD IDENTITY GROUNDING: Every game/character name, story Canto/Chapter number, and entity MUST appear in or be verified against transcript text or the WORLD IDENTITY REFERENCE above. If the stream covers a story chapter (e.g. Limbus Company Canto X vs Canto VI/VII), NEVER hallucinate or regress chapter numbers based on older training data; strictly adhere to the WORLD IDENTITY REFERENCE timeline and transcript evidence. Beware of ASR phoneme ghosts (e.g. "บัวใคร" = Blue Archive, "Wing Wave" = Wuthering Waves). If game title is unclear or single-mention noise, use [Talk] with event description only. Never guess names or chapter numbers.
   - THAI LIVECHAT PSYCHOLOGY: Do not interpret viewer chat literally. "เบื่อว่ะ/กด dislike ละ" upon winning gacha = playful envy/celebration. Irony/trash-unit hype ("Eric คือ META") = community banter.

3. garbled_notes:
   - Array of phonetic hybrids / garbled words spotted in transcript that survived cleaning (e.g. Thai-Latin hybrids like "ดองซam", "โinaa" or phonetically mutilated proper nouns) with timestamp: ["word @ HH:MM:SS", ...].
   - Spot ONLY real phonetic garbles, NOT standard loanwords (FGO, NP, YouTube, AI). Do NOT guess replacement; audio ground truth will be resolved automatically. Return [] if none.

4. chunk_summary: 1 short sentence summarizing what happens in this chunk in Thai.
5. updated_summary: 1-2 concise sentences (under 50 words) updating the rolling summary context.
6. new_topic_title: Specific Thai title (5-8 words) if this chunk starts a new topic, or null if continuing.

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
) -> str:
    """Build group prompt combining 3-5 chunks (~15-25 min) with continuity awareness."""
    first_items = chunks[0].get("items", [])
    last_items = chunks[-1].get("items", [])
    group_start = fmt_ts(first_items[0].get("start", 0)) if first_items else "00:00:00"
    group_end = fmt_ts(last_items[-1].get("start", 0) + last_items[-1].get("duration", 5)) if last_items else "00:00:00"
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    if prev_tail:
        masked = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*", "", prev_tail).strip()
        prev_section = f"Previous Group Topic (context only):\n[context] {masked}\n"
    else:
        prev_section = "(First group — starting livestream.)\n"

    transcript_blocks = []
    collected_domain_blocks = []
    extra_tags_collected = set()
    best_group_signal: Optional[dict] = None
    best_group_score: float = 0.0

    for ch in chunks:
        idx_str = f"chunk_{ch.get('_idx', 0):02d}"
        c_items = ch.get("items", [])
        c_start, c_end = _chunk_range(c_items)

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

        lines = [f"({it.get('timestamp', fmt_ts(it.get('start', 0)))}) {it.get('text', '').strip()}"
                 for it in c_items if it.get("text", "").strip()]
        ch_text = "\n".join(lines) if lines else "(silent or empty)"

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

    wi_ref = load_world_identity_context(best_group_signal, world_identity_dir)
    world_identity_section = f"{wi_ref}\n" if wi_ref else ""

    prompt = f"""\
You are an expert timestamper processing Group {group_idx} (chunks {chunks[0].get('_idx', 0):02d} to {chunks[-1].get('_idx', 0):02d}) of a Thai livestream by Pu Boat (Anibon Official).
Group Time Range: {group_start} - {group_end} (~{len(chunks)*4} minutes)

{prev_section}{domain_guidance}{world_identity_section}
## YOUR TASK

Read the entire group transcript. Output 2 to 4 notable timestamps for major topics or moments in this group.

Format — one line per timestamp:
HH:MM:SS - [Tag] Description

Rules:
- HH:MM:SS MUST literally appear in the transcript within ({group_start} - {group_end}).
- Description in {lang_note}. Max 12 words. Active voice.
- Tags: {tags_list} (Strictly use allowed tags; do NOT invent new tags).
- CONTINUITY & DEDUPLICATION RULE:
  * If consecutive chunks discuss the same topic or review the same game/subject, emit ONLY ONE timestamp when the topic starts.
  * Do NOT emit micro-stamps for minor conversational pauses within the same topic.
  * Emit timestamps ONLY for true topic shifts, reactions, donations, or gameplay transitions.
  * STRICT PASSING MENTIONS FILTER: Do NOT stamp brief passing remarks or 1-3 sentence off-hand mentions where Pu Boat merely touches upon a subject without deep dive or substantive analysis (e.g. reading a chat comment, casual mentions of other games/consoles, fleeting remarks). Timestamp ONLY when speaker actively dwells and analyzes the topic for >1-2 minutes or several paragraphs.
  * Explicit Q&A question frames ("เดี๋ยวตอบคำถามนี้", "ปู่ปู่ว่า...", "คำถามสุดท้าย") count as topic switches.
- PROPER NOUN IN EVERY STAMP: Every timestamp must name its specific proper noun (e.g. Wuthering Waves, Zelda, Bleach). Never use vague pronouns ("เกมนี้", "คนนี้"). The summarizer must NEVER drop proper nouns to fit limits; trim adjectives or emotional filler instead.
- FULL LIST REVEAL RULE: If streamer reveals a multi-item list or update across chunks, do not prematurely truncate count; describe the accurate ongoing reveal.
- ANTI-HALLUCINATION & WORLD IDENTITY GROUNDING: Every game/character name, story Canto/Chapter number, and entity MUST appear in or be verified against transcript text or the WORLD IDENTITY REFERENCE above. If the stream covers a story chapter (e.g. Limbus Company Canto X vs Canto VI/VII), NEVER hallucinate or regress chapter numbers based on older training data; strictly adhere to the WORLD IDENTITY REFERENCE timeline and transcript evidence. Beware of ASR phoneme ghosts (e.g. "บัวใคร" = Blue Archive, "Wing Wave" = Wuthering Waves). If unsure or single-mention noise, use [Talk] with event description only. Never guess names or chapter numbers.
- THAI LIVECHAT PSYCHOLOGY: Do not interpret viewer chat literally ("เบื่อว่ะ/กด dislike ละ" upon winning gacha = playful envy/celebration; 1-star hype = meme banter).
- First-verb guidance: แซว, ฮาลั่น!, เม้าท์มอย, ชำแหละ, จวกยับ, สับเละ, วิเคราะห์, อึ้ง!, เหวอ.
- Output ONLY 2 to 4 timestamp lines in chronological order. Immediately STOP after the last timestamp. Do NOT repeat or output a second list. No preamble, no explanation.

## GROUP TRANSCRIPT ({group_start} - {group_end})
{full_group_transcript}
"""
    return prompt.strip()
