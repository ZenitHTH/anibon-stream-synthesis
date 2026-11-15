import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_LIB = Path(__file__).resolve().parent.parent.parent.parent / "lib"
for _p in (_SCRIPTS, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import process_chunks_local as pcl
from process.runners.recursive import _wait_for_network_recovery

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
        write_worker_pid(self.ws, pid=999999)
        with patch("chunk.pause.is_pid_alive", return_value=False):
            self.assertEqual(wait_for_pause_ack(self.ws, timeout_sec=1.0, poll_sec=0.01), "not_running")

        write_worker_pid(self.ws, pid=os.getpid())
        save_state(self.ws, {"phase": "paused", "current_chunk": 2, "total_chunks": 10})
        self.assertEqual(wait_for_pause_ack(self.ws, timeout_sec=1.0, poll_sec=0.01), "paused")

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
        calls = {"n": 0}

        def fake_call_local(endpoint, model, prompt, max_tokens, temperature, **kwargs):
            idx = calls["n"]
            calls["n"] += 1
            events.append(f"call_{idx}")
            if idx == 0:
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
        calls = {"n": 0}

        def fake_call_local(*args, **kwargs):
            idx = calls["n"]
            calls["n"] += 1
            events.append(f"group_{idx}")
            if idx == 0:
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


if __name__ == "__main__":
    unittest.main()
