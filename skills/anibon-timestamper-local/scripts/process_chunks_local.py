"""
process_chunks_local.py — Local LLM chunk runner for Anibon timestamping on Tesla P100 (16GB).

Two execution modes:
1. --mode recursive (RECOMMENDED): Dynamic rolling summary state-machine.
   Tracks topic flow across chunks organically (not locked to arbitrary minutes).
   Accumulates rolling context when topics continue, flushes summary when topics pivot.
2. --mode group: Batched processing across groups of chunks (~16-20 min windows).

Architecture:
- anibon.audit: Transcript cleaning, phonetic drift sanitization, and entity glossary auditing.
- anibon.assembly: Markdown part assembly, pruning, and parity gate execution.
- anibon.garbled_collector: Whisper ground-truth audio verification & dictionary sync.
- anibon.runners: Modular execution runners (recursive state-machine & group windowing).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Enforce UTF-8 encoding on standard streams to prevent Thai character truncation/corruption
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# ── Shared Library Path Resolution ──────────────────────────────────────────
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
for p in (_SCRIPT_DIR, _LIB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from interface import (
    CHUNK_MAX_TOKENS,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CHAT_PATH,
    DEFAULT_GROUP_SIZE,
    DEFAULT_PORT,
    DEFAULT_TEMPERATURE,
    EVAL_BATCH_SIZE,
    PRIMARY_HOST,
    SCENE_DELTA_THRESHOLD,
    WORLD_IDENTITY_DIR,
    audit_timestamps_against_glossary,
    call_local,
    call_multimodal,
    call_vision,
    cfg_bool,
    detect_signals_for_chunks,
    detect_transcript_source,
    discover_chunks,
    enrich_with_sqlite_databases,
    ensure_mood_555,
    extract_entity_glossary,
    finalize_and_assemble_timestamps,
    get_loaded_models,
    is_youtube_auto_transcript,
    load_config,
    load_garbled_replacements,
    load_mappings,
    prepare_storyboard_slides,
    reload_config,
    resolve_endpoint,
    resolve_model,
    run_garbled_collector,
    run_group_mode,
    run_recursive_mode,
    sample_chunk_keyframes,
    sanitize_and_audit_timestamps,
    save_entity_glossary,
)

# Re-exports for test compatibility
__all__ = [
    "run_knowledge_discovery",
    "sanitize_and_audit_timestamps",
    "audit_timestamps_against_glossary",
    "finalize_and_assemble_timestamps",
    "run_recursive_mode",
    "run_group_mode",
    "run_garbled_collector",
    "build_argument_parser",
    "main",
    "call_local",
    "call_multimodal",
    "sample_chunk_keyframes",
    "prepare_storyboard_slides",
]


# ── Domain Knowledge Discovery ──────────────────────────────────────────────


def _load_signals_from_file(workspace: Path) -> dict:
    """Read signals.json from workspace if present, or return empty dict."""
    sig_file = workspace / "signals.json"
    if not sig_file.is_file():
        return {}
    try:
        with open(sig_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run_knowledge_discovery(
    workspace: Path,
    signals_map: Optional[dict] = None,
    world_identity_dir: Optional[Path] = None,
) -> Path:
    """Auto-discover domain references, bootstrap DBs, and emit <workspace>/entity_glossary.json."""
    workspace = Path(workspace)
    if signals_map is None:
        signals_map = _load_signals_from_file(workspace)

    ref_dir = world_identity_dir or WORLD_IDENTITY_DIR
    glossary = extract_entity_glossary(signals_map, ref_dir)
    glossary = enrich_with_sqlite_databases(glossary, signals_map)
    out_file = save_entity_glossary(glossary, workspace)
    print(f"[knowledge] Generated entity glossary with {len(glossary)} entries -> {out_file.name}")
    return out_file


# ── Argument Parser & Main Controller ────────────────────────────────────────


def build_argument_parser() -> argparse.ArgumentParser:
    """Build command line argument parser for local timestamper."""
    default_multimodal = cfg_bool("multimodal_chunks", True)
    ap = argparse.ArgumentParser(description="P100 Single-GPU Timestamper (Recursive & Group Modes).")
    ap.add_argument("workspace", help="Path to youtube_VIDEOID_workspace directory")
    ap.add_argument("--mode", default="recursive", choices=["recursive", "group"],
                    help="Execution mode: recursive (dynamic topic state-machine) or group (fixed 4-chunk groups)")
    ap.add_argument("--endpoint", default=f"http://{PRIMARY_HOST}:{DEFAULT_PORT}{DEFAULT_CHAT_PATH}")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--force-model", action="store_true")
    ap.add_argument("--lang", default="th", choices=["th", "en"])
    ap.add_argument("--max-tokens", type=int, default=CHUNK_MAX_TOKENS)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--group-size", type=int, default=DEFAULT_GROUP_SIZE)
    ap.add_argument("--no-summarizer-pass", action="store_true")
    ap.add_argument("--byte-cap", action="store_true")
    ap.add_argument("--summarize-only", action="store_true")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chunks", type=int, default=None)
    ap.add_argument("--max-groups", type=int, default=None)
    ap.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    ap.add_argument("--config", "--env-file", dest="config_file", default=None)
    ap.add_argument("--world-identity-dir", default=None)
    ap.add_argument("--video-url", default=None)
    ap.add_argument("--whisper-bin", default=None)
    ap.add_argument("--whisper-model", default=None)
    ap.add_argument("--no-garbled-collector", action="store_true")
    ap.add_argument("--vision-verify", action="store_true")
    ap.add_argument("--multimodal-chunks", "--multimodal", dest="multimodal_chunks", action="store_true", default=default_multimodal)
    ap.add_argument("--no-multimodal-chunks", "--no-multimodal", "--text-only", dest="multimodal_chunks", action="store_false")
    ap.add_argument("--eval-batch-size", type=int, default=EVAL_BATCH_SIZE)
    ap.add_argument("--max-chunk-frames", type=int, default=None)
    ap.add_argument("--scene-delta-threshold", type=float, default=SCENE_DELTA_THRESHOLD)
    ap.add_argument("--no-scene-dedup", action="store_true")
    ap.add_argument("--video-file", default=None)
    ap.add_argument("--vision-model", default=None)
    ap.add_argument("--no-knowledge-reader", action="store_true")
    ap.add_argument("--api-key", default=os.environ.get("TOKENME_API_KEY") or os.environ.get("LM_API_KEY"))
    return ap


def _load_raw_timestamps_for_summary(workspace: Path) -> List[str]:
    """Load existing timestamps file or exit if missing."""
    raw_ts = workspace / "all_timestamps.txt"
    if not raw_ts.exists():
        print(f"ERROR: {raw_ts} not found for --summarize-only", file=sys.stderr)
        sys.exit(1)
    return [l.strip() for l in raw_ts.read_text(encoding="utf-8").splitlines() if l.strip()]


def _discover_summary_glossary(workspace: Path, disabled: bool) -> Optional[dict]:
    """Discover domain glossary for summarize-only run."""
    if disabled:
        return None
    sig_map = _load_signals_from_file(workspace)
    g_path = run_knowledge_discovery(workspace, sig_map, world_identity_dir=None)
    if g_path.exists():
        try:
            with open(g_path, encoding="utf-8") as gf:
                return json.load(gf)
        except Exception:
            return None
    return None


def _run_summarize_only(workspace: Path, model: str, args: argparse.Namespace) -> None:
    """Execute Pass 2 summarizer pass on existing raw timestamps."""
    stamps = _load_raw_timestamps_for_summary(workspace)
    print(f"[summarize-only] Loaded {len(stamps)} timestamps. Running assembly...")

    glossary = _discover_summary_glossary(workspace, args.no_knowledge_reader)
    out_md, _ = finalize_and_assemble_timestamps(
        workspace=workspace, all_timestamps=stamps, endpoint=args.endpoint, model=model,
        temperature=args.temperature, block_size=args.block_size, no_summarizer_pass=args.no_summarizer_pass,
        args=args, glossary=glossary,
    )
    print(f"✅ Assembly complete: {out_md}")

    _finalize_garbled_collector(workspace, args, model)


def _apply_early_config_override() -> None:
    """Process --config / --env-file before full CLI argument parsing."""
    temp_ap = argparse.ArgumentParser(add_help=False)
    temp_ap.add_argument("--config", "--env-file", dest="config_file", default=None)
    temp_args, _ = temp_ap.parse_known_args()
    if temp_args.config_file:
        load_config(Path(temp_args.config_file), override=True)
        reload_config()


def _resolve_runtime_targets(
    args: argparse.Namespace,
    workspace: Path,
) -> Tuple[str, Optional[Path]]:
    """Resolve model identifier, endpoint, and world identity reference directory."""
    if args.api_key:
        os.environ["TOKENME_API_KEY"] = args.api_key

    args.endpoint = resolve_endpoint(args.endpoint)
    model = resolve_model(args.model, args.endpoint, force=args.force_model)

    world_identity_dir: Optional[Path] = (
        Path(args.world_identity_dir) if args.world_identity_dir else WORLD_IDENTITY_DIR
    )
    if world_identity_dir and world_identity_dir.is_dir():
        print(f"[init] world-id    : {world_identity_dir}")
    else:
        world_identity_dir = None
        print("[init] world-id    : not found (world identity context disabled)")

    return model, world_identity_dir


def _discover_workspace_chunks(workspace: Path) -> List[Path]:
    """Discover available transcript chunk files or exit gracefully."""
    try:
        return discover_chunks(workspace)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def _load_or_detect_signals(workspace: Path) -> dict:
    """Load existing workspace signals or trigger fresh detection."""
    signals_file = workspace / "signals.json"
    if not signals_file.exists():
        print("[signals] Detecting domain signals...")
        return detect_signals_for_chunks(workspace)
    try:
        with open(signals_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return detect_signals_for_chunks(workspace)


def _load_or_discover_glossary(
    workspace: Path,
    signals_map: dict,
    world_identity_dir: Optional[Path],
    disabled: bool,
) -> dict:
    """Generate or read entity glossary unless explicitly disabled."""
    if disabled:
        return {}
    glossary_path = run_knowledge_discovery(workspace, signals_map, world_identity_dir)
    try:
        with open(glossary_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _prepare_transcript_mappings(workspace: Path) -> Tuple[list, list, bool]:
    """Detect transcript source and prepare phonetic mappings and garbled dictionaries."""
    is_yt_auto = is_youtube_auto_transcript(workspace)
    src_label = detect_transcript_source(workspace)

    if is_yt_auto:
        print("[transcript] Source: YouTube Auto-Transcript -> Enabling Garbled replacements & collector.")
        garbled = load_garbled_replacements()
    else:
        print(f"[transcript] Source: {src_label.capitalize()}/clean transcript -> Skipping Garbled replacements & collector.")
        garbled = []

    mappings = load_mappings()
    if garbled:
        print(f"[knowledge] Loaded {len(garbled)} garbled replacement entries (garbled_replacements.json)")
    if mappings:
        print(f"[knowledge] Loaded {len(mappings)} phonetic entity mappings (default_mappings.json)")

    return garbled + mappings, garbled, is_yt_auto


def _print_run_header(
    workspace: Path,
    model: str,
    endpoint: str,
    mode: str,
    multimodal: bool,
    total_chunks: int,
    lang: str,
) -> None:
    """Print initialization status header."""
    print(f"[init] workspace   : {workspace}")
    print(f"[init] model       : {model}")
    print(f"[init] endpoint    : {endpoint}")
    print(f"[init] mode        : {mode}")
    print(f"[init] multimodal  : {'enabled' if multimodal else 'disabled (text-only)'}")
    print(f"[init] total chunks: {total_chunks}")
    print(f"[init] lang        : {lang}")


def _dispatch_pipeline_mode(
    args: argparse.Namespace,
    workspace: Path,
    model: str,
    chunk_files: List[Path],
    signals_map: dict,
    mappings: list,
    world_identity_dir: Optional[Path],
    glossary: dict,
) -> None:
    """Route execution to recursive or group runner mode."""
    if args.mode == "recursive":
        run_recursive_mode(
            workspace=workspace, chunk_files=chunk_files, endpoint=args.endpoint, model=model,
            lang=args.lang, max_tokens=args.max_tokens, temperature=args.temperature,
            signals_map=signals_map, mappings=mappings, no_resume=args.no_resume,
            max_chunks=args.max_chunks, no_summarizer_pass=args.no_summarizer_pass,
            block_size=args.block_size, world_identity_dir=world_identity_dir, args=args, glossary=glossary,
        )
    else:
        run_group_mode(
            workspace=workspace, chunk_files=chunk_files, endpoint=args.endpoint, model=model,
            lang=args.lang, max_tokens=args.max_tokens, temperature=args.temperature,
            group_size=args.group_size, signals_map=signals_map, mappings=mappings,
            no_resume=args.no_resume, max_groups=args.max_groups, no_summarizer_pass=args.no_summarizer_pass,
            block_size=args.block_size, world_identity_dir=world_identity_dir, args=args, glossary=glossary,
        )


def _finalize_garbled_collector(workspace: Path, args: argparse.Namespace, model: str) -> None:
    """Run whisper audio verification if running on YouTube auto-transcript."""
    if is_youtube_auto_transcript(workspace) and not args.no_garbled_collector:
        run_garbled_collector(
            workspace=workspace,
            video_url=args.video_url,
            whisper_bin=args.whisper_bin,
            whisper_model=args.whisper_model,
            endpoint=args.endpoint,
            llm_model=model,
        )
    elif not is_youtube_auto_transcript(workspace):
        print("[garbled] Skipping whisper.cpp collection (not a YouTube auto-transcript).")


def main() -> None:
    """Main CLI entry point for local timestamp runner."""
    _apply_early_config_override()

    ap = build_argument_parser()
    args = ap.parse_args()

    workspace = Path(args.workspace)
    if not workspace.exists():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)

    model, world_identity_dir = _resolve_runtime_targets(args, workspace)
    ensure_mood_555(workspace)

    if args.summarize_only:
        _run_summarize_only(workspace, model, args)
        return

    chunk_files = _discover_workspace_chunks(workspace)
    _print_run_header(
        workspace, model, args.endpoint, args.mode,
        getattr(args, "multimodal_chunks", False), len(chunk_files), args.lang
    )

    if args.dry_run:
        print(f"[dry-run] Discovered {len(chunk_files)} chunks.")
        return

    signals_map = _load_or_detect_signals(workspace)
    glossary = _load_or_discover_glossary(workspace, signals_map, world_identity_dir, args.no_knowledge_reader)
    mappings, _, is_yt_auto = _prepare_transcript_mappings(workspace)

    _dispatch_pipeline_mode(
        args, workspace, model, chunk_files, signals_map, mappings, world_identity_dir, glossary
    )
    _finalize_garbled_collector(workspace, args, model)


if __name__ == "__main__":
    main()
