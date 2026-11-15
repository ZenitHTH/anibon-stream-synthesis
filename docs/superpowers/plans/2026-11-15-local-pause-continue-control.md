# Local Timestamper Pause & Continue Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable cooperative live pause and continue for `process_chunks_local.py` via a dedicated CLI control script (`control_chunks_local.py`) so users and AI agents can park an active worker between chunks without killing its PID or dropping in-flight HTTP requests.

**Architecture:** Extract workspace pause-marker (`.pause`), PID-liveness (`timestamper.pid`), and state-preserving wait primitives into a focused module `lib/chunk/pause.py`, exposed through `lib/chunk/__init__.py` and `lib/interface.py`. Wire cooperative pause polling into `lib/process/runners/recursive.py` and `lib/process/runners/group.py`, wire PID tracking into `skills/anibon-timestamper-local/scripts/process_chunks_local.py`, and provide a standalone zero-LLM-dependency CLI at `skills/anibon-timestamper-local/scripts/control_chunks_local.py` (`pause`, `continue`, `status`) that leaves stdout/`timestamper.log` logging solely to the worker.

**Tech Stack:** Python 3.11+, `unittest`, `argparse`, `os`, `pathlib`, `time`, `threading`.

**Spec:** Chat-agreed small-change spec (no separate spec doc):
- Control commands (`pause`, `continue`, `status`) live in a separate Python script (`control_chunks_local.py`), not in `process_chunks_local.py`.
- Worker keeps its PID alive during pause, finishes any in-flight chunk/group cleanly, saves `"phase": "paused"` to `anibon_timestamper_state.json`, sleeps with zero GPU/HTTP requests until unpaused, and logs `[pause]` / `[resume]` to stdout (appending continuously to `timestamper.log` when launched via `launch_local.*`).
- `control_chunks_local.py` never writes directly to `timestamper.log`.

## Global Constraints

- Keep files under 200 lines and functions `<= 20` lines per Clean Code standards (`lib/chunk/state.py` is already 192 lines, so new pause/PID helpers go in `lib/chunk/pause.py`).
- Include `from __future__ import annotations` in every new Python module under `lib/` and `skills/` (enforced by `tests/test_skill_structure.py`).
- Internal library functions must not take boolean flag arguments; split distinct actions (`request_pause`, `clear_pause`).
- `control_chunks_local.py` must not import LM Studio/network/torch dependencies or resolve endpoints/models.
- All unit tests run via `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest` with zero `pytest` imports, zero real network calls, and zero long sleeps.

## Review Focus

1. **Stale or dead `timestamper.pid` when running `pause`**: If a prior worker crashed leaving `timestamper.pid` with a dead or non-numeric PID, `control_chunks_local.py pause` must detect `not is_pid_alive(...)` immediately, refuse to leave a dangling `.pause` file, and exit `1` instead of hanging until timeout (pinned in Task 1 & Task 3).
2. **Pause requested while worker is already inside `_wait_for_network_recovery` (e.g., laptop Wi-Fi dropped right as user packs up)**: `_wait_for_network_recovery` loops on `is_host_reachable`; if `.pause` is set during that loop, it must park via `wait_if_paused` (setting `"phase": "paused"`) rather than spinning on network checks and blocking `pause` confirmation (pinned in Task 2).
3. **Worker completes final chunk and exits while `control_chunks_local.py pause` is waiting for ack**: `wait_for_pause_ack` must notice the PID exited (`"not_running"`), clean up the newly created `.pause` marker so a future run is not unexpectedly parked, and exit `0` cleanly (pinned in Task 1 & Task 3).
4. **State preservation across pause/resume (`current_chunk`/`current_group`, `all_timestamps`, `rolling_summary`, `current_topic_title`, `prev_tail`)**: Entering `"phase": "paused"` and restoring `"recursive_loop"` / `"group_loop"` must mutate only `"phase"` in `anibon_timestamper_state.json`, never clobbering existing fields (pinned in Task 1 & Task 2).
5. **Stale `.pause` leftover before a `--no-resume` clean-slate restart**: Passing `no_resume=True` in recursive or group runner must unlink any leftover `.pause` marker alongside `anibon_timestamper_state.json` so fresh runs never stall immediately (pinned in Task 2).

---

### Task 1: Shared Pause & PID Control Primitives (`lib/chunk/pause.py`)

**Files:**
- Create: `lib/chunk/pause.py`
- Modify: `lib/chunk/__init__.py:18-44`
- Modify: `lib/interface.py:81-99,206-222`
- Test: `skills/anibon-timestamper-local/tests/test_pause_control.py`

**Interfaces:**
- Consumes: `chunk.state.load_state(workspace: Path) -> dict`, `chunk.state.save_state(workspace: Path, state: dict) -> None`
- Produces:
  - `PAUSE_FILENAME: str = ".pause"`
  - `PID_FILENAME: str = "timestamper.pid"`
  - `is_paused(workspace: Path) -> bool`
  - `request_pause(workspace: Path) -> Path`
  - `clear_pause(workspace: Path) -> bool`
  - `write_worker_pid(workspace: Path, pid: Optional[int] = None) -> Path`
  - `read_worker_pid(workspace: Path) -> Optional[int]`
  - `remove_worker_pid(workspace: Path, pid: Optional[int] = None) -> None`
  - `is_pid_alive(pid: Optional[int]) -> bool`
  - `get_worker_status(workspace: Path) -> dict`
  - `wait_if_paused(workspace: Path, active_phase: str, poll_sec: float = 1.0, label: str = "") -> bool`
  - `wait_for_pause_ack(workspace: Path, timeout_sec: float = 180.0, poll_sec: float = 0.5) -> str`

- [ ] **Step 1: Write the failing unit tests in `skills/anibon-timestamper-local/tests/test_pause_control.py`**

```python
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from chunk.pause import (
    clear_pause,
    get_worker_status,
    is_paused,
    is_pid_alive,
    read_worker_pid,
    remove_worker_pid,
    request_pause,
    wait_for_pause_ack,
    wait_if_paused,
    write_worker_pid,
)
from chunk.state import load_state, save_state


class TestPausePrimitives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pause_marker_lifecycle_is_idempotent(self):
        self.assertFalse(is_paused(self.ws))
        marker = request_pause(self.ws)
        self.assertTrue(marker.exists())
        self.assertTrue(is_paused(self.ws))
        self.assertEqual(request_pause(self.ws), marker)
        self.assertTrue(clear_pause(self.ws))
        self.assertFalse(is_paused(self.ws))
        self.assertFalse(clear_pause(self.ws))

    def test_pid_write_read_ownership_remove_and_stale_handling(self):
        write_worker_pid(self.ws, pid=os.getpid())
        self.assertEqual(read_worker_pid(self.ws), os.getpid())
        self.assertTrue(is_pid_alive(os.getpid()))
        remove_worker_pid(self.ws, pid=os.getpid() + 99999)
        self.assertEqual(read_worker_pid(self.ws), os.getpid())
        remove_worker_pid(self.ws, pid=os.getpid())
        self.assertIsNone(read_worker_pid(self.ws))
        (self.ws / "timestamper.pid").write_text("not-a-pid", encoding="utf-8")
        self.assertIsNone(read_worker_pid(self.ws))
        self.assertFalse(is_pid_alive(None))
        self.assertFalse(is_pid_alive(-1))

    def test_wait_if_paused_preserves_state_and_resumes_when_cleared(self):
        save_state(self.ws, {
            "current_chunk": 4,
            "total_chunks": 20,
            "all_timestamps": ["00:01:00 - [Talk] Hi"],
            "current_topic_title": "TopicA",
            "rolling_summary": "SummaryA",
            "phase": "recursive_loop",
        })
        request_pause(self.ws)

        def unpause_soon():
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if load_state(self.ws).get("phase") == "paused":
                    clear_pause(self.ws)
                    return
                time.sleep(0.01)

        t = threading.Thread(target=unpause_soon, daemon=True)
        t.start()
        was_paused = wait_if_paused(self.ws, active_phase="recursive_loop", poll_sec=0.02, label="chunk 4/20")
        t.join(timeout=2.0)

        self.assertTrue(was_paused)
        after = load_state(self.ws)
        self.assertEqual(after["phase"], "recursive_loop")
        self.assertEqual(after["current_chunk"], 4)
        self.assertEqual(after["all_timestamps"], ["00:01:00 - [Talk] Hi"])
        self.assertEqual(after["current_topic_title"], "TopicA")
        self.assertEqual(after["rolling_summary"], "SummaryA")

    def test_wait_for_pause_ack_outcomes(self):
        # 1. Dead/missing worker returns not_running immediately
        write_worker_pid(self.ws, pid=999999)
        with patch("chunk.pause.is_pid_alive", return_value=False):
            self.assertEqual(wait_for_pause_ack(self.ws, timeout_sec=1.0, poll_sec=0.01), "not_running")

        # 2. Live worker with phase == paused returns paused
        write_worker_pid(self.ws, pid=os.getpid())
        save_state(self.ws, {"phase": "paused", "current_chunk": 2, "total_chunks": 10})
        self.assertEqual(wait_for_pause_ack(self.ws, timeout_sec=1.0, poll_sec=0.01), "paused")

        # 3. Live worker still in recursive_loop times out
        save_state(self.ws, {"phase": "recursive_loop", "current_chunk": 2, "total_chunks": 10})
        self.assertEqual(wait_for_pause_ack(self.ws, timeout_sec=0.03, poll_sec=0.01), "timeout")

    def test_get_worker_status_summarizes_fields(self):
        write_worker_pid(self.ws, pid=os.getpid())
        request_pause(self.ws)
        save_state(self.ws, {"phase": "paused", "current_chunk": 3, "total_chunks": 9})
        st = get_worker_status(self.ws)
        self.assertEqual(st["phase"], "paused")
        self.assertTrue(st["paused"])
        self.assertTrue(st["worker_alive"])
        self.assertEqual(st["pid"], os.getpid())
        self.assertEqual(st["current_chunk"], 3)
        self.assertEqual(st["total_chunks"], 9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_pause_control.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chunk.pause'`.

- [ ] **Step 3: Implement `lib/chunk/pause.py` and re-export via `lib/chunk/__init__.py` and `lib/interface.py`**

Implement each small helper (`<= 20` lines, file `< 140` lines) in `lib/chunk/pause.py`:
- `is_paused`, `request_pause` (writes ISO UTC timestamp to `workspace/.pause`), `clear_pause` (unlinks `.pause`).
- `write_worker_pid`, `read_worker_pid`, `remove_worker_pid` (checks stored PID matches `pid or os.getpid()` before unlinking).
- `is_pid_alive(pid: Optional[int]) -> bool`: returns `False` for `None` or `<= 0`; calls `os.kill(pid, 0)` returning `True` on success or `PermissionError`, `False` on `ProcessLookupError`/`OSError`.
- `get_worker_status(workspace: Path) -> dict`: combines `load_state(workspace)`, `is_paused(workspace)`, `read_worker_pid(workspace)`, and `is_pid_alive(pid)` into a dict containing `workspace`, `phase`, `paused`, `pid`, `worker_alive`, `current_chunk`, `total_chunks`, `current_group`, `total_groups`, `last_updated`.
- `wait_if_paused(workspace: Path, active_phase: str, poll_sec: float = 1.0, label: str = "") -> bool`: returns `False` immediately if not `is_paused(workspace)`; copies `load_state(workspace)`, saves `"phase": "paused"`, prints `[pause] Paused{f' at {label}' if label else ''}. Waiting for resume...` with `flush=True`, sleeps `poll_sec` while `is_paused(workspace)`, then copies `load_state(workspace)`, restores `"phase": active_phase`, prints `[resume] Resumed{f' at {label}' if label else ''}.` with `flush=True`, and returns `True`.
- `wait_for_pause_ack(workspace: Path, timeout_sec: float = 180.0, poll_sec: float = 0.5) -> str`: polls until `not is_pid_alive(read_worker_pid(workspace))` (`"not_running"`), `load_state(workspace).get("phase") == "paused"` (`"paused"`), or deadline expires (`"timeout"`).
- Export all public functions in `lib/chunk/__init__.py` and `lib/interface.py` (`__all__`).

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_pause_control.py tests/test_interface.py -v`
Expected: PASS (all tests in `test_pause_control.py` and `test_interface.py`).

- [ ] **Step 5: Commit**

```bash
git add lib/chunk/pause.py lib/chunk/__init__.py lib/interface.py skills/anibon-timestamper-local/tests/test_pause_control.py
git commit -m "feat(pause): add workspace pause marker, PID liveness, and wait primitives"
```

---

### Task 2: Cooperative Pause Polling in Recursive & Group Runners

**Files:**
- Modify: `lib/process/runners/recursive.py:27-52,303-325,481-551`
- Modify: `lib/process/runners/group.py:18-26,179-251`
- Test: `skills/anibon-timestamper-local/tests/test_pause_control.py`

**Interfaces:**
- Consumes (from Task 1): `clear_pause`, `is_paused`, `wait_if_paused` from `chunk.pause`
- Produces:
  - `_wait_for_network_recovery(endpoint: str, poll_interval: float = NETWORK_POLL_INTERVAL_SEC, workspace: Optional[Path] = None) -> None` (backward-compatible optional `workspace`)
  - Pause-aware chunk loop in `run_recursive_mode(...)` (between chunks, inside network wait, and before final assembly)
  - Pause-aware group loop in `run_group_mode(...)` (between groups and before final assembly)
  - `no_resume=True` clears any stale `.pause` marker in both runners

- [ ] **Step 1: Write the failing runner tests in `skills/anibon-timestamper-local/tests/test_pause_control.py`**

```python
import urllib.error
import process_chunks_local as pcl
from process.runners.recursive import _wait_for_network_recovery


class TestRunnerPauseIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "chunks").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_recursive_mode_pauses_between_chunks_and_continues(self):
        for idx in range(2):
            (self.ws / "chunks" / f"chunk_{idx:02d}.txt").write_text(
                f"CHUNK {idx:02d} | 00:0{idx}:00–00:0{idx + 1}:00\n(00:0{idx}:05) hi\n",
                encoding="utf-8",
            )
        events = []

        def fake_call_local(endpoint, model, prompt, max_tokens, temperature, **kwargs):
            events.append(f"call_{len(events)}")
            if len(events) == 1:
                request_pause(self.ws)
            return '{"is_continuation": false, "timestamps": ["00:00:00 - [Talk] ok"], "chunk_summary": "s", "updated_summary": "s", "new_topic_title": "t"}'

        def watcher():
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if load_state(self.ws).get("phase") == "paused":
                    events.append("observed_paused")
                    clear_pause(self.ws)
                    return
                time.sleep(0.01)

        t = threading.Thread(target=watcher, daemon=True)
        t.start()
        with patch.object(pcl, "call_local", side_effect=fake_call_local), \
             patch("process.runners.recursive.PAUSE_POLL_SEC", 0.02), \
             patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(self.ws / "anibon_timestamps.md", [])):
            pcl.run_recursive_mode(
                workspace=self.ws,
                chunk_files=sorted((self.ws / "chunks").glob("chunk_*.txt")),
                endpoint="http://localhost:1234/v1/chat/completions",
                model="test-model", lang="th", max_tokens=200, temperature=0.2,
                signals_map={}, mappings=[], no_resume=True, max_chunks=None,
                no_summarizer_pass=True, block_size=40,
            )
        t.join(timeout=2.0)
        self.assertEqual(events, ["call_0", "observed_paused", "call_1"])
        self.assertEqual(load_state(self.ws).get("phase"), "complete")

    def test_no_resume_clears_leftover_pause_marker(self):
        (self.ws / "chunks" / "chunk_00.txt").write_text("[00:00:00] hi\n", encoding="utf-8")
        request_pause(self.ws)
        with patch.object(pcl, "call_local", return_value='{"is_continuation": true, "chunk_summary": "s", "updated_summary": "s"}'), \
             patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(self.ws / "anibon_timestamps.md", [])):
            pcl.run_recursive_mode(
                workspace=self.ws,
                chunk_files=[self.ws / "chunks" / "chunk_00.txt"],
                endpoint="http://localhost:1234/v1/chat/completions",
                model="test-model", lang="th", max_tokens=200, temperature=0.2,
                signals_map={}, mappings=[], no_resume=True, max_chunks=1,
                no_summarizer_pass=True, block_size=40,
            )
        self.assertFalse(is_paused(self.ws))

    def test_wait_for_network_recovery_respects_pause_marker(self):
        request_pause(self.ws)
        save_state(self.ws, {"phase": "recursive_loop", "current_chunk": 1, "total_chunks": 5})

        def unpause_once_parked():
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if load_state(self.ws).get("phase") == "paused":
                    clear_pause(self.ws)
                    return
                time.sleep(0.01)

        t = threading.Thread(target=unpause_once_parked, daemon=True)
        t.start()
        with patch("process.runners.recursive.is_host_reachable", side_effect=[False, True]), \
             patch("process.runners.recursive.PAUSE_POLL_SEC", 0.02), \
             patch("process.runners.recursive.RECOVERY_STABILIZE_SEC", 0.0):
            _wait_for_network_recovery("http://localhost:1234/v1/chat/completions", poll_interval=0.01, workspace=self.ws)
        t.join(timeout=2.0)
        self.assertEqual(load_state(self.ws).get("phase"), "recursive_loop")

    def test_group_mode_pauses_between_groups_and_continues(self):
        for idx in range(2):
            (self.ws / "chunks" / f"chunk_{idx:02d}.txt").write_text(
                f"CHUNK {idx:02d} | 00:0{idx}:00–00:0{idx + 1}:00\n(00:0{idx}:05) hi\n",
                encoding="utf-8",
            )
        events = []

        def fake_call_local(*args, **kwargs):
            events.append(f"group_{len(events)}")
            if len(events) == 1:
                request_pause(self.ws)
            return "CONTINUATION"

        def watcher():
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if load_state(self.ws).get("phase") == "paused":
                    events.append("observed_paused")
                    clear_pause(self.ws)
                    return
                time.sleep(0.01)

        t = threading.Thread(target=watcher, daemon=True)
        t.start()
        with patch.object(pcl, "call_local", side_effect=fake_call_local), \
             patch("process.runners.group.PAUSE_POLL_SEC", 0.02), \
             patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(self.ws / "anibon_timestamps.md", [])):
            pcl.run_group_mode(
                workspace=self.ws,
                chunk_files=sorted((self.ws / "chunks").glob("chunk_*.txt")),
                endpoint="http://localhost:1234/v1/chat/completions",
                model="test-model", lang="th", max_tokens=200, temperature=0.2,
                group_size=1, signals_map={}, mappings=[], no_resume=True, max_groups=None,
                no_summarizer_pass=True, block_size=40,
            )
        t.join(timeout=2.0)
        self.assertEqual(events, ["group_0", "observed_paused", "group_1"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_pause_control.py -v`
Expected: FAIL (`PAUSE_POLL_SEC` not defined on `process.runners.recursive` / `unexpected keyword argument 'workspace'`).

- [ ] **Step 3: Wire cooperative pause checks in `lib/process/runners/recursive.py` and `lib/process/runners/group.py`**

In `lib/process/runners/recursive.py`:
- Import `clear_pause`, `wait_if_paused` from `chunk.pause` and define module constant `PAUSE_POLL_SEC: float = 1.0`.
- In `_reset_recursive_state`: call `clear_pause(workspace)` when `no_resume` is `True`.
- In `_wait_for_network_recovery(endpoint: str, poll_interval: float = NETWORK_POLL_INTERVAL_SEC, workspace: Optional[Path] = None)`: inside the `while not is_host_reachable(...)` loop, call `if workspace: wait_if_paused(workspace, active_phase="recursive_loop", poll_sec=PAUSE_POLL_SEC, label="network wait")`; thread `workspace` from `_handle_inference_error` and `_call_chunk_model_with_retry` (keep `workspace: Optional[Path] = None` with default `None` so existing signature stays backward compatible).
- In `run_recursive_mode`: right before `_process_single_recursive_chunk` (after `_should_skip_cached_chunk`), call `wait_if_paused(workspace, active_phase="recursive_loop", poll_sec=PAUSE_POLL_SEC, label=f"{chunk_idx} ({i + 1}/{total})")`; also call `wait_if_paused(workspace, active_phase="assemble", poll_sec=PAUSE_POLL_SEC, label="before assembly")` right after the chunk loop before `finalize_fn(...)`.

In `lib/process/runners/group.py`:
- Import `clear_pause`, `wait_if_paused` from `chunk.pause` and define `PAUSE_POLL_SEC: float = 1.0`.
- In `run_group_mode`: when `no_resume` is `True`, call `clear_pause(workspace)`.
- Inside `for g in range(num_groups):` (after skip check, before `_process_single_group`), call `wait_if_paused(workspace, active_phase="group_loop", poll_sec=PAUSE_POLL_SEC, label=f"{group_idx} ({g + 1}/{num_groups})")`; also call `wait_if_paused(workspace, active_phase="assemble", poll_sec=PAUSE_POLL_SEC, label="before assembly")` after the loop before `finalize_fn(...)`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_pause_control.py skills/anibon-timestamper-local/tests/test_process_chunks_resume.py skills/anibon-timestamper-local/tests/test_state.py -v`
Expected: PASS across all tests in all three files.

- [ ] **Step 5: Commit**

```bash
git add lib/process/runners/recursive.py lib/process/runners/group.py skills/anibon-timestamper-local/tests/test_pause_control.py
git commit -m "feat(runners): add cooperative pause polling to recursive and group loops"
```

---

### Task 3: Worker PID Lifecycle (`process_chunks_local.py`) & Control CLI (`control_chunks_local.py`)

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/process_chunks_local.py:372-414`
- Create: `skills/anibon-timestamper-local/scripts/control_chunks_local.py`
- Modify: `skills/anibon-timestamper-local/SKILL.md:301-320`
- Test: `skills/anibon-timestamper-local/tests/test_pause_control.py`

**Interfaces:**
- Consumes (from Task 1): `clear_pause`, `get_worker_status`, `is_pid_alive`, `read_worker_pid`, `remove_worker_pid`, `request_pause`, `wait_for_pause_ack`, `write_worker_pid` from `chunk.pause`
- Produces:
  - `process_chunks_local.py` writes `timestamper.pid` on non-dry-run execution and removes own PID in `finally:`
  - `control_chunks_local.py` CLI:
    - `python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py <workspace> pause [--timeout 180]`
    - `python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py <workspace> continue`
    - `python3 skills/anibon-timestamper-local/scripts/control_chunks_local.py <workspace> status`
  - Public functions in `control_chunks_local.py`: `build_argument_parser() -> argparse.ArgumentParser`, `cmd_pause(workspace: Path, timeout_sec: float) -> int`, `cmd_continue(workspace: Path) -> int`, `cmd_status(workspace: Path) -> int`, `main(argv: Optional[List[str]] = None) -> int`

- [ ] **Step 1: Write the failing control CLI and PID lifecycle tests in `skills/anibon-timestamper-local/tests/test_pause_control.py`**

```python
import io
from contextlib import redirect_stdout
import control_chunks_local as ccl


class TestControlChunksCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pause_refuses_when_no_live_worker_and_leaves_no_dangling_marker(self):
        write_worker_pid(self.ws, pid=999999)
        with patch("chunk.pause.is_pid_alive", return_value=False):
            rc = ccl.main([str(self.ws), "pause", "--timeout", "1"])
        self.assertEqual(rc, 1)
        self.assertFalse(is_paused(self.ws))

    def test_pause_already_paused_returns_zero_immediately(self):
        write_worker_pid(self.ws, pid=os.getpid())
        request_pause(self.ws)
        save_state(self.ws, {"phase": "paused", "current_chunk": 3, "total_chunks": 10})
        rc = ccl.main([str(self.ws), "pause", "--timeout", "1"])
        self.assertEqual(rc, 0)
        self.assertTrue(is_paused(self.ws))

    def test_pause_clears_marker_if_worker_finishes_while_waiting(self):
        write_worker_pid(self.ws, pid=os.getpid())
        save_state(self.ws, {"phase": "recursive_loop", "current_chunk": 9, "total_chunks": 10})
        with patch("control_chunks_local.wait_for_pause_ack", return_value="not_running"):
            rc = ccl.main([str(self.ws), "pause", "--timeout", "1"])
        self.assertEqual(rc, 0)
        self.assertFalse(is_paused(self.ws))

    def test_continue_and_status_commands(self):
        write_worker_pid(self.ws, pid=os.getpid())
        request_pause(self.ws)
        save_state(self.ws, {"phase": "paused", "current_chunk": 4, "total_chunks": 20})

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_status = ccl.main([str(self.ws), "status"])
        self.assertEqual(rc_status, 0)
        out = buf.getvalue()
        self.assertIn("paused", out)
        self.assertIn("4/20", out)
        self.assertIn(str(os.getpid()), out)

        rc_cont = ccl.main([str(self.ws), "continue"])
        self.assertEqual(rc_cont, 0)
        self.assertFalse(is_paused(self.ws))

    def test_process_chunks_local_writes_and_cleans_pid_file(self):
        (self.ws / "chunks").mkdir()
        (self.ws / "chunks" / "chunk_00.txt").write_text("[00:00:00] hi\n", encoding="utf-8")
        observed_pid = {}

        def fake_dispatch(*args, **kwargs):
            observed_pid["during_run"] = read_worker_pid(self.ws)

        with patch.object(pcl, "resolve_endpoint", return_value="http://localhost:1234/v1/chat/completions"), \
             patch.object(pcl, "resolve_model", return_value="test-model"), \
             patch.object(pcl, "ensure_mood_555"), \
             patch.object(pcl, "_prepare_transcript_mappings", return_value=([], [], False)), \
             patch.object(pcl, "_load_or_detect_signals", return_value={}), \
             patch.object(pcl, "_load_or_discover_glossary", return_value={}), \
             patch.object(pcl, "_dispatch_pipeline_mode", side_effect=fake_dispatch), \
             patch("sys.argv", ["process_chunks_local.py", str(self.ws), "--no-knowledge-reader"]):
            pcl.main()

        self.assertEqual(observed_pid.get("during_run"), os.getpid())
        self.assertIsNone(read_worker_pid(self.ws))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest skills/anibon-timestamper-local/tests/test_pause_control.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'control_chunks_local'`.

- [ ] **Step 3: Implement `control_chunks_local.py`, add PID lifecycle to `process_chunks_local.py`, and document usage in `SKILL.md`**

1. In `skills/anibon-timestamper-local/scripts/process_chunks_local.py`:
   - Import `write_worker_pid`, `remove_worker_pid` from `chunk.pause` (or `interface`).
   - Extract `_run_pipeline_with_pid(workspace: Path, args: argparse.Namespace, model: str, world_identity_dir: Optional[Path]) -> None` (or wrap the active execution after `if args.dry_run: return` in `try: write_worker_pid(workspace) ... finally: remove_worker_pid(workspace)`), keeping `main()` `<= 25` lines.
2. Create `skills/anibon-timestamper-local/scripts/control_chunks_local.py` (`< 140` lines, every function `<= 20` lines):
   - UTF-8 stdout/stderr reconfigure matching `process_chunks_local.py`, `_LIB_DIR` path resolution (`Path(__file__).resolve().parents[3] / "lib"`).
   - `build_argument_parser()`: positional `workspace`, positional `action` (`choices=["pause", "continue", "status"]`), `--timeout` (`type=float, default=180.0`, help for `pause`).
   - `cmd_pause(workspace: Path, timeout_sec: float) -> int`:
     - Check `pid = read_worker_pid(workspace)` and `is_pid_alive(pid)`; if not alive, print error `"No active worker running for workspace; pause not set."` and return `1`.
     - If already `is_paused(workspace)` and `get_worker_status(workspace)["phase"] == "paused"`, print `"Already paused."` and return `0`.
     - Call `request_pause(workspace)`. If `timeout_sec <= 0`, print `"Pause marker created (non-blocking)."` and return `0`.
     - Wrap `wait_for_pause_ack(workspace, timeout_sec=timeout_sec)` in `try ... except KeyboardInterrupt:` (on `KeyboardInterrupt`, keep `.pause` and print `"Interrupted wait; pause marker kept for next chunk boundary."` and return `0`).
     - On `"paused"`: print progress and `"Safe to close laptop."`, return `0`.
     - On `"not_running"`: call `clear_pause(workspace)`, print `"Worker exited while waiting; cleared pause marker."`, return `0`.
     - On `"timeout"`: print `"Timed out waiting for active chunk; pause marker kept."`, return `0`.
   - `cmd_continue(workspace: Path) -> int`: calls `clear_pause(workspace)`, checks `is_pid_alive(read_worker_pid(workspace))`, prints status line (`"Resumed worker PID ..."` or `"Cleared pause marker (no active worker running)."`), returns `0`.
   - `cmd_status(workspace: Path) -> int`: formats `get_worker_status(workspace)` cleanly (`workspace`, `phase`, `paused`, `worker`, `progress`, `last_updated`), returns `0`.
   - Validate `workspace.is_dir()` in `main()` (exit `1` if missing).
3. Update `skills/anibon-timestamper-local/SKILL.md` right after section `3. Detached Background Launch` (lines ~318) with a short `#### 3.1 Pause, Continue & Status Control (No PID Kill)` block showing the three `control_chunks_local.py` commands and noting `timestamper.log` continuity.

- [ ] **Step 4: Run full verification test suite**

Run:
```bash
PYTHONPATH="lib:skills/anibon-timestamper-local/scripts" python3 -m unittest \
  skills/anibon-timestamper-local/tests/test_pause_control.py \
  skills/anibon-timestamper-local/tests/test_process_chunks_resume.py \
  skills/anibon-timestamper-local/tests/test_state.py \
  tests/test_interface.py \
  tests/test_skill_structure.py -v
```
Expected: All tests PASS with 0 failures and 0 skipped assertions.

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/control_chunks_local.py \
  skills/anibon-timestamper-local/scripts/process_chunks_local.py \
  skills/anibon-timestamper-local/SKILL.md \
  skills/anibon-timestamper-local/tests/test_pause_control.py
git commit -m "feat(cli): add control_chunks_local.py pause/continue/status and worker PID tracking"
```
