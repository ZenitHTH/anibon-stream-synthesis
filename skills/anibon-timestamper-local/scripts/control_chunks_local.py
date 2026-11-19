"""CLI control utility to pause, continue, or inspect a running local timestamper worker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

_LIB_DIR = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from chunk.pause import (
    DEFAULT_PAUSE_WAIT_SEC,
    clear_pause,
    get_worker_status,
    request_pause,
    wait_for_pause_ack,
)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build argument parser for workspace pause, continue, and status commands."""
    ap = argparse.ArgumentParser(description="Control a running local timestamper worker without killing its PID.")
    ap.add_argument("workspace", help="Path to youtube_VIDEOID_workspace directory")
    ap.add_argument("action", choices=["pause", "continue", "status"], help="Control action to perform")
    ap.add_argument("--timeout", type=float, default=DEFAULT_PAUSE_WAIT_SEC,
                    help="Seconds to wait for active chunk to pause (0 returns immediately)")
    return ap


def _format_progress(status: dict) -> str:
    """Format chunk or group progress ratio from worker status."""
    if status.get("total_chunks"):
        done = status.get("current_chunk") or 0
        return f"chunk {done}/{status['total_chunks']}"
    if status.get("total_groups"):
        done = status.get("current_group") or 0
        return f"group {done}/{status['total_groups']}"
    return "n/a"


def _format_worker(status: dict) -> str:
    """Format live or stale PID status string."""
    pid = status.get("pid")
    if status.get("worker_alive"):
        return f"alive (PID {pid})"
    return f"not running (stale PID {pid})" if pid else "not running"


def _await_pause_ack(workspace: Path, timeout_sec: float) -> int:
    """Wait for worker pause acknowledgement and report final transition."""
    try:
        outcome = wait_for_pause_ack(workspace, timeout_sec=timeout_sec)
    except KeyboardInterrupt:
        print("\n[pause] Interrupted wait; pause marker kept for next chunk boundary.")
        return 0
    if outcome == "paused":
        progress = _format_progress(get_worker_status(workspace))
        print(f"[pause] Paused safely ({progress}). Safe to close laptop.")
        return 0
    if outcome == "not_running":
        clear_pause(workspace)
        print("[pause] Worker exited while waiting; cleared pause marker.")
        return 0
    print(f"[pause] Timed out after {timeout_sec:.0f}s; pause marker kept.")
    return 0


def cmd_pause(workspace: Path, timeout_sec: float) -> int:
    """Request cooperative pause for an active worker and await boundary park."""
    status = get_worker_status(workspace)
    if not status["worker_alive"]:
        print("[pause] No active worker running for workspace; pause not set.", file=sys.stderr)
        return 1
    if status["paused"] and status["phase"] == "paused":
        print(f"[pause] Already paused ({_format_progress(status)}).")
        return 0
    request_pause(workspace)
    if timeout_sec <= 0:
        print("[pause] Pause marker created (non-blocking).")
        return 0
    print(f"[pause] Waiting for active chunk to finish (PID {status['pid']})...")
    return _await_pause_ack(workspace, timeout_sec)


def cmd_continue(workspace: Path) -> int:
    """Remove workspace pause marker so a parked worker resumes."""
    was_paused = clear_pause(workspace)
    status = get_worker_status(workspace)
    if status["worker_alive"]:
        verb = "Resumed" if was_paused else "Already unpaused;"
        print(f"[resume] {verb} worker PID {status['pid']} ({_format_progress(status)}).")
        return 0
    msg = "Cleared pause marker" if was_paused else "Pause marker not set"
    print(f"[resume] {msg} (no active worker running).")
    return 0


def cmd_status(workspace: Path) -> int:
    """Print workspace phase, pause state, worker PID liveness, and progress."""
    status = get_worker_status(workspace)
    print(f"workspace : {status['workspace']}")
    print(f"phase     : {status['phase']}")
    print(f"paused    : {'yes' if status['paused'] else 'no'}")
    print(f"worker    : {_format_worker(status)}")
    print(f"progress  : {_format_progress(status)}")
    if status.get("last_updated"):
        print(f"updated   : {status['last_updated']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for local timestamper pause/continue/status control."""
    args = build_argument_parser().parse_args(argv)
    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        return 1
    if args.action == "pause":
        return cmd_pause(workspace, args.timeout)
    if args.action == "continue":
        return cmd_continue(workspace)
    return cmd_status(workspace)


if __name__ == "__main__":
    sys.exit(main())
