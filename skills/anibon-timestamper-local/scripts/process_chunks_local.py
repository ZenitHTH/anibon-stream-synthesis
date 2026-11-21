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
from dataclasses import dataclass
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
    FACE_MOTION_THRESHOLD,
    PRIMARY_HOST,
    REACTION_VERIFY,
    SCENE_DELTA_THRESHOLD,
    WEBCAM_CORNER,
    WORLD_IDENTITY_DIR,
    audit_timestamps_against_glossary,
    call_local,
    call_multimodal,
    call_vision,
    cfg_bool,
    clean_workspace_chunks,
    configure_lm_think_logging,
    detect_signals_for_chunks,
    detect_transcript_source,
    discover_chunks,
    enrich_with_sqlite_databases,
    enrich_workspace_chunks,
    ensure_mood_555,
    extract_entity_glossary,
    finalize_and_assemble_timestamps,
    get_loaded_models,
    is_youtube_auto_transcript,
    load_config,
    load_garbled_replacements,
    load_mappings,
    log_banner,
    log_error,
    log_info,
    log_kv,
    log_ok,
    log_warn,
    prepare_livechat,
    prepare_storyboard_slides,
    reload_config,
    remove_worker_pid,
    resolve_endpoint,
    resolve_model,
    run_garbled_collector,
    run_group_mode,
    run_recursive_mode,
    sample_chunk_keyframes,
    sanitize_and_audit_timestamps,
    save_entity_glossary,
    summarize_lm_trace,
    write_worker_pid,
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
    log_info("knowledge", f"generated entity glossary -> {out_file.name} ({len(glossary)} entries)")
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
    ap.add_argument("--reaction-verify", action="store_true", default=REACTION_VERIFY, help="Enable Pass 1 live webcam closeup fallback when video source exists")
    ap.add_argument("--post-reaction-verify", action="store_true", help="Opt-in: run post-Pass-1 (Pass 2) webcam reaction onset verification")
    ap.add_argument(
        "--webcam-corner",
        default=WEBCAM_CORNER,
        choices=["auto", "top-right", "mid-right", "lower-right", "mid-left", "bottom-right", "bottom-left", "top-left", "fullscreen", "none"],
    )
    ap.add_argument("--log-think", action="store_true", help="Print LM thinking/token metrics live in addition to lm_think_trace.jsonl")
    ap.add_argument("--face-threshold", type=float, default=FACE_MOTION_THRESHOLD)
    ap.add_argument("--remote-snap", action="store_true")
    ap.add_argument("--multimodal-chunks", "--multimodal", dest="multimodal_chunks", action="store_true", default=default_multimodal)
    ap.add_argument("--no-multimodal-chunks", "--no-multimodal", "--text-only", dest="multimodal_chunks", action="store_false")
    ap.add_argument("--eval-batch-size", type=int, default=EVAL_BATCH_SIZE)
    ap.add_argument("--max-chunk-frames", type=int, default=None)
    ap.add_argument("--scene-delta-threshold", type=float, default=SCENE_DELTA_THRESHOLD)
    ap.add_argument("--no-scene-dedup", action="store_true")
    ap.add_argument("--video-file", default=None)
    ap.add_argument("--vision-model", default=None)
    ap.add_argument("--no-knowledge-reader", action="store_true")
    ap.add_argument("--live-chat", action="store_true", help="Download and align live chat replay into livechat/ chunks")
    ap.add_argument("--enrich", dest="enrich", action="store_true", default=True, help="Run pre-chunk storyboard/audio/webcam/Shazam prep before timestamping (default: on)")
    ap.add_argument("--no-enrich", dest="enrich", action="store_false", help="Skip pre-chunk enrichment prep stage")
    ap.add_argument("--api-key", default=os.environ.get("TOKENME_API_KEY") or os.environ.get("LM_API_KEY"))
    return ap


def _load_raw_timestamps_for_summary(workspace: Path) -> List[str]:
    """Load existing timestamps file or exit if missing."""
    raw_ts = workspace / "all_timestamps.txt"
    if not raw_ts.exists():
        log_error("summarize", f"raw timestamps not found: {raw_ts}")
        sys.exit(1)
    return [l.strip() for l in raw_ts.read_text(encoding="utf-8").splitlines() if l.strip()]


def _discover_summary_glossary(workspace: Path, disabled: bool) -> Optional[dict]:
    """Discover domain glossary for summarize-only run."""
    if disabled:
        return None
    sig_map = _load_or_detect_signals(workspace)
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
    log_banner(f"ANIBON TIMESTAMPER :: SUMMARIZE ONLY ({args.lang.upper()})")
    log_info("summarize", f"loaded {len(stamps)} raw timestamps; running assembly")

    glossary = _discover_summary_glossary(workspace, args.no_knowledge_reader)
    out_md, _ = finalize_and_assemble_timestamps(
        workspace=workspace, all_timestamps=stamps, endpoint=args.endpoint, model=model,
        temperature=args.temperature, block_size=args.block_size, no_summarizer_pass=args.no_summarizer_pass,
        args=args, glossary=glossary,
    )
    log_ok("done", f"assembly complete -> {out_md}")


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
        log_kv("init", "world-id", world_identity_dir)
    else:
        world_identity_dir = None
        log_warn("init", "world-id directory not found; world identity context disabled")

    return model, world_identity_dir


def _discover_workspace_chunks(workspace: Path) -> List[Path]:
    """Discover available transcript chunk files or exit gracefully."""
    try:
        return discover_chunks(workspace)
    except FileNotFoundError as e:
        log_error("init", str(e))
        sys.exit(1)


def _load_or_detect_signals(workspace: Path) -> dict:
    """Load existing workspace signals or trigger fresh detection and persist signals.json."""
    signals_file = workspace / "signals.json"
    if signals_file.exists():
        try:
            with open(signals_file, encoding="utf-8") as f:
                data = json.load(f)
            if data:
                return data
        except Exception:
            pass
    log_info("signals", "detecting domain signals across chunks")
    signals = detect_signals_for_chunks(workspace)
    if signals:
        signals_file.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
    return signals


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
        log_info("transcript", "source=YouTube Auto-Transcript -> garbled collector enabled")
        garbled = load_garbled_replacements()
    else:
        log_info("transcript", f"source={src_label.capitalize()}/clean -> garbled collector skipped")
        garbled = []

    mappings = load_mappings()
    if garbled:
        log_info("knowledge", f"loaded {len(garbled)} garbled replacements (garbled_replacements.json)")
    if mappings:
        log_info("knowledge", f"loaded {len(mappings)} phonetic mappings (default_mappings.json)")

    return garbled + mappings, garbled, is_yt_auto


def _print_run_header(args: argparse.Namespace, model: str, total_chunks: int) -> None:
    """Print aligned initialization configuration summary."""
    mm_on = bool(getattr(args, "multimodal_chunks", False))
    rx_on = bool(getattr(args, "reaction_verify", False))
    corner = getattr(args, "webcam_corner", WEBCAM_CORNER)
    remote = bool(getattr(args, "remote_snap", False))
    log_kv("init", "workspace", args.workspace)
    log_kv("init", "model", model)
    log_kv("init", "endpoint", args.endpoint)
    log_kv("init", "multimodal", "enabled" if mm_on else "disabled (text-only)")
    log_kv("init", "reaction-verify", f"enabled (corner={corner}, remote={remote})" if rx_on else "disabled")
    log_kv("init", "total_chunks", total_chunks)


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


def _ensure_livechat_if_requested(workspace: Path, args: argparse.Namespace) -> None:
    """Download and align livechat if --live-chat flag passed."""
    if not getattr(args, "live_chat", False):
        return
    url_file = workspace / ".video_url"
    url = args.video_url or (url_file.read_text(encoding="utf-8").strip() if url_file.is_file() else None)
    if url:
        prepare_livechat(url, workspace)


def _run_prep_stage(workspace: Path, args: argparse.Namespace) -> None:
    """Run pre-chunk storyboard, audio yell/silence webcam, and Shazam prep before Pass 1."""
    if not getattr(args, "enrich", True):
        return
    from process.audio_separator_engine import DEFAULT_AUDIOCPP_URL
    from process.chunk_enrichment import ChunkEnrichConfig, resolve_workspace_media
    from process.music.chunk_scanner import SongScanConfig
    audio_src, video_src = resolve_workspace_media(workspace, args)
    audiocpp_url = os.environ.get("AUDIOCPP_URL") or DEFAULT_AUDIOCPP_URL
    song_cfg = SongScanConfig(
        audiocpp_url=audiocpp_url,
        whisper_bin=getattr(args, "whisper_bin", None),
        whisper_model=getattr(args, "whisper_model", None),
    )
    cfg = ChunkEnrichConfig(
        workspace=workspace,
        audio_source=audio_src,
        video_source=video_src,
        webcam_corner=getattr(args, "webcam_corner", WEBCAM_CORNER),
        song_cfg=song_cfg,
    )
    count = enrich_workspace_chunks(cfg)
    log_info("enrich", f"pre-enriched {count} chunks (storyboard/audio/webcam/Shazam)")


_run_pre_enrichment_if_requested = _run_prep_stage


def _assert_prep_complete(workspace: Path, chunk_files: List[Path]) -> None:
    """Warn on chunks missing pre-stage enrichment caches without aborting text-only runs."""
    enr_dir = workspace / "enrichment"
    missing = [cf.stem for cf in chunk_files if not (enr_dir / f"{cf.stem}.json").is_file()]
    if missing:
        preview = ", ".join(missing[:5]) + ("..." if len(missing) > 5 else "")
        log_warn("enrich", f"prep cache missing for {len(missing)}/{len(chunk_files)} chunks ({preview}); continuing with fallback")


@dataclass(frozen=True)
class _PipelineContext:
    """Bundled runtime inputs for an active chunk processing run."""

    args: argparse.Namespace
    workspace: Path
    model: str
    chunk_files: List[Path]
    world_identity_dir: Optional[Path]


def _run_active_pipeline(ctx: _PipelineContext) -> None:
    """Execute pre-timestamp prep first, then mappings, signals, glossary, and Pass 1 runner."""
    configure_lm_think_logging(
        ctx.workspace / "lm_think_trace.jsonl",
        verbose=bool(getattr(ctx.args, "log_think", False)),
    )
    write_worker_pid(ctx.workspace)
    try:
        _run_prep_stage(ctx.workspace, ctx.args)
        if getattr(ctx.args, "enrich", True):
            _assert_prep_complete(ctx.workspace, ctx.chunk_files)
        mappings, _, is_yt_auto = _prepare_transcript_mappings(ctx.workspace)
        if is_yt_auto:
            clean_workspace_chunks(ctx.workspace)
        signals_map = _load_or_detect_signals(ctx.workspace)
        glossary = _load_or_discover_glossary(
            ctx.workspace, signals_map, ctx.world_identity_dir, ctx.args.no_knowledge_reader
        )
        _dispatch_pipeline_mode(
            ctx.args, ctx.workspace, ctx.model, ctx.chunk_files,
            signals_map, mappings, ctx.world_identity_dir, glossary,
        )
    finally:
        stats = summarize_lm_trace(ctx.workspace / "lm_think_trace.jsonl")
        if stats.get("calls"):
            log_info(
                "lm-think",
                f"summary: calls={stats['calls']}, comp={stats['completion_tokens']} tok ({stats['tok_per_sec']} tok/s), "
                f"think={stats['reasoning_tokens']} tok, errs={stats['errors'] or 'none'}",
            )
        remove_worker_pid(ctx.workspace)


def main() -> None:
    """Main CLI entry point for local timestamp runner."""
    _apply_early_config_override()

    ap = build_argument_parser()
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser()
    args.workspace = str(workspace)
    if not workspace.exists():
        log_error("init", f"workspace not found: {workspace}")
        sys.exit(1)

    if not args.summarize_only:
        log_banner(f"ANIBON TIMESTAMPER :: {args.mode.upper()} MODE ({args.lang.upper()})")
    model, world_identity_dir = _resolve_runtime_targets(args, workspace)
    _ensure_livechat_if_requested(workspace, args)
    ensure_mood_555(workspace)

    if args.summarize_only:
        _run_summarize_only(workspace, model, args)
        return

    chunk_files = _discover_workspace_chunks(workspace)
    _print_run_header(args, model, len(chunk_files))

    if args.dry_run:
        log_info("init", f"dry-run complete ({len(chunk_files)} chunks discovered)")
        return

    _run_active_pipeline(_PipelineContext(args, workspace, model, chunk_files, world_identity_dir))


if __name__ == "__main__":
    main()
