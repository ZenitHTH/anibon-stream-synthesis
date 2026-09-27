"""
process_chunks_local.py — Local LLM chunk runner for Anibon timestamping on Tesla P100 (16GB).

Two execution modes:
1. --mode recursive (RECOMMENDED): Dynamic rolling summary state-machine.
   Tracks topic flow across chunks organically (not locked to arbitrary minutes).
   Accumulates rolling context when topics continue, flushes summary when topics pivot.
2. --mode group: Batched processing across groups of chunks (~16-20 min windows).

Includes:
- Multi-modal context fusion (LiveChat messages, 555 laugh pulses, Storyboard visual activity).
- Corpus-level signal detection & dynamic domain prompt injection.
- Tag whitelist enforcement & auto-normalization.
- Two-pass architecture: Pass 1 (Topic Segmentation) -> Pass 2 (Local Summarizer for parts & Caveman headers).
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple

try:
    from signal_detector import (
        load_mappings,
        normalize_transcript,
        detect_signals_for_chunks,
        get_domain_guidance,
    )
except ImportError:
    from scripts.signal_detector import (
        load_mappings,
        normalize_transcript,
        detect_signals_for_chunks,
        get_domain_guidance,
    )

# ── Constants ────────────────────────────────────────────────────────────────

TAGS = (
    "[Greeting]", "[Talk]", "[News]", "[Chat]", "[Donation]",
    "[Gameplay]", "[Gacha]", "[Boss]", "[Death]", "[Victory]",
    "[WatchParty]", "[Reaction]", "[Story]", "[Lore]", "[Review]",
)

TAG_REMAP = {
    "วิเคราะห์": "Talk",
    "เจาะลึก": "Talk",
    "ชำแหละ": "Talk",
    "บ่น": "Talk",
    "บ่นอุบ": "Talk",
    "คุย": "Talk",
    "เม้าท์": "Talk",
    "เม้าท์มอย": "Talk",
    "ส่อง": "Reaction",
    "ฮา": "Reaction",
    "เหวอ": "Reaction",
    "อึ้ง": "Reaction",
    "เปิดตัว": "News",
    "อัปเดต": "News",
    "ข่าว": "News",
    "Game News": "News",
    "ตอบแชท": "Chat",
    "ถามตอบ": "Chat",
    "ขอบคุณ": "Donation",
    "โดเนท": "Donation",
    "เล่นเกม": "Gameplay",
    "ลองเล่น": "Gameplay",
    "กาชา": "Gacha",
    "เปิดกาชา": "Gacha",
    "สู้บอส": "Boss",
}

SYSTEM_PROMPT = """\
You are an expert livestream editor for Thai livestreams by Pu Boat (Anibon Official).
CRITICAL INSTRUCTION: Keep your internal thinking under 2 sentences. \
Do NOT list items or transcribe text in your thinking. \
Proceed immediately to outputting the final decision."""

# ── Formatting & Time Helpers ────────────────────────────────────────────────

def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def ts_to_sec(ts: str) -> int:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _chunk_range(items: list) -> Tuple[str, str]:
    if not items:
        return "00:00:00", "00:00:00"
    start = items[0].get("start", 0)
    last = items[-1]
    end = last.get("start", 0) + last.get("duration", 5)
    return _fmt_ts(start), _fmt_ts(end)

# ── Multi-Modal Context Helpers ──────────────────────────────────────────────

def load_chunk_livechat(workspace: Path, chunk_idx: str) -> str:
    """Return top chat snippet for this chunk if available."""
    lc_file = workspace / "livechat" / f"livechat_{chunk_idx}.txt"
    if lc_file.exists():
        try:
            lines = [l.strip() for l in lc_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                return "\n".join(lines[:6])
        except Exception:
            pass
    return ""


def load_chunk_activity(workspace: Path, chunk_idx: str) -> str:
    """Return visual activity summary (game on screen, webcam state) if available."""
    act_file = workspace / "activity" / f"activity_{chunk_idx}.txt"
    if act_file.exists():
        try:
            return act_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def load_chunk_mood(workspace: Path, chunk_idx: str) -> str:
    """Return 555 laugh/meme pulse verdict if available."""
    mood_file = workspace / "mood_555.json"
    if mood_file.exists():
        try:
            with open(mood_file, encoding="utf-8") as f:
                data = json.load(f)
                info = data.get(chunk_idx)
                if info and info.get("verdict") and info.get("verdict") != "QUIET":
                    tone_desc = info.get("tone", {}).get("tone", "")
                    return f"Chat Mood: {info.get('verdict')} ({tone_desc})"
        except Exception:
            pass
    return ""

# ── Tag Sanitization & Normalization ─────────────────────────────────────────

def normalize_tag(match: re.Match) -> str:
    tag = match.group(1).strip()
    if tag in TAG_REMAP:
        return f"[{TAG_REMAP[tag]}]"
    return f"[{tag}]"


def sanitize_timestamp_line(line: str) -> str:
    """Strip reasoning, comments, and normalize tags."""
    line = re.sub(r"\s*-\s*\d+\s*words.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\.?\s*Wait,\s*.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*(?:Or just describe|Note:|Remark:).*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\([A-Za-z\s\?\,\.\-\:\'\/]{8,}\).*$", "", line)
    line = re.sub(r"\s*\([A-Za-z0-9\s\?\,\.\-\:\'\/]+\)\.?$", "", line)
    line = re.sub(r"^[`'\"]+|[`'\"\\.]+$", "", line.strip())

    # Tag Normalization: remap non-standard tags like [วิเคราะห์] -> [Talk]
    line = re.sub(r"\[([^\]]+)\]", normalize_tag, line, count=1)
    return line.strip()


def parse_timestamps(raw: str, max_stamps: int = 4) -> List[str]:
    """Extract and sanitize valid HH:MM:SS - [Tag] lines from model output.

    Guards against LLM repetition loops (where the model restarts from the first timestamp)
    and timestamp collisions (where multiple timestamps have identical seconds or are <60s apart).
    """
    lines = []
    prev_sec = None
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^(\d{2}):(\d{2}):(\d{2})\s*-\s*\[", line)
        if m:
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))

            # 1. Chronological Loop Breaker:
            if prev_sec is not None and sec <= prev_sec:
                break

            # 2. Collision Guard (< 60s):
            if prev_sec is not None and (sec - prev_sec) < 60:
                continue

            cleaned = sanitize_timestamp_line(line)
            if cleaned:
                lines.append(cleaned)
                prev_sec = sec

            if len(lines) >= max_stamps:
                break

    return lines


def validate_timestamps(stamps: List[str], start_sec: int, end_sec: int) -> List[str]:
    """Discard stamps falling outside [start_sec - 60, end_sec + 60]."""
    lo = max(0, start_sec - 60)
    hi = end_sec + 60
    valid = []
    for stamp in stamps:
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})", stamp)
        if not m:
            continue
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        if lo <= sec <= hi:
            valid.append(stamp)
        else:
            print(f"  [drop] out-of-range stamp {stamp[:8]} (window {_fmt_ts(start_sec)}-{_fmt_ts(end_sec)})")
    return valid


def is_continuation(raw: str) -> bool:
    upper = raw.upper().strip()
    return (upper == "SKIP" or upper == "CONTINUATION") and not re.search(r"\d{2}:\d{2}:\d{2}", raw)

# ── Prompt Building ──────────────────────────────────────────────────────────

def build_recursive_prompt(
    chunk: dict,
    current_topic: str,
    rolling_summary: str,
    lang: str,
    signal: Optional[dict] = None,
    livechat: str = "",
    activity: str = "",
    mood: str = ""
) -> str:
    """Build prompt for recursive rolling summary state-machine."""
    items = chunk.get("items", [])
    start_ts, end_ts = _chunk_range(items)
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    lines = [f"({it.get('timestamp', _fmt_ts(it.get('start', 0)))}) {it.get('text', '').strip()}"
             for it in items if it.get("text", "").strip()]
    transcript_block = "\n".join(lines) if lines else "(no transcript data)"

    extra_tags, domain_block = get_domain_guidance(signal)
    all_tags = list(TAGS)
    for t in extra_tags:
        if t not in all_tags:
            all_tags.append(t)
    tags_list = "  ".join(all_tags)

    domain_section = f"{domain_block}\n" if domain_block else ""
    context_extras = []
    if mood:
        context_extras.append(f"Viewer Reaction: {mood}")
    if activity:
        context_extras.append(f"Screen/Webcam State: {activity}")
    if livechat:
        context_extras.append(f"LiveChat Highlights:\n{livechat}")
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

{topic_section}{context_block}{domain_section}
## YOUR TASK
Compare the main subject discussed in Chunk {chunk.get('_idx', 0):02d} with the Active Topic and Recent Focus above.
Decide if this chunk continues the exact same subject, or shifts to a new topic (or different focus).

Rules:
1. is_continuation:
   - true: The speaker is directly continuing the EXACT same subject or activity (e.g. still discussing the same game event, still in the same boss battle, still on the same drama).
   - false: The speaker shifts to a DIFFERENT subject, game, event, review, news item, or activity (e.g., from game news to card game drama, from general chatter to FGO event farming, from talk to gameplay).
   NOTE: Merely being in the same livestream or general gaming category is NOT continuation. If the specific subject or focus changed, mark is_continuation: false!

2. chunk_summary: 1 short sentence summarizing what happens in this chunk in Thai.
3. If is_continuation is true:
   - updated_summary: 1-2 concise sentences (under 50 words) summarizing current progress. Do NOT concatenate long paragraphs.
   - new_topic_title: null
   - new_timestamp: null
4. If is_continuation is false (TOPIC SHIFT):
   - new_topic_title: Specific Thai title (5-8 words). NEVER create broad compound titles like "เกมใหม่และดราม่า...".
   - updated_summary: 1-2 sentences summarizing this new topic.
   - new_timestamp: Format "HH:MM:SS - [Tag] Description" where HH:MM:SS is an exact timestamp appearing in the transcript ({start_ts} - {end_ts}).
     Tags: {tags_list} (Strictly use allowed tags; do NOT invent new tags).
     First-verb: แซว, ฮาลั่น!, เม้าท์มอย, ชำแหละ, จวกยับ, สับเละ, วิเคราะห์, ส่อง, อึ้ง!, เหวอ.

OUTPUT STRICTLY AS JSON:
{{
  "is_continuation": false,
  "chunk_summary": "...",
  "updated_summary": "...",
  "new_topic_title": "...",
  "new_timestamp": "HH:MM:SS - [Tag] Description"
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
) -> str:
    """Build group prompt combining 3-5 chunks (~15-25 min) with continuity awareness."""
    first_items = chunks[0].get("items", [])
    last_items = chunks[-1].get("items", [])
    group_start = _fmt_ts(first_items[0].get("start", 0)) if first_items else "00:00:00"
    group_end = _fmt_ts(last_items[-1].get("start", 0) + last_items[-1].get("duration", 5)) if last_items else "00:00:00"
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    if prev_tail:
        masked = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*", "", prev_tail).strip()
        prev_section = f"Previous Group Topic (context only):\n[context] {masked}\n"
    else:
        prev_section = "(First group — starting livestream.)\n"

    transcript_blocks = []
    collected_domain_blocks = []
    extra_tags_collected = set()

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

        lc = load_chunk_livechat(workspace, idx_str)
        act = load_chunk_activity(workspace, idx_str)
        mood = load_chunk_mood(workspace, idx_str)

        lines = [f"({it.get('timestamp', _fmt_ts(it.get('start', 0)))}) {it.get('text', '').strip()}"
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

    prompt = f"""\
You are an expert timestamper processing Group {group_idx} (chunks {chunks[0].get('_idx', 0):02d} to {chunks[-1].get('_idx', 0):02d}) of a Thai livestream by Pu Boat (Anibon Official).
Group Time Range: {group_start} - {group_end} (~{len(chunks)*4} minutes)

{prev_section}{domain_guidance}
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
- First-verb guidance: แซว, ฮาลั่น!, เม้าท์มอย, ชำแหละ, จวกยับ, สับเละ, วิเคราะห์, อึ้ง!, เหวอ.
- Output ONLY 2 to 4 timestamp lines in chronological order. Immediately STOP after the last timestamp. Do NOT repeat or output a second list. No preamble, no explanation.

## GROUP TRANSCRIPT ({group_start} - {group_end})
{full_group_transcript}
"""
    return prompt.strip()

# ── LM Studio & API Call ─────────────────────────────────────────────────────

def get_loaded_models() -> List[str]:
    """Query LM Studio CLI for currently loaded models in memory."""
    try:
        res = subprocess.run(
            ["lms", "ps", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return [m.get("identifier") for m in data if m.get("identifier")]
    except Exception:
        pass
    return []


def resolve_model(requested_model: str, endpoint: str, force: bool = False) -> str:
    """Resolve which model to use, preventing JIT eviction on Tesla P100."""
    loaded = get_loaded_models()
    if loaded:
        print(f"[init] LM Studio loaded model(s): {', '.join(loaded)}")
        if not requested_model or requested_model.lower() == "auto":
            for preferred in ("google/gemma-4-12b-qat", "qwen/qwen3.5-9b"):
                if preferred in loaded:
                    print(f"[init] Auto-selected loaded model: {preferred}")
                    return preferred
            return loaded[0]

        if requested_model in loaded:
            print(f"[init] Using requested loaded model: {requested_model}")
            return requested_model

        if force:
            return requested_model

        fallback = loaded[0]
        for preferred in ("google/gemma-4-12b-qat", "qwen/qwen3.5-9b"):
            if preferred in loaded:
                fallback = preferred
                break
        print(f"[warn] '{requested_model}' not loaded; using '{fallback}' to prevent eviction.", file=sys.stderr)
        return fallback

    return "google/gemma-4-12b-qat" if (not requested_model or requested_model.lower() == "auto") else requested_model


def call_local(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call local OpenAI-compatible API."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    msg = data["choices"][0]["message"]
    content = msg.get("content", "").strip()

    if not content and msg.get("reasoning_content"):
        rc = msg["reasoning_content"]
        if "ส่วนที่" in rc or "════" in rc:
            content = rc
        else:
            m = re.findall(r"(\d{2}:\d{2}:\d{2}\s*-\s*\[[\w]+\]\s*[^\n]+)", rc)
            if m:
                content = "\n".join(m)
            elif "CONTINUATION" in rc.upper() or "SKIP" in rc.upper():
                content = "CONTINUATION"
            else:
                content = rc

    return content

# ── Chunk Discovery & Loading ────────────────────────────────────────────────

def discover_chunks(workspace: Path) -> List[Path]:
    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        raise FileNotFoundError(f"No chunks dir: {chunks_dir}")

    files = sorted(
        list(chunks_dir.glob("chunk_*.txt")) + list(chunks_dir.glob("chunk_*.json")),
        key=lambda f: int(re.search(r"chunk_(\d+)", f.stem).group(1)),
    )
    if not files:
        raise FileNotFoundError(f"No chunk files in: {chunks_dir}")
    return files


def load_chunk_file(path: Path, mappings: Optional[list] = None) -> dict:
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if mappings:
            for it in data.get("items", []):
                if it.get("text"):
                    it["text"] = normalize_transcript(it["text"], mappings)
        return data

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    items = []
    start_sec = 0
    end_sec = 0
    cutoff = 0

    if lines:
        header = lines[0]
        m = re.search(r"(\d{2}:\d{2}:\d{2})[–-](\d{2}:\d{2}:\d{2})", header)
        if m:
            start_sec = ts_to_sec(m.group(1))
            end_sec = ts_to_sec(m.group(2))
        mc = re.search(r"cutoff=(\d{2}:\d{2}:\d{2})", header)
        if mc:
            cutoff = ts_to_sec(mc.group(1)) if mc else end_sec

        for line in lines[1:]:
            lm = re.match(r"\((\d{2}:\d{2}:\d{2})\)\s+(.*)", line)
            if lm:
                ts = lm.group(1)
                sec = ts_to_sec(ts)
                if cutoff and sec > cutoff:
                    continue
                raw_text = lm.group(2)
                clean_text = normalize_transcript(raw_text, mappings) if mappings else raw_text
                items.append({"start": float(sec), "timestamp": ts, "text": clean_text})

    return {"start_sec": start_sec, "end_sec": end_sec, "items": items}

# ── State Management ─────────────────────────────────────────────────────────

def load_state(workspace: Path) -> dict:
    state_path = workspace / "anibon_timestamper_state.json"
    if state_path.exists():
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(workspace: Path, state: dict) -> None:
    state_path = workspace / "anibon_timestamper_state.json"
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── Local Summarizer Pass & Assembly ─────────────────────────────────────────

def run_local_summarizer_pass(
    endpoint: str,
    model: str,
    all_stamps: List[str],
    workspace: Path,
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> Optional[str]:
    """Call Gemma 4 locally to partition timestamps into Parts with Caveman summaries."""
    if not all_stamps:
        return None

    raw_list = "\n".join(all_stamps)
    prompt = f"""\
You are an expert livestream editor for Anibon Official.
Below are {len(all_stamps)} timestamps from a livestream by Pu Boat.

## YOUR TASK:
Divide these timestamps into 3 to 4 logical Parts for YouTube comments (each part roughly 40-50 minutes).
For each part, specify:
1. The start timestamp where this part begins.
2. A punchy Thai summary header (2-3 short sentences in Thai, highlighting major drama, news, or gameplay).

Format strictly as:
Part 1: 00:00:00
Summary: [Thai Summary 2-3 sentences]

Part 2: HH:MM:SS
Summary: [Thai Summary 2-3 sentences]

Part 3: HH:MM:SS
Summary: [Thai Summary 2-3 sentences]

TIMESTAMPS:
{raw_list}
"""
    print("[summarizer] Calling local model for part division & Caveman summaries...")
    try:
        content = call_local(endpoint, model, prompt, max_tokens, temperature)
        matches = re.findall(r"Part\s+(\d+)[:\s]+(\d{2}:\d{2}:\d{2}).*?Summary[:\s]+([^\n\r]+)", content, flags=re.DOTALL)
        if matches:
            border = "═" * 57
            rendered_parts = []
            for idx, (p_num, p_start, p_summary) in enumerate(matches):
                start_sec = ts_to_sec(p_start)
                next_start_sec = ts_to_sec(matches[idx+1][1]) if idx + 1 < len(matches) else 999999
                part_stamps = [s for s in all_stamps if start_sec <= ts_to_sec(s[:8]) < next_start_sec]
                if part_stamps:
                    header = f" ส่วนที่ {p_num}: {p_summary.strip()} (⏱ เริ่ม: {p_start})"
                    part_text = f"{border}\n{header}\n{border}\n" + "\n".join(part_stamps)
                    rendered_parts.append(part_text)
            if rendered_parts:
                return "\n\n".join(rendered_parts)
    except Exception as e:
        print(f"[summarizer] Warning: local summarizer call failed ({e}). Falling back to heuristic assembly.")
    return None


def generate_part_summary(stamps: List[str]) -> str:
    """Generate a 2-3 topic summary sentence from stamps in this part (heuristic fallback)."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        if desc and desc not in topics:
            topics.append(desc)

    if not topics:
        return "สรุปเนื้อหาและบรรยากาศในไลฟ์สตรีม."

    if len(topics) <= 3:
        return ". ".join(topics) + "."

    t1 = topics[0].rstrip(". ")
    t2 = topics[len(topics) // 2].rstrip(". ")
    t3 = topics[-1].rstrip(". ")
    return f"{t1}. {t2}. {t3}."


def assemble_parts(
    all_stamps: List[str],
    workspace: Path,
    block_size: int = 5400,
) -> str:
    """Heuristic fallback to group timestamps into YouTube parts with double borders."""
    if not all_stamps:
        return ""

    all_stamps = sorted(list(dict.fromkeys(all_stamps)), key=lambda l: ts_to_sec(l[:8]))

    blocks: List[List[str]] = []
    curr: List[str] = []
    block_start = ts_to_sec(all_stamps[0][:8])

    for stamp in all_stamps:
        t = ts_to_sec(stamp[:8])
        if t - block_start >= block_size and curr:
            blocks.append(curr)
            curr = [stamp]
            block_start = t
        else:
            curr.append(stamp)
    if curr:
        blocks.append(curr)

    border = "═" * 57
    parts: List[str] = []
    for i, block in enumerate(blocks, 1):
        start = block[0][:8]
        summary = generate_part_summary(block)
        header = f" ส่วนที่ {i}: {summary} (⏱ เริ่ม: {start})"
        part_text = f"{border}\n{header}\n{border}\n" + "\n".join(block)

        if len(part_text.encode("utf-8")) > 3500 and len(block) > 4:
            mid = len(block) // 2
            b1, b2 = block[:mid], block[mid:]
            s1, s2 = generate_part_summary(b1), generate_part_summary(b2)
            p1 = f"{border}\n ส่วนที่ {i}.1: {s1} (⏱ เริ่ม: {b1[0][:8]})\n{border}\n" + "\n".join(b1)
            p2 = f"{border}\n ส่วนที่ {i}.2: {s2} (⏱ เริ่ม: {b2[0][:8]})\n{border}\n" + "\n".join(b2)
            parts.append(p1)
            parts.append(p2)
        else:
            parts.append(part_text)

    return "\n\n".join(parts)

# ── Execution Engines ────────────────────────────────────────────────────────

def run_recursive_mode(
    workspace: Path,
    chunk_files: List[Path],
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    signals_map: dict,
    mappings: Optional[list],
    no_resume: bool,
    max_chunks: Optional[int],
    no_summarizer_pass: bool,
    block_size: int,
) -> None:
    """Dynamic rolling summary state-machine execution."""
    output_dir = workspace / "recursive_outputs"
    output_dir.mkdir(exist_ok=True)

    state = load_state(workspace)
    all_timestamps: List[str] = state.get("all_timestamps", []) if not no_resume else []
    current_topic_title: str = state.get("current_topic_title", "") if not no_resume else ""
    rolling_summary: str = state.get("rolling_summary", "") if not no_resume else ""

    total = len(chunk_files)
    print(f"[recursive] Starting recursive rolling topic state-machine across {total} chunks...")
    if not no_resume and all_timestamps:
        print(f"[resume] Loaded {len(all_timestamps)} timestamps from state (Ongoing Topic: '{current_topic_title}')")

    processed_count = 0
    for i, chunk_path in enumerate(chunk_files):
        chunk_idx = f"chunk_{i:02d}"
        out_path = output_dir / f"{chunk_idx}.json"

        if not no_resume and out_path.exists():
            try:
                saved_res = json.loads(out_path.read_text(encoding="utf-8"))
                current_topic_title = saved_res.get("current_topic_title", current_topic_title)
                rolling_summary = saved_res.get("rolling_summary", rolling_summary)
                saved_ts = saved_res.get("new_timestamp")
                if saved_ts and saved_ts not in all_timestamps:
                    all_timestamps.append(saved_ts)
                print(f"[skip] {chunk_idx} (already processed)")
                continue
            except Exception:
                pass

        try:
            chunk = load_chunk_file(chunk_path, mappings=mappings)
        except Exception as e:
            print(f"[warn] failed to load {chunk_path.name}: {e}", file=sys.stderr)
            continue

        chunk["_idx"] = i
        sig = signals_map.get(chunk_idx)
        lc = load_chunk_livechat(workspace, chunk_idx)
        act = load_chunk_activity(workspace, chunk_idx)
        mood = load_chunk_mood(workspace, chunk_idx)

        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic=current_topic_title,
            rolling_summary=rolling_summary,
            lang=lang,
            signal=sig,
            livechat=lc,
            activity=act,
            mood=mood,
        )
        prompt_tokens = len(prompt) // 4
        print(f"[{chunk_idx}/{total-1}] ~{prompt_tokens} tokens → calling model ...", end=" ", flush=True)

        try:
            raw = call_local(endpoint, model, prompt, max_tokens, temperature)
            text = raw
            jm = re.search(r'(\{[^{}]*"is_continuation"[^{}]*\})', text, re.DOTALL)
            if not jm:
                jm = re.search(r"(\{.*\})", text, re.DOTALL)

            if jm:
                res = json.loads(jm.group(1))
                is_cont = res.get("is_continuation", False)
                ch_sum = res.get("chunk_summary", "")
                up_sum = res.get("updated_summary", "")
                new_ts = res.get("new_timestamp")
                new_title = res.get("new_topic_title", "")

                v_ts = []
                if not is_cont:
                    # TOPIC SHIFT / FLUSH OLD
                    cleaned_ts = sanitize_timestamp_line(new_ts) if new_ts else None
                    c_start = chunk.get("start_sec", 0)
                    c_end = chunk.get("end_sec", 0)
                    if not cleaned_ts:
                        cleaned_ts = f"{_fmt_ts(c_start)} - [Talk] {new_title or ch_sum}"

                    v_ts = validate_timestamps([cleaned_ts], c_start, c_end)
                    if v_ts:
                        all_timestamps.append(v_ts[0])
                        print(f"👉 TOPIC SHIFT: {v_ts[0]} ('{new_title}')", flush=True)
                    else:
                        print(f"👉 TOPIC SHIFT (stamp out-of-range, kept topic: '{new_title}')", flush=True)

                    current_topic_title = new_title or ch_sum
                    rolling_summary = up_sum or ch_sum
                else:
                    # CONTINUATION
                    print(f"🔄 CONTINUATION (Topic: '{current_topic_title}')", flush=True)
                    rolling_summary = up_sum or ch_sum or rolling_summary

                out_path.write_text(json.dumps({
                    "chunk": chunk_idx,
                    "is_continuation": is_cont,
                    "new_timestamp": (v_ts[0] if v_ts else None) if not is_cont else None,
                    "chunk_summary": ch_sum,
                    "rolling_summary": rolling_summary,
                    "current_topic_title": current_topic_title,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                print(f"[warn] JSON parse failed, raw: {text[:100]}")

        except Exception as e:
            print(f"[error] {chunk_idx}: {e}", file=sys.stderr)

        save_state(workspace, {
            "current_chunk": i + 1,
            "total_chunks": total,
            "all_timestamps": all_timestamps,
            "current_topic_title": current_topic_title,
            "rolling_summary": rolling_summary,
            "phase": "recursive_loop",
        })

        processed_count += 1
        if max_chunks and processed_count >= max_chunks:
            print(f"[pause] Reached --max-chunks {max_chunks}.")
            break

    # Assembly
    print(f"\n[assemble] {len(all_timestamps)} total timestamps collected from topic shifts.")

    deduped = []
    seen = set()
    for s in all_timestamps:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    raw_ts = workspace / "all_timestamps.txt"
    raw_ts.write_text("\n".join(deduped), encoding="utf-8")
    print(f"[done] Raw timestamps: {raw_ts}")

    assembled = None
    if not no_summarizer_pass:
        assembled = run_local_summarizer_pass(endpoint, model, deduped, workspace, temperature)

    if not assembled:
        print("[assemble] Using heuristic double-border part assembly.")
        assembled = assemble_parts(deduped, workspace, block_size)

    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    print(f"[done] Final timestamps: {out_md}")

    is_finished = (not max_chunks or processed_count >= total)
    save_state(workspace, {
        "current_chunk": total if is_finished else (processed_count),
        "total_chunks": total,
        "all_timestamps": deduped,
        "current_topic_title": current_topic_title,
        "rolling_summary": rolling_summary,
        "phase": "complete" if is_finished else "paused",
    })
    print(f"\n✅ Recursive run complete: {out_md}")


def run_group_mode(
    workspace: Path,
    chunk_files: List[Path],
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    group_size: int,
    signals_map: dict,
    mappings: Optional[list],
    no_resume: bool,
    max_groups: Optional[int],
    no_summarizer_pass: bool,
    block_size: int,
) -> None:
    """Group-based execution across fixed windows of chunks."""
    output_dir = workspace / "group_outputs"
    output_dir.mkdir(exist_ok=True)

    state = load_state(workspace)
    all_timestamps: List[str] = state.get("all_timestamps", []) if not no_resume else []
    prev_tail: str = state.get("prev_tail", "") if not no_resume else ""

    total_chunks = len(chunk_files)
    num_groups = (total_chunks + group_size - 1) // group_size

    if not no_resume and all_timestamps:
        print(f"[resume] {len(all_timestamps)} timestamps already recorded")

    groups_processed = 0
    for g in range(num_groups):
        group_idx = f"group_{g:02d}"
        out_path = output_dir / f"{group_idx}_output.md"

        if not no_resume and out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            for line in reversed(existing.splitlines()):
                line = line.strip()
                if re.match(r"\d{2}:\d{2}:\d{2}\s*-\s*\[", line):
                    prev_tail = line
                    break
            print(f"[skip] {group_idx} (output exists)")
            continue

        g_files = chunk_files[g * group_size : (g + 1) * group_size]
        g_chunks = []
        for cf in g_files:
            try:
                ch = load_chunk_file(cf, mappings=mappings)
                m = re.search(r"chunk_(\d+)", cf.stem)
                ch["_idx"] = int(m.group(1)) if m else 0
                g_chunks.append(ch)
            except Exception as e:
                print(f"[warn] failed to load {cf.name}: {e}", file=sys.stderr)

        if not g_chunks:
            continue

        g_start_sec = g_chunks[0].get("start_sec", 0)
        g_end_sec = g_chunks[-1].get("end_sec", 0)

        prompt = build_group_prompt(g_chunks, g, prev_tail, lang, signals_map, workspace)
        prompt_tokens = len(prompt) // 4
        print(f"[{group_idx}/{num_groups-1}] chunks {g_chunks[0]['_idx']:02d}..{g_chunks[-1]['_idx']:02d} ~{prompt_tokens} tokens → calling model ...", end=" ", flush=True)

        try:
            raw = call_local(endpoint, model, prompt, max_tokens, temperature)
        except urllib.error.URLError as e:
            print(f"\n[error] endpoint unreachable: {e}", file=sys.stderr)
            save_state(workspace, {
                "current_group": g,
                "all_timestamps": all_timestamps,
                "prev_tail": prev_tail,
                "phase": "group_loop",
            })
            sys.exit(1)
        except Exception as e:
            print(f"\n[error] {group_idx}: {e}", file=sys.stderr)
            continue

        if is_continuation(raw):
            stamps = []
            result_label = "CONTINUATION"
        else:
            stamps = parse_timestamps(raw, max_stamps=4)
            stamps = validate_timestamps(stamps, g_start_sec, g_end_sec)
            result_label = f"{len(stamps)} stamp(s)" if stamps else "0 stamps (continuity)"

        print(result_label)

        if stamps:
            md_lines = [f"<!-- {group_idx} | {_fmt_ts(g_start_sec)} – {_fmt_ts(g_end_sec)} -->", ""]
            md_lines.extend(stamps)
            md_content = "\n".join(md_lines)
            prev_tail = stamps[-1]
            all_timestamps.extend(stamps)
        else:
            md_content = f"<!-- {group_idx} | {_fmt_ts(g_start_sec)} – {_fmt_ts(g_end_sec)} | CONTINUATION -->"

        out_path.write_text(md_content + "\n", encoding="utf-8")

        save_state(workspace, {
            "current_group": g + 1,
            "total_groups": num_groups,
            "all_timestamps": all_timestamps,
            "prev_tail": prev_tail,
            "phase": "group_loop",
        })

        groups_processed += 1
        if max_groups and groups_processed >= max_groups:
            print(f"[pause] Reached --max-groups {max_groups}.")
            break

    # Assembly
    print(f"\n[assemble] {len(all_timestamps)} total timestamps collected.")

    deduped = []
    seen = set()
    for s in all_timestamps:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    raw_ts = workspace / "all_timestamps.txt"
    raw_ts.write_text("\n".join(deduped), encoding="utf-8")
    print(f"[done] Raw timestamps: {raw_ts}")

    assembled = None
    if not no_summarizer_pass:
        assembled = run_local_summarizer_pass(endpoint, model, deduped, workspace, temperature)

    if not assembled:
        print("[assemble] Using heuristic double-border part assembly.")
        assembled = assemble_parts(deduped, workspace, block_size)

    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    print(f"[done] Final timestamps: {out_md}")

    save_state(workspace, {
        "current_group": num_groups,
        "total_groups": num_groups,
        "all_timestamps": deduped,
        "prev_tail": prev_tail,
        "phase": "complete",
    })
    print(f"\n✅ Group run complete: {out_md}")

# ── Main Controller ──────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="P100 Single-GPU Timestamper (Recursive & Group Modes).")
    ap.add_argument("workspace", help="Path to youtube_VIDEOID_workspace directory")
    ap.add_argument("--mode", default="recursive", choices=["recursive", "group"],
                    help="Execution mode: recursive (dynamic topic state-machine) or group (fixed 4-chunk groups)")
    ap.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--force-model", action="store_true")
    ap.add_argument("--lang", default="th", choices=["th", "en"])
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--group-size", type=int, default=4,
                    help="Chunks per group in --mode group (default 4 = ~16-20 min)")
    ap.add_argument("--no-summarizer-pass", action="store_true",
                    help="Disable LLM summarizer pass; use heuristic assembly")
    ap.add_argument("--summarize-only", action="store_true",
                    help="Skip chunk loop and run summarizer pass on all_timestamps.txt")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chunks", type=int, default=None,
                    help="Max chunks to process in recursive mode")
    ap.add_argument("--max-groups", type=int, default=None,
                    help="Max groups to process in group mode")
    ap.add_argument("--block-size", type=int, default=5400)
    args = ap.parse_args()

    workspace = Path(args.workspace)
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)

    model = resolve_model(args.model, args.endpoint, force=args.force_model)

    # ── Summarize-only Shortcut ──────────────────────────────────────────────
    if args.summarize_only:
        raw_ts = workspace / "all_timestamps.txt"
        if not raw_ts.exists():
            print(f"ERROR: {raw_ts} not found for --summarize-only", file=sys.stderr)
            sys.exit(1)
        stamps = [l.strip() for l in raw_ts.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"[summarize-only] Loaded {len(stamps)} timestamps. Running assembly...")
        assembled = None
        if not args.no_summarizer_pass:
            assembled = run_local_summarizer_pass(args.endpoint, model, stamps, workspace, args.temperature)
        if not assembled:
            assembled = assemble_parts(stamps, workspace, args.block_size)
        out_md = workspace / "anibon_timestamps.md"
        out_md.write_text(assembled, encoding="utf-8")
        print(f"✅ Assembly complete: {out_md}")
        return

    try:
        chunk_files = discover_chunks(workspace)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    total_chunks = len(chunk_files)
    print(f"[init] workspace   : {workspace}")
    print(f"[init] model       : {model}")
    print(f"[init] endpoint    : {args.endpoint}")
    print(f"[init] mode        : {args.mode}")
    print(f"[init] total chunks: {total_chunks}")
    print(f"[init] lang        : {args.lang}")

    if args.dry_run:
        print(f"[dry-run] Discovered {total_chunks} chunks.")
        return

    # ── Signal & Knowledge Detection ─────────────────────────────────────────
    signals_file = workspace / "signals.json"
    if not signals_file.exists():
        print("[signals] Detecting domain signals...")
        signals_map = detect_signals_for_chunks(workspace)
    else:
        try:
            with open(signals_file, encoding="utf-8") as f:
                signals_map = json.load(f)
        except Exception:
            signals_map = detect_signals_for_chunks(workspace)

    mappings = load_mappings()
    if mappings:
        print(f"[knowledge] Loaded {len(mappings)} phonetic entity mappings")

    # ── Execution Branching ──────────────────────────────────────────────────
    if args.mode == "recursive":
        run_recursive_mode(
            workspace=workspace,
            chunk_files=chunk_files,
            endpoint=args.endpoint,
            model=model,
            lang=args.lang,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            signals_map=signals_map,
            mappings=mappings,
            no_resume=args.no_resume,
            max_chunks=args.max_chunks,
            no_summarizer_pass=args.no_summarizer_pass,
            block_size=args.block_size,
        )
    else:
        run_group_mode(
            workspace=workspace,
            chunk_files=chunk_files,
            endpoint=args.endpoint,
            model=model,
            lang=args.lang,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            group_size=args.group_size,
            signals_map=signals_map,
            mappings=mappings,
            no_resume=args.no_resume,
            max_groups=args.max_groups,
            no_summarizer_pass=args.no_summarizer_pass,
            block_size=args.block_size,
        )


if __name__ == "__main__":
    main()
