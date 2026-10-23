"""
anibon.assembly — Markdown timestamp aggregation, Pass 2 summarization, and parity gates.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from process.audit import audit_timestamps_against_glossary
from process.parity_gates import run_parity_gates
from process.summarizer import (
    assemble_parts,
    enforce_byte_cap,
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
    """Assemble final markdown timestamps document and execute Pass 2 summarizer and parity gates."""
    if args and getattr(args, "byte_cap", False):
        byte_cap = True

    deduped = list(dict.fromkeys(all_timestamps))
    _write_raw_timestamps(workspace, deduped)

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
