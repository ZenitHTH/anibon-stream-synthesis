"""
anibon.assembly — Markdown timestamp aggregation, Pass 2 summarization, and parity gates.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from common.cleaner import _CACHE as _CLEANER_CACHE, clean_text, load_replacements
from common.config import LINE_WARN_LIMIT
from common.time import parse_ts as ts_to_sec
from download.transcript_source import is_youtube_auto_transcript
from process.audit import audit_timestamps_against_glossary
from process.byte_cap import enforce_byte_cap, enforce_line_cap
from process.garbled_collector import run_garbled_collector
from process.parity_gates import run_mood_validation, run_parity_gates
from process.summarizer import (
    assemble_parts,
    prune_essential,
    run_local_summarizer_pass,
)
from process.vision_verify import apply_vision_verify


def _write_raw_timestamps(workspace: Path, deduped: List[str]) -> Path:
    """Save raw deduplicated timestamp lines to all_timestamps.txt."""
    raw_ts = workspace / "all_timestamps.txt"
    raw_ts.write_text("\n".join(deduped), encoding="utf-8")
    print(f"[done] Raw timestamps: {raw_ts}")
    return raw_ts


def _reload_cleaned_raw_timestamps(workspace: Path, fallback: List[str]) -> List[str]:
    """Reload all_timestamps.txt and apply updated garbled replacements in-place."""
    _CLEANER_CACHE.clear()
    raw_ts = workspace / "all_timestamps.txt"
    if not raw_ts.is_file():
        return fallback
    compiled = load_replacements()
    lines = [clean_text(l.strip(), compiled) for l in raw_ts.read_text(encoding="utf-8").splitlines() if l.strip()]
    if lines:
        raw_ts.write_text("\n".join(lines), encoding="utf-8")
        return lines
    return fallback


def _collect_and_clean_garbled(
    workspace: Path,
    deduped: List[str],
    endpoint: str,
    model: str,
    args: Optional[argparse.Namespace],
) -> List[str]:
    """Run Whisper garbled collector before summarization and reload cleaned timestamps."""
    no_gc = bool(args and getattr(args, "no_garbled_collector", False))
    if no_gc or not is_youtube_auto_transcript(workspace):
        return deduped

    run_garbled_collector(
        workspace=workspace,
        video_url=getattr(args, "video_url", None) if args else None,
        whisper_bin=getattr(args, "whisper_bin", None) if args else None,
        whisper_model=getattr(args, "whisper_model", None) if args else None,
        endpoint=endpoint,
        llm_model=model,
    )
    return _reload_cleaned_raw_timestamps(workspace, deduped)


def _prune_and_verify_timestamps(
    deduped: List[str],
    workspace: Path,
    endpoint: str,
    model: str,
    temperature: float,
    args: Optional[argparse.Namespace],
    no_summarizer_pass: bool,
) -> List[str]:
    """Optionally run visual verification and LLM pruning passes."""
    if args:
        deduped = apply_vision_verify(deduped, workspace, args, model)
    if not no_summarizer_pass:
        deduped = prune_essential(endpoint, model, deduped, temperature)
    return deduped


def _assemble_parts_content(
    deduped: List[str],
    workspace: Path,
    endpoint: str,
    model: str,
    temperature: float,
    block_size: int,
    no_summarizer_pass: bool,
    byte_cap: bool,
) -> str:
    """Generate part summaries via local LLM or fallback double-border heuristic."""
    assembled = None
    if not no_summarizer_pass:
        assembled = run_local_summarizer_pass(endpoint, model, deduped, workspace, temperature)
    if not assembled:
        print("[assemble] Using heuristic double-border part assembly.")
        assembled = assemble_parts(deduped, workspace, block_size)
    if not no_summarizer_pass and assembled:
        assembled = enforce_line_cap(assembled, limit=LINE_WARN_LIMIT)
    if byte_cap:
        assembled = enforce_byte_cap(assembled)
    return assembled


def finalize_and_assemble_timestamps(
    workspace: Path,
    all_timestamps: List[str],
    endpoint: str,
    model: str,
    temperature: float,
    block_size: int,
    no_summarizer_pass: bool,
    args: Optional[argparse.Namespace] = None,
    glossary: Optional[dict] = None,
    byte_cap: bool = False,
) -> Tuple[Path, List[str]]:
    """Validate mood, collect garbled words, summarize, enforce limits, and run parity gates."""
    if args and getattr(args, "byte_cap", False):
        byte_cap = True

    deduped = sorted(list(dict.fromkeys(all_timestamps)), key=ts_to_sec)
    raw_ts = _write_raw_timestamps(workspace, deduped)
    run_mood_validation(workspace, raw_ts)
    deduped = _collect_and_clean_garbled(workspace, deduped, endpoint, model, args)

    deduped = _prune_and_verify_timestamps(
        deduped, workspace, endpoint, model, temperature, args, no_summarizer_pass
    )
    assembled = _assemble_parts_content(
        deduped, workspace, endpoint, model, temperature, block_size, no_summarizer_pass, byte_cap
    )

    out_md = workspace / "anibon_timestamps.md"
    out_md.write_text(assembled, encoding="utf-8")
    if glossary:
        audit_timestamps_against_glossary(out_md, glossary)

    print(f"[done] Final timestamps: {out_md}")
    run_parity_gates(workspace, out_md)
    return out_md, deduped
