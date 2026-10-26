"""
anibon.garbled_collector — Whisper audio verification and garbled dictionary synchronization.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from common.lmstudio import call_local
from process.garbled_resolver import LlmTarget, resolve_garbled_notes
from process.garbled_rules import (
    has_garbled_candidates,
    is_safe_replacement,
    is_valid_candidate_token,
    load_domain_hint,
    load_raw_transcript_compact,
    strip_filler_prefix,
)

_is_safe_replacement = is_safe_replacement
_is_valid_candidate_token = is_valid_candidate_token
_strip_filler_prefix = strip_filler_prefix
_load_raw_transcript_compact = load_raw_transcript_compact
_load_domain_hint = load_domain_hint
_has_garbled_candidates = has_garbled_candidates


@dataclass(frozen=True)
class GarbledCollectorOptions:
    """Configuration options for garbled collector pipeline."""
    video_url: Optional[str] = None
    whisper_bin: Optional[str] = None
    whisper_model: Optional[str] = None
    endpoint: Optional[str] = None
    llm_model: Optional[str] = None


def _sync_garbled_dictionary(workspace: Path, notes_json: Path) -> None:
    """Sync verified entries from notes_json into garbled_replacements.json."""
    plugin_root = Path(__file__).resolve().parents[2]
    script = plugin_root / "skills" / "cleaning-auto-transcripts" / "scripts" / "update_garbled_dictionary.py"
    if script.is_file():
        subprocess.run([
            sys.executable, str(script),
            "--from-notes", str(notes_json),
            "--workspace", str(workspace),
        ], check=False)
    print("✅ Garbled collection & dictionary sync complete.")


def _coerce_collector_options(
    options: Optional[GarbledCollectorOptions],
    kwargs: Dict[str, Any],
) -> GarbledCollectorOptions:
    if options is not None:
        return options
    return GarbledCollectorOptions(
        video_url=kwargs.get("video_url"),
        whisper_bin=kwargs.get("whisper_bin"),
        whisper_model=kwargs.get("whisper_model") or kwargs.get("model"),
        endpoint=kwargs.get("endpoint"),
        llm_model=kwargs.get("llm_model"),
    )


def _run_whisper_dispatch(
    workspace: Path, notes_json: Path, opts: GarbledCollectorOptions
) -> int:
    from process.whisper_dispatcher import dispatch_verification

    print("[garbled] Running whisper_dispatcher.py with local whisper.cpp...")
    return dispatch_verification(
        workspace=str(workspace),
        raw_notes_dir=str(workspace / "garbled_notes_raw"),
        video_url=opts.video_url,
        whisper_bin=opts.whisper_bin,
        model_bin=opts.whisper_model,
        output_json=str(notes_json),
        verbose=False,
    )


def _resolve_and_sync(
    workspace: Path, notes_json: Path, opts: GarbledCollectorOptions
) -> None:
    target = LlmTarget(endpoint=opts.endpoint, model=opts.llm_model)
    resolve_garbled_notes(workspace, notes_json, target)
    print("[garbled] Synchronizing resolved entries to garbled_replacements.json...")
    _sync_garbled_dictionary(workspace, notes_json)


def _execute_garbled_collection(workspace: Path, opts: GarbledCollectorOptions) -> None:
    notes_json = workspace / "garbled_notes.json"
    try:
        ret = _run_whisper_dispatch(workspace, notes_json, opts)
        if ret == 0 and notes_json.is_file():
            _resolve_and_sync(workspace, notes_json, opts)
        else:
            print(f"[garbled] whisper_dispatcher returned status code {ret}.")
    except Exception as e:
        print(f"[garbled] Warning: Garbled collector encountered error ({e}).")


def run_garbled_collector(
    workspace: Path,
    options: Optional[GarbledCollectorOptions] = None,
    **kwargs: Any,
) -> None:
    """Run whisper_dispatcher.py to transcribe phonetic ground truth, resolve, and sync dictionary."""
    print("\n[garbled] Checking for garbled notes to collect...")
    if not has_garbled_candidates(workspace):
        print("[garbled] No garbled candidates found in workspace. Skipping whisper.cpp verification.")
        return
    opts = _coerce_collector_options(options, kwargs)
    _execute_garbled_collection(workspace, opts)
