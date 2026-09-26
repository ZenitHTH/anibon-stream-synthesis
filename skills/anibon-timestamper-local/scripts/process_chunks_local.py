"""
process_chunks_local.py — Local LLM chunk runner for Anibon timestamping.

Two modes:

1. --full-context (RECOMMENDED for gemma-4-12b-qat with Q4.0 KV cache)
   Sends entire transcript in ONE call. No CONTINUATION issues, no prev_tail
   hallucination. Requires ~51k input tokens for a 2hr stream.
   With Q4.0 KV cache on P100 (16GB), context fits up to 200k tokens.

   python -X utf8 process_chunks_local.py [WORKSPACE] --full-context --max-tokens 4000

2. Sequential (fallback for small-context models, <8k ctx)
   Processes chunks one-by-one. Use when model context < 32k tokens.

   python -X utf8 process_chunks_local.py [WORKSPACE] --max-tokens 1200

Flags:
    --endpoint      LM Studio API base  (default: http://127.0.0.1:1234/v1/chat/completions)
    --model         Model identifier    (default: auto; picks loaded model, Gemma -> Qwen)
    --force-model   Force requested model even if not currently loaded in LM Studio
    --lang          Output language     th|en (default: th)
    --max-tokens    max_tokens per call (default: 4000 full-ctx, 1200 sequential)
    --temperature   sampling temp       (default: 0.1)
    --full-context  Send entire transcript in one call (needs 32k+ ctx)
    --no-resume     Ignore existing chunk_outputs, reprocess all chunks
    --dry-run       Print discovered chunks without calling model
    --block-size    Seconds per YouTube part block for assembly (default: 5400)
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

# ── Constants ────────────────────────────────────────────────────────────────

TAGS = (
    "[Greeting]", "[Talk]", "[News]", "[Chat]", "[Donation]",
    "[Gameplay]", "[Gacha]", "[Boss]", "[Death]", "[Victory]",
    "[WatchParty]", "[Reaction]",
)

SYSTEM_PROMPT = """\
You are a timestamper for Thai livestream VODs by Pu Boat (Anibon Official).
CRITICAL INSTRUCTION: Keep your internal thinking under 2 sentences. \
Do NOT list items or transcribe text in your thinking. \
Proceed immediately to outputting the final decision."""

# ── Prompt building ───────────────────────────────────────────────────────────


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _chunk_range(items: list) -> tuple[str, str]:
    if not items:
        return "00:00:00", "00:00:00"
    start = items[0].get("start", 0)
    last = items[-1]
    end = last.get("start", 0) + last.get("duration", 5)
    return _fmt_ts(start), _fmt_ts(end)


def build_prompt(chunk: dict, prev_tail: str, lang: str) -> str:
    """Build front-tier quality prompt for a single chunk."""
    items = chunk.get("items", [])
    start_ts, end_ts = _chunk_range(items)

    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"

    # Format transcript lines
    lines = []
    for it in items:
        ts = it.get("timestamp", _fmt_ts(it.get("start", 0)))
        text = it.get("text", "").strip()
        if text:
            lines.append(f"({ts}) {text}")
    transcript_block = "\n".join(lines) if lines else "(no transcript data)"

    # Mask timestamp from prev_tail — show only tag+description, NOT the time.
    # Prevents model from echoing prev_tail's timestamp into the current chunk.
    if prev_tail:
        masked = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*", "", prev_tail).strip()
        prev_section = f"Previous chunk topic (context only — do NOT use this timestamp):\n[context] {masked}\n"
    else:
        prev_section = "(First chunk — no previous context.)\n"

    tags_list = "  ".join(TAGS)

    prompt = f"""\
You are timestamping chunk {chunk.get('_idx', '??')} of a Thai livestream VOD by Pu Boat (Anibon Official).
Chunk time range: {start_ts} - {end_ts}

{prev_section}
## YOUR TASK

Read the transcript. Output ONE timestamp line for the most notable moment or topic in this chunk.

Format: HH:MM:SS - [Tag] Description

Rules:
- HH:MM:SS MUST be a timestamp that literally appears in the transcript ({start_ts} - {end_ts}).
- Description in {lang_note}. Max 12 words. One phrase. Active voice.
- Tags: {tags_list}
- FIRST-VERB GUIDANCE (Reflect Pu Boat's vibe and emotion):
  * Funny / Meme / Roast: แซว, ฮาลั่น!, เม้าท์มอย, ขำก๊าก, ขยี้, ปั่น, ล้อ
  * Rant / Drama / Politics: ชำแหละ, จวกยับ, สับเละ, บ่นอุบ, โวยวาย, สาวไส้
  * News / Serious Talk: วิเคราะห์, เจาะลึก, กางตัวเลข, เตือน, ชี้จุดสังเกต
  * Shock / Hype: อึ้ง!, เหวอ, ช็อกตาค้าง, โคตรเดือด, ตะโกนลั่น
  * Do NOT use flat verbs like "พูดถึง..." or "พูดคุยเรื่อง..." if there is a specific action or emotion.
- STRICT CLEANLINESS:
  * Output ONLY in Thai (or specified language).
  * NEVER append English translations, meta-notes, or self-corrections in parentheses (e.g. NO '(Too long?)', NO '(Criticizing...)').
  * Output ONLY the single timestamp line. No preamble, no explanation, no markdown backticks.

Output SKIP (and nothing else) ONLY when:
- Transcript is empty or silent gap
- Chunk is a mid-sentence continuation of the exact same talking point with zero new development

When NOT to output SKIP (stamp these):
- New sub-topic in same conversation → stamp it
- Donation read, news mention, reaction → stamp it
- Same game but activity changed (gacha, boss, talk) → stamp it
- Any notable viewer interaction → stamp it

## TRANSCRIPT ({start_ts} - {end_ts})
{transcript_block}
"""
    return prompt.strip()


def build_full_context_prompt(chunk_files: list, lang: str) -> str:
    """Build single prompt containing the ENTIRE transcript for one-shot timestamping.

    Used when model has large context (32k+). Eliminates prev_tail hallucination
    and CONTINUATION over-merging by giving the model full stream visibility.
    """
    lang_note = "Thai (ภาษาไทย)" if lang == "th" else "English"
    tags_list = "  ".join(TAGS)

    # Build full transcript: one block per chunk with clear time headers
    transcript_parts = []
    total_duration_min = 0
    for chunk_path in chunk_files:
        try:
            chunk = load_chunk_file(chunk_path)
        except Exception:
            continue
        items = chunk.get("items", [])
        if not items:
            continue
        start_ts, end_ts = _chunk_range(items)
        lines = []
        for it in items:
            ts = it.get("timestamp", _fmt_ts(it.get("start", 0)))
            text = it.get("text", "").strip()
            if text:
                lines.append(f"({ts}) {text}")
        if lines:
            transcript_parts.append(f"=== {start_ts} - {end_ts} ===\n" + "\n".join(lines))
        end_sec = chunk.get("end_sec", 0)
        total_duration_min = max(total_duration_min, end_sec // 60)

    full_transcript = "\n\n".join(transcript_parts)
    expected_stamps = max(5, total_duration_min // 5)  # ~1 per 5 min

    prompt = f"""\
You are generating YouTube timestamps for a Thai livestream VOD by Pu Boat (Anibon Official).
Stream duration: ~{total_duration_min} minutes.

## YOUR TASK

Read the full transcript below. Output timestamps for every notable topic, activity change, or moment.
Target: approximately {expected_stamps} timestamps (1 per 5 minutes). More is fine if topics change frequently.

Output format — one line per timestamp:
HH:MM:SS - [Tag] Description

Rules:
- HH:MM:SS MUST be a timestamp that literally appears in the transcript.
- Description in {lang_note}. Max 12 words. Active voice. No quotes.
- Tags: {tags_list}
- List timestamps in chronological order.
- Output ONLY timestamp lines. No headers, no explanation, no extra text.

Stamp when:
- Stream starts / greeting
- New topic of conversation begins
- Game or activity changes
- Donation is read
- Notable news or reaction
- Gameplay section starts/changes (new boss, gacha pull, etc.)

## FULL TRANSCRIPT
{full_transcript}
"""
    return prompt.strip()


def run_full_context(
    workspace: Path,
    chunk_files: list,
    endpoint: str,
    model: str,
    lang: str,
    max_tokens: int,
    temperature: float,
    block_size: int,
) -> None:
    """One-shot full-context timestamping: entire transcript → single API call."""
    print(f"[full-ctx] building prompt from {len(chunk_files)} chunks ...")
    prompt = build_full_context_prompt(chunk_files, lang)
    tokens_estimate = len(prompt) // 4
    print(f"[full-ctx] prompt ~{tokens_estimate:,} tokens → calling model ...")

    try:
        raw = call_local(endpoint, model, prompt, max_tokens, temperature)
    except urllib.error.URLError as e:
        print(f"[error] endpoint unreachable: {e}", file=sys.stderr)
        print("[error] Is LM Studio running?", file=sys.stderr)
        sys.exit(1)

    stamps = parse_timestamps(raw)
    print(f"[full-ctx] got {len(stamps)} timestamps from model")

    if not stamps:
        print("[warn] No timestamps extracted. Raw output:", file=sys.stderr)
        print(raw[:500], file=sys.stderr)
        sys.exit(1)

    # Write raw output
    raw_out = workspace / "all_timestamps.txt"
    raw_out.write_text("\n".join(stamps), encoding="utf-8")
    print(f"[done] {raw_out}")

    # Assemble into parts
    assembled = assemble_parts(stamps, workspace, block_size)
    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    print(f"[done] {out_md}")
    print(f"\n✅ Complete. {len(stamps)} timestamps (full-context mode).")
    print(f"   Output: {out_md}")


# ── LM Studio model detection & resolution ───────────────────────────────────


def get_loaded_models() -> list[str]:
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
    """Resolve which model to use, preventing eviction of active models.

    On a 16GB Tesla P100 GPU, both google/gemma-4-12b-qat (7.15 GB) and
    qwen/qwen3.5-9b (6.55 GB) fit simultaneously in VRAM (13.7 GB total).
    If a model is requested that isn't loaded, falling back to what's loaded
    prevents LM Studio from JIT-evicting the user's active Cline chat session.
    """
    loaded = get_loaded_models()
    if loaded:
        print(f"[init] LM Studio loaded model(s): {', '.join(loaded)}")

        # Auto selection or no model specified
        if not requested_model or requested_model.lower() == "auto":
            # Priority 1: google/gemma-4-12b-qat, Priority 2: qwen/qwen3.5-9b
            for preferred in ("google/gemma-4-12b-qat", "qwen/qwen3.5-9b"):
                if preferred in loaded:
                    print(f"[init] Auto-selected loaded model: {preferred}")
                    return preferred
            selected = loaded[0]
            print(f"[init] Auto-selected loaded model: {selected}")
            return selected

        # User gave explicit model name
        if requested_model in loaded:
            print(f"[init] Using requested loaded model: {requested_model}")
            return requested_model

        if force:
            print(f"[warn] Model '{requested_model}' not in LM Studio loaded list, but --force-model was set.", file=sys.stderr)
            return requested_model

        # Requested model is NOT loaded, but other models are loaded
        fallback = None
        for preferred in ("google/gemma-4-12b-qat", "qwen/qwen3.5-9b"):
            if preferred in loaded:
                fallback = preferred
                break
        if not fallback:
            fallback = loaded[0]

        print(f"[warn] Requested model '{requested_model}' is not currently loaded in LM Studio!", file=sys.stderr)
        print(f"[warn] Falling back to already-loaded '{fallback}' to prevent LM Studio model conflict/eviction.", file=sys.stderr)
        return fallback

    # Fallback if lms ps is unavailable
    if not requested_model or requested_model.lower() == "auto":
        return "google/gemma-4-12b-qat"
    return requested_model


# ── API call ─────────────────────────────────────────────────────────────────


def call_local(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call local OpenAI-compatible API. Returns extracted content string."""
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    msg = data["choices"][0]["message"]
    content = msg.get("content", "").strip()

    # Fallback: reasoning model burned budget into reasoning_content
    if not content and msg.get("reasoning_content"):
        rc = msg["reasoning_content"]
        # Try to extract any timestamp line from reasoning
        m = re.search(r"(\d{2}:\d{2}:\d{2}\s*-\s*\[[\w]+\]\s*[^\n]+)", rc)
        if m:
            content = m.group(1).strip()
        elif "CONTINUATION" in rc.upper():
            content = "CONTINUATION"
        else:
            content = "CONTINUATION"  # safe fallback

    return content


# ── Chunk discovery ───────────────────────────────────────────────────────────


def discover_chunks(workspace: Path) -> list[Path]:
    """Return sorted chunk .txt or .json files from workspace/chunks/."""
    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        raise FileNotFoundError(f"No chunks dir: {chunks_dir}")

    files = sorted(
        list(chunks_dir.glob("chunk_*.txt")) +
        list(chunks_dir.glob("chunk_*.json")),
        key=lambda f: int(re.search(r"chunk_(\d+)", f.stem).group(1)),
    )
    if not files:
        raise FileNotFoundError(f"No chunk files in: {chunks_dir}")
    return files


def load_chunk_file(path: Path) -> dict:
    """Load chunk file; returns unified dict with 'items', 'start_sec', 'end_sec'."""
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data

    # .txt format: parse header + lines
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    items = []
    start_sec = 0
    end_sec = 0
    cutoff = 0

    if lines:
        # Header: "CHUNK 00 | 00:00:00–00:05:00 | cutoff=00:04:30"
        header = lines[0]
        m = re.search(r"(\d{2}:\d{2}:\d{2})[–-](\d{2}:\d{2}:\d{2})", header)
        if m:
            def ts2s(t: str) -> int:
                h, mi, s = t.split(":")
                return int(h) * 3600 + int(mi) * 60 + int(s)
            start_sec = ts2s(m.group(1))
            end_sec = ts2s(m.group(2))
        mc = re.search(r"cutoff=(\d{2}:\d{2}:\d{2})", header)
        if mc:
            cutoff = ts2s(mc.group(1)) if mc else end_sec

        for line in lines[1:]:
            # "(HH:MM:SS) text"
            lm = re.match(r"\((\d{2}:\d{2}:\d{2})\)\s+(.*)", line)
            if lm:
                ts = lm.group(1)
                h, mi, s = ts.split(":")
                sec = int(h) * 3600 + int(mi) * 60 + int(s)
                # Skip lines past cutoff
                if cutoff and sec > cutoff:
                    continue
                items.append({"start": float(sec), "timestamp": ts, "text": lm.group(2)})

    return {"start_sec": start_sec, "end_sec": end_sec, "items": items}


# ── Output parsing ────────────────────────────────────────────────────────────


def sanitize_timestamp_line(line: str) -> str:
    """Strip English reasoning, self-correction comments, word counts, and prompt leaks from timestamp line."""
    # Strip meta comments like " - 9 words. Good.", ". Wait, description...", " (Wait, ...)"
    line = re.sub(r"\s*-\s*\d+\s*words.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\.?\s*Wait,\s*.*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*(?:Or just describe|Note:|Remark:).*$", "", line, flags=re.IGNORECASE)
    # Strip parenthetical English translations/explanations: (Analyze ...) or (Requesting ...) or (Too long? ...)
    line = re.sub(r"\s*\([A-Za-z\s\?\,\.\-\:\'\"]{8,}\).*$", "", line)
    # Strip trailing English thoughts in parentheses
    line = re.sub(r"\s*\([A-Za-z0-9\s\?\,\.\-\:\'\"]+\)\.?$", "", line)
    # Strip surrounding quotes, backticks, stray markdown
    line = re.sub(r"^[`'\"]+|[`'\"\\.]+$", "", line.strip())
    return line.strip()


def parse_timestamps(raw: str) -> list[str]:
    """Extract and sanitize valid HH:MM:SS - [Tag] ... lines from model output."""
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if re.match(r"\d{2}:\d{2}:\d{2}\s*-\s*\[", line):
            cleaned = sanitize_timestamp_line(line)
            if cleaned:
                lines.append(cleaned)
    return lines


def validate_timestamps(stamps: list[str], start_sec: int, end_sec: int) -> list[str]:
    """Discard stamps whose time falls outside [start_sec-60, end_sec+60].

    Guards against model hallucinating timestamps from prev_tail context.
    """
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
            print(f"  [drop] out-of-range stamp {stamp[:8]} (chunk {_fmt_ts(start_sec)}-{_fmt_ts(end_sec)})")
    return valid


def is_continuation(raw: str) -> bool:
    upper = raw.upper().strip()
    return (upper == "SKIP" or upper == "CONTINUATION") and not re.search(r"\d{2}:\d{2}:\d{2}", raw)


# ── State management ──────────────────────────────────────────────────────────


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


# ── Assembly ──────────────────────────────────────────────────────────────────


def ts_to_sec(ts: str) -> int:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def generate_part_summary(stamps: list[str]) -> str:
    """Generate a punchy 2-3 topic summary sentence from stamps in this part."""
    topics = []
    for s in stamps:
        desc = re.sub(r"^\d{2}:\d{2}:\d{2}\s*-\s*\[\w+\]\s*", "", s).strip()
        if desc and desc not in topics:
            topics.append(desc)

    if not topics:
        return "สรุปเนื้อหาและบรรยากาศในไลฟ์สตรีม."

    if len(topics) <= 3:
        chosen = topics
    else:
        mid_idx = len(topics) // 2
        chosen = [topics[0], topics[mid_idx], topics[-1]]

    summary = ". ".join(chosen)
    if not summary.endswith("."):
        summary += "."
    return summary


def assemble_parts(
    all_stamps: list[str],
    workspace: Path,
    block_size: int = 5400,
) -> str:
    """Group timestamps into YouTube-comment-sized parts with front-tier headers."""
    if not all_stamps:
        return ""

    # Sort by time
    all_stamps = sorted(all_stamps, key=lambda l: ts_to_sec(l[:8]))

    # Group into blocks by block_size seconds
    blocks: list[list[str]] = []
    curr: list[str] = []
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

    # Extract Video ID from workspace name
    m = re.search(r"youtube_([a-zA-Z0-9_-]+)_workspace", workspace.name)
    video_id = m.group(1) if m else workspace.name

    divider = "═" * 57

    # Render parts
    parts: list[str] = []
    for i, block in enumerate(blocks, 1):
        start = block[0][:8]
        summary = generate_part_summary(block)
        header = f"{divider}\n ส่วนที่ {i}: {summary} (⏱ เริ่ม: {start})\n{divider}"
        parts.append(f"{header}\n" + "\n".join(block))

    # Check byte budget (YouTube comment ≤4500 bytes per part)
    final_parts: list[str] = []
    for part in parts:
        if len(part.encode("utf-8")) > 4500:
            lines = part.splitlines()
            mid = len(lines) // 2
            final_parts.append("\n".join(lines[:mid]))
            final_parts.append("\n".join(lines[mid:]))
        else:
            final_parts.append(part)

    # Document Header matching front-tier benchmarks
    doc_header = f"""# ไทม์สแตมป์ไลฟ์สตรีม | ANIBON

- **YouTube Video ID**: [{video_id}](https://www.youtube.com/watch?v={video_id})
- **Workspace Directory**: `{workspace.name}`
- **Total Timestamps**: {len(all_stamps)}

---
"""
    return doc_header + "\n" + "\n\n".join(final_parts) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description="Local LLM timestamper (full-context or sequential).")
    ap.add_argument("workspace", help="Path to youtube_VIDEOID_workspace directory")
    ap.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    ap.add_argument("--model", default="auto",
                    help="Model identifier or 'auto' to use loaded model (default: auto)")
    ap.add_argument("--force-model", action="store_true",
                    help="Force using requested model even if not loaded in LM Studio")
    ap.add_argument("--lang", default="th", choices=["th", "en"])
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="Max tokens per call (default: 4000 full-ctx, 1200 sequential)")
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--full-context", action="store_true",
                    help="Send entire transcript in one call (recommended for 32k+ context models)")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chunks", type=int, default=None,
                    help="Max new chunks to process in this run (e.g. 1 for quick step)")
    ap.add_argument("--block-size", type=int, default=5400, help="Seconds per YouTube part block")
    args = ap.parse_args()

    # Default max-tokens depends on mode
    if args.max_tokens is None:
        args.max_tokens = 4000 if args.full_context else 1200

    workspace = Path(args.workspace)
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)

    model = resolve_model(args.model, args.endpoint, force=args.force_model)

    output_dir = workspace / "chunk_outputs"
    output_dir.mkdir(exist_ok=True)

    try:
        chunk_files = discover_chunks(workspace)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    total = len(chunk_files)
    mode = "full-context" if args.full_context else "sequential"
    print(f"[init] workspace : {workspace}")
    print(f"[init] model     : {model}")
    print(f"[init] endpoint  : {args.endpoint}")
    print(f"[init] chunks    : {total}")
    print(f"[init] lang      : {args.lang}")
    print(f"[init] mode      : {mode}")
    print(f"[init] max-tokens: {args.max_tokens}")

    if args.dry_run:
        for i, f in enumerate(chunk_files):
            print(f"  chunk_{i:02d}: {f.name}")
        print("[dry-run] done")
        return

    # ── Full-context mode: one call for entire transcript ─────────────────────
    if args.full_context:
        run_full_context(
            workspace=workspace,
            chunk_files=chunk_files,
            endpoint=args.endpoint,
            model=model,
            lang=args.lang,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            block_size=args.block_size,
        )
        return

    state = load_state(workspace)
    all_timestamps: list[str] = state.get("all_timestamps", [])
    prev_tail: str = state.get("prev_tail", "")

    if not args.no_resume and all_timestamps:
        print(f"[resume] {len(all_timestamps)} timestamps already in state")

    processed_count = 0
    for i, chunk_path in enumerate(chunk_files):
        chunk_idx = f"chunk_{i:02d}"
        out_path = output_dir / f"{chunk_idx}_output.md"

        # Resume: skip already-done chunks.
        # Trust state's all_timestamps — do NOT re-scan output files (causes duplicates).
        if not args.no_resume and out_path.exists():
            # Only update prev_tail from the file (last stamp line), don't re-add to list.
            existing = out_path.read_text(encoding="utf-8")
            for line in reversed(existing.splitlines()):
                line = line.strip()
                if re.match(r"\d{2}:\d{2}:\d{2}\s*-\s*\[", line):
                    prev_tail = line
                    break
            print(f"[skip] {chunk_idx} (output exists)")
            continue

        # Load chunk
        try:
            chunk = load_chunk_file(chunk_path)
        except Exception as e:
            print(f"[warn] failed to load {chunk_path.name}: {e}", file=sys.stderr)
            continue

        chunk["_idx"] = i

        # Build prompt
        prompt = build_prompt(chunk, prev_tail, args.lang)
        prompt_tokens = len(prompt) // 4
        print(f"[chunk {i:02d}/{total-1}] ~{prompt_tokens} tokens → calling model ...", end=" ", flush=True)

        # Call model
        try:
            raw = call_local(args.endpoint, model, prompt, args.max_tokens, args.temperature)
        except urllib.error.URLError as e:
            print(f"\n[error] endpoint unreachable: {e}", file=sys.stderr)
            print("[error] Is LM Studio running? Start it and retry.", file=sys.stderr)
            save_state(workspace, {
                "current_chunk": i,
                "all_timestamps": all_timestamps,
                "prev_tail": prev_tail,
                "phase": "chunk_loop",
            })
            sys.exit(1)
        except Exception as e:
            print(f"\n[error] {chunk_idx}: {e}", file=sys.stderr)
            continue

        # Parse
        if is_continuation(raw):
            stamps = []
            result_label = "CONTINUATION"
        else:
            stamps = parse_timestamps(raw)
            # Validate: drop stamps outside this chunk's time window (hallucination guard)
            stamps = validate_timestamps(stamps, chunk.get("start_sec", 0), chunk.get("end_sec", 0))
            if not stamps:
                result_label = "CONTINUATION (all stamps out-of-range, dropped)"
            else:
                result_label = f"{len(stamps)} stamp(s)"

        print(result_label)

        # Build output markdown
        if stamps:
            items = chunk.get("items", [])
            start_ts, end_ts = _chunk_range(items)
            md_lines = [f"<!-- {chunk_idx} | {start_ts} – {end_ts} -->", ""]
            md_lines.extend(stamps)
            md_content = "\n".join(md_lines)
            prev_tail = stamps[-1]
            all_timestamps.extend(stamps)
        else:
            items = chunk.get("items", [])
            start_ts, end_ts = _chunk_range(items)
            md_content = f"<!-- {chunk_idx} | {start_ts} – {end_ts} | CONTINUATION -->"

        out_path.write_text(md_content + "\n", encoding="utf-8")

        # Update state after EVERY chunk
        save_state(workspace, {
            "current_chunk": i + 1,
            "total_chunks": total,
            "all_timestamps": all_timestamps,
            "prev_tail": prev_tail,
            "phase": "chunk_loop",
        })

        processed_count += 1
        if args.max_chunks and processed_count >= args.max_chunks:
            print(f"\n[pause] Processed {processed_count} chunk(s) (reached --max-chunks {args.max_chunks}).")
            if i + 1 < total:
                print(f"[pause] {total - (i + 1)} chunks remaining. Re-run or use launch_local.ps1 to finish.")
            break

    # ── Assembly ──────────────────────────────────────────────────────────────
    print(f"\n[assemble] {len(all_timestamps)} total timestamps → building parts ...")

    assembled = assemble_parts(all_timestamps, workspace, args.block_size)

    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    print(f"[done] {out_md}")

    # Raw flat list
    raw_ts = workspace / "all_timestamps.txt"
    raw_ts.write_text("\n".join(all_timestamps), encoding="utf-8")
    print(f"[done] {raw_ts}")

    save_state(workspace, {
        "current_chunk": total,
        "total_chunks": total,
        "all_timestamps": all_timestamps,
        "prev_tail": prev_tail,
        "phase": "complete",
    })

    print(f"\n✅ Complete. {len(all_timestamps)} stamps across {total} chunks.")
    print(f"   Output: {out_md}")


if __name__ == "__main__":
    main()
