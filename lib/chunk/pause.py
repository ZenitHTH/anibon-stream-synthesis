"""Cooperative pause marker, worker PID liveness, and wait-loop helpers."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from chunk.state import load_state, save_state

PAUSE_FILENAME = ".pause"
PID_FILENAME = "timestamper.pid"
DEFAULT_POLL_SEC = 1.0
DEFAULT_PAUSE_WAIT_SEC = 180.0


def pause_file_path(workspace: Path) -> Path:
    """Return path to workspace pause marker file."""
    return Path(workspace) / PAUSE_FILENAME


def pid_file_path(workspace: Path) -> Path:
    """Return path to workspace worker PID file."""
    return Path(workspace) / PID_FILENAME


def is_paused(workspace: Path) -> bool:
    """Return True if workspace pause marker exists."""
    return pause_file_path(workspace).is_file()


def request_pause(workspace: Path) -> Path:
    """Create pause marker file idempotently and return its path."""
    marker = pause_file_path(workspace)
    if not marker.exists():
        marker.write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
    return marker


def clear_pause(workspace: Path) -> bool:
    """Remove pause marker file if present; return True if removed."""
    marker = pause_file_path(workspace)
    if not marker.exists():
        return False
    marker.unlink(missing_ok=True)
    return True


def write_worker_pid(workspace: Path, pid: Optional[int] = None) -> Path:
    """Persist current or specified worker PID to timestamper.pid."""
    target_pid = os.getpid() if pid is None else pid
    path = pid_file_path(workspace)
    path.write_text(f"{target_pid}\n", encoding="utf-8")
    return path


def read_worker_pid(workspace: Path) -> Optional[int]:
    """Read integer PID from timestamper.pid, returning None if missing or invalid."""
    path = pid_file_path(workspace)
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def remove_worker_pid(workspace: Path, pid: Optional[int] = None) -> None:
    """Unlink timestamper.pid only when it belongs to current or specified PID."""
    expected_pid = os.getpid() if pid is None else pid
    if read_worker_pid(workspace) == expected_pid:
        pid_file_path(workspace).unlink(missing_ok=True)


def is_pid_alive(pid: Optional[int]) -> bool:
    """Return True if POSIX process with given PID exists."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def get_worker_status(workspace: Path) -> dict:
    """Summarize saved checkpoint state, pause marker, and worker PID liveness."""
    ws = Path(workspace)
    state = load_state(ws)
    pid = read_worker_pid(ws)
    return {
        "workspace": str(ws),
        "phase": state.get("phase", "idle"),
        "paused": is_paused(ws),
        "pid": pid,
        "worker_alive": is_pid_alive(pid),
        "current_chunk": state.get("current_chunk"),
        "total_chunks": state.get("total_chunks"),
        "current_group": state.get("current_group"),
        "total_groups": state.get("total_groups"),
        "last_updated": state.get("last_updated"),
    }


def _set_state_phase(workspace: Path, phase: str) -> None:
    """Update only the phase field in anibon_timestamper_state.json."""
    state = dict(load_state(workspace))
    state["phase"] = phase
    save_state(workspace, state)


def wait_if_paused(
    workspace: Path,
    active_phase: str,
    label: str = "",
) -> bool:
    """Park worker in a sleep loop while pause marker exists, preserving state."""
    ws = Path(workspace)
    if not is_paused(ws):
        return False
    suffix = f" at {label}" if label else ""
    _set_state_phase(ws, "paused")
    print(f"[pause] Paused{suffix}. Waiting for resume...", flush=True)
    while is_paused(ws):
        time.sleep(DEFAULT_POLL_SEC)
    _set_state_phase(ws, active_phase)
    print(f"[resume] Resumed{suffix}.", flush=True)
    return True


def wait_for_pause_ack(
    workspace: Path,
    timeout_sec: float = DEFAULT_PAUSE_WAIT_SEC,
    poll_sec: float = 0.5,
) -> str:
    """Wait until live worker enters paused phase, exits, or timeout elapses."""
    ws = Path(workspace)
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while True:
        if not is_pid_alive(read_worker_pid(ws)):
            return "not_running"
        if load_state(ws).get("phase") == "paused":
            return "paused"
        if time.monotonic() >= deadline:
            return "timeout"
        time.sleep(poll_sec)
