"""
anibon.garbled_collector — Whisper audio verification and garbled dictionary synchronization.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional


def _has_garbled_candidates(workspace: Path) -> bool:
    """Check if raw garbled candidate notes exist in workspace."""
    raw_dir = workspace / "garbled_notes_raw"
    notes_json = workspace / "garbled_notes.json"
    return bool((raw_dir.is_dir() and any(raw_dir.glob("*.txt"))) or notes_json.is_file())


def _sync_garbled_dictionary(workspace: Path, notes_json: Path) -> None:
    """Sync verified entries from notes_json into garbled_replacements.json."""
    plugin_root = Path(__file__).resolve().parents[2]
    dict_script = plugin_root / "skills" / "cleaning-auto-transcripts" / "scripts" / "update_garbled_dictionary.py"
    if dict_script.is_file():
        subprocess.run([
            sys.executable, str(dict_script),
            "--from-notes", str(notes_json),
            "--workspace", str(workspace),
        ], check=False)
    print("✅ Garbled collection & dictionary sync complete.")


def run_garbled_collector(
    workspace: Path,
    video_url: Optional[str] = None,
    whisper_bin: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Run whisper_dispatcher.py to transcribe phonetic ground truth and sync dictionary."""
    print("\n[garbled] Checking for garbled notes to collect...")
    if not _has_garbled_candidates(workspace):
        print("[garbled] No garbled candidates found in workspace. Skipping whisper.cpp verification.")
        return

    raw_dir = workspace / "garbled_notes_raw"
    notes_json = workspace / "garbled_notes.json"

    try:
        from process.whisper_dispatcher import dispatch_verification

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
            _sync_garbled_dictionary(workspace, notes_json)
        else:
            print(f"[garbled] whisper_dispatcher returned status code {ret}.")
    except Exception as e:
        print(f"[garbled] Warning: Garbled collector encountered error ({e}).")
