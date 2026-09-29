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
import io
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

# Enforce UTF-8 encoding on standard streams to prevent Thai character truncation/corruption
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

try:
    from signal_detector import (
        load_mappings,
        load_garbled_replacements,
        clean_transcript_noise,
        normalize_transcript,
        detect_signals_for_chunks,
        get_domain_guidance,
    )
except ImportError:
    from scripts.signal_detector import (
        load_mappings,
        load_garbled_replacements,
        clean_transcript_noise,
        normalize_transcript,
        detect_signals_for_chunks,
        get_domain_guidance,
    )

# ── Constants ────────────────────────────────────────────────────────────────

# Auto-discover anibon-world-identity references directory.
_SCRIPT_DIR = Path(__file__).resolve().parent
_WI_CANDIDATES = [
    _SCRIPT_DIR.parent.parent / "anibon-world-identity" / "references",
    _SCRIPT_DIR.parent.parent.parent / "anibon-world-identity" / "references",
]
WORLD_IDENTITY_DIR: Optional[Path] = next((p for p in _WI_CANDIDATES if p.is_dir()), None)

from anibon.timestamps import (
    TAGS,
    TAG_REMAP,
    normalize_tag,
    sanitize_timestamp_line,
    parse_timestamps,
    validate_timestamps,
    is_continuation,
)

from anibon.lmstudio import (
    SYSTEM_PROMPT,
    get_loaded_models,
    resolve_model,
    call_local,
    call_vision,
)

from anibon.prompts import (
    WORLD_IDENTITY_DIR,
    load_world_identity_context,
    build_recursive_prompt,
    build_group_prompt,
)

from anibon.summarizer import (
    generate_part_summary,
    run_local_summarizer_pass,
    assemble_parts,
)


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

from anibon.state import (
    load_state,
    save_state,
    load_chunk_livechat,
    load_chunk_activity,
    load_chunk_mood,
    discover_chunks,
    load_chunk_file,
)

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
    world_identity_dir: Optional[Path] = None,
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
                saved_ts = saved_res.get("timestamp") or saved_res.get("new_timestamp")
                if saved_ts and saved_ts not in all_timestamps:
                    all_timestamps.append(saved_ts)
                print(f"[skip] {chunk_idx} (already processed)", flush=True)
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
        wi_ref = load_world_identity_context(sig, world_identity_dir)

        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic=current_topic_title,
            rolling_summary=rolling_summary,
            lang=lang,
            signal=sig,
            livechat=lc,
            activity=act,
            mood=mood,
            world_identity_ref=wi_ref,
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
                raw_ts = res.get("timestamps") or res.get("timestamp") or res.get("new_timestamp")
                new_title = res.get("new_topic_title", "")

                candidate_stamps: List[str] = []
                if isinstance(raw_ts, list):
                    for st in raw_ts:
                        if st and isinstance(st, str):
                            san = sanitize_timestamp_line(st)
                            if san:
                                candidate_stamps.append(san)
                elif isinstance(raw_ts, str) and raw_ts.strip():
                    san = sanitize_timestamp_line(raw_ts)
                    if san:
                        candidate_stamps.append(san)

                c_start = chunk.get("start_sec", 0)
                c_end = chunk.get("end_sec", 0)
                v_ts = validate_timestamps(candidate_stamps, c_start, c_end)

                # Deduplicate and sort chronologically within chunk
                def _sec(s: str) -> int:
                    m = re.match(r"(\d{2}):(\d{2}):(\d{2})", s)
                    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else 0

                v_ts_sorted: List[str] = []
                prev_s = -1
                for s in sorted(v_ts, key=_sec):
                    sec_val = _sec(s)
                    if prev_s == -1 or (sec_val - prev_s) >= 45:
                        v_ts_sorted.append(s)
                        prev_s = sec_val

                if not is_cont:
                    # MAJOR TOPIC SHIFT / FLUSH OLD
                    if not v_ts_sorted:
                        fallback_ts = f"{_fmt_ts(c_start)} - [Talk] {new_title or ch_sum}"
                        v_ts_sorted = validate_timestamps([fallback_ts], c_start, c_end)

                    for stamp in v_ts_sorted:
                        all_timestamps.append(stamp)
                        print(f"👉 MAJOR SHIFT: {stamp} ('{new_title or ch_sum}')", flush=True)

                    if not v_ts_sorted:
                        print(f"👉 MAJOR SHIFT (topic: '{new_title or ch_sum}')", flush=True)

                    current_topic_title = new_title or ch_sum
                    rolling_summary = up_sum or ch_sum
                else:
                    # CONTINUATION (with optional sub-topic stamps)
                    for stamp in v_ts_sorted:
                        all_timestamps.append(stamp)
                        print(f"📌 SUB-TOPIC:   {stamp}", flush=True)

                    if not v_ts_sorted:
                        print(f"🔄 CONTINUATION (no stamp)", flush=True)

                    rolling_summary = up_sum or ch_sum or rolling_summary

                garbled_notes = res.get("garbled_notes", [])
                if isinstance(garbled_notes, list) and garbled_notes:
                    raw_notes_dir = workspace / "garbled_notes_raw"
                    raw_notes_dir.mkdir(exist_ok=True)
                    gn_lines = [f"- {gn.strip()}" for gn in garbled_notes if isinstance(gn, str) and gn.strip()]
                    if gn_lines:
                        (raw_notes_dir / f"{chunk_idx}.txt").write_text(
                            "GARBLED_NOTES:\n" + "\n".join(gn_lines) + "\n",
                            encoding="utf-8",
                        )

                out_path.write_text(json.dumps({
                    "chunk": chunk_idx,
                    "is_continuation": is_cont,
                    "timestamps": v_ts_sorted,
                    "timestamp": (v_ts_sorted[0] if v_ts_sorted else None),
                    "garbled_notes": garbled_notes,
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
    world_identity_dir: Optional[Path] = None,
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

        prompt = build_group_prompt(
            g_chunks,
            g,
            prev_tail,
            lang,
            signals_map,
            workspace,
            world_identity_dir,
            livechat_loader=load_chunk_livechat,
            activity_loader=load_chunk_activity,
            mood_loader=load_chunk_mood,
        )
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

# ── Garbled Collector & Whisper Audio Ground Truth ───────────────────────────

def run_garbled_collector(
    workspace: Path,
    video_url: Optional[str] = None,
    whisper_bin: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Run whisper_dispatcher.py to transcribe phonetic ground truth and sync dictionary."""
    print("\n[garbled] Checking for garbled notes to collect...")
    raw_dir = workspace / "garbled_notes_raw"
    notes_json = workspace / "garbled_notes.json"

    # Only run if raw candidates or notes exist
    has_raw = raw_dir.is_dir() and any(raw_dir.glob("*.txt"))
    has_notes = notes_json.is_file()

    if not has_raw and not has_notes:
        print("[garbled] No garbled candidates found in workspace. Skipping whisper.cpp verification.")
        return

    try:
        try:
            from whisper_dispatcher import dispatch_verification
        except ImportError:
            from scripts.whisper_dispatcher import dispatch_verification

        print("[garbled] Running whisper_dispatcher.py with local whisper.cpp...")
        ret = dispatch_verification(
            workspace=str(workspace),
            raw_notes_dir=str(raw_dir),
            video_url=video_url,
            whisper_bin=whisper_bin,
            model_bin=model,
            output_json=str(notes_json),
            verbose=False,
        )

        if ret == 0 and notes_json.is_file():
            print("[garbled] Synchronizing resolved entries to garbled_replacements.json...")
            dict_script = _SCRIPT_DIR.parent.parent / "cleaning-auto-transcripts" / "scripts" / "update_garbled_dictionary.py"
            if dict_script.is_file():
                subprocess.run([
                    sys.executable,
                    str(dict_script),
                    "--from-notes", str(notes_json),
                    "--workspace", str(workspace),
                ], check=False)
            print("✅ Garbled collection & dictionary sync complete.")
        else:
            print(f"[garbled] whisper_dispatcher returned status code {ret}.")
    except Exception as e:
        print(f"[garbled] Warning: Garbled collector encountered error ({e}).")

# ── Main Controller ──────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="P100 Single-GPU Timestamper (Recursive & Group Modes).")
    ap.add_argument("workspace", help="Path to youtube_VIDEOID_workspace directory")
    ap.add_argument("--mode", default="recursive", choices=["recursive", "group"],
                    help="Execution mode: recursive (dynamic topic state-machine) or group (fixed 4-chunk groups)")
    ap.add_argument("--endpoint", default="http://100.115.25.30:1234/v1/chat/completions")
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
    ap.add_argument("--block-size", type=int, default=2400)
    ap.add_argument("--world-identity-dir", default=None,
                    help="Path to anibon-world-identity/references/ (auto-discovered if omitted)")
    ap.add_argument("--video-url", default=None,
                    help="YouTube URL for on-the-fly audio stream slicing in whisper_dispatcher")
    ap.add_argument("--whisper-bin", default=None,
                    help="Path to whisper-cli executable (auto-discovered if omitted)")
    ap.add_argument("--whisper-model", default=None,
                    help="Path to whisper GGML model binary (auto-discovered if omitted)")
    ap.add_argument("--no-garbled-collector", action="store_true",
                    help="Disable automatic garbled collector & whisper.cpp ground truth pass after summary")
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

        if not args.no_garbled_collector:
            run_garbled_collector(
                workspace=workspace,
                video_url=args.video_url,
                whisper_bin=args.whisper_bin,
                model=args.whisper_model,
            )
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

    # Resolve world identity references directory
    world_identity_dir: Optional[Path] = (
        Path(args.world_identity_dir) if args.world_identity_dir else WORLD_IDENTITY_DIR
    )
    if world_identity_dir and world_identity_dir.is_dir():
        print(f"[init] world-id    : {world_identity_dir}")
    else:
        world_identity_dir = None
        print("[init] world-id    : not found (world identity context disabled)")

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

    # ── Phonetic & Garbled Correction Mappings ───────────────────────────────
    # garbled_replacements.json: confirmed Whisper ground-truth corrections (2000+ entries).
    # Loaded FIRST so confirmed corrections take priority over heuristic phonetic matches.
    garbled = load_garbled_replacements()
    mappings = load_mappings()
    if garbled:
        print(f"[knowledge] Loaded {len(garbled)} garbled replacement entries (garbled_replacements.json)")
    if mappings:
        print(f"[knowledge] Loaded {len(mappings)} phonetic entity mappings (default_mappings.json)")
    mappings = garbled + mappings  # garbled first = higher priority

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
            world_identity_dir=world_identity_dir,
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
            world_identity_dir=world_identity_dir,
        )

    if not args.no_garbled_collector:
        run_garbled_collector(
            workspace=workspace,
            video_url=args.video_url,
            whisper_bin=args.whisper_bin,
            model=args.whisper_model,
        )


if __name__ == "__main__":
    main()
