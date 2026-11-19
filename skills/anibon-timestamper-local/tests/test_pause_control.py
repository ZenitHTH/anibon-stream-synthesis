import inspect
import io
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_LIB = Path(__file__).resolve().parent.parent.parent.parent / "lib"
for _p in (_SCRIPTS, _LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import control_chunks_local as ccl
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
        with patch("chunk.pause.DEFAULT_POLL_SEC", 0.02):
            was_paused = wait_if_paused(self.ws, active_phase="recursive_loop", label="chunk 4/20")
        t.join(timeout=2.0)

        self.assertLessEqual(len(inspect.signature(wait_if_paused).parameters), 3)

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
             patch("chunk.pause.DEFAULT_POLL_SEC", 0.02), \
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
             patch("chunk.pause.DEFAULT_POLL_SEC", 0.02), \
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
             patch("chunk.pause.DEFAULT_POLL_SEC", 0.02), \
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

        self.assertLessEqual(len(inspect.signature(pcl._run_active_pipeline).parameters), 3)
        self.assertEqual(observed_pid.get("during_run"), os.getpid())
        self.assertIsNone(read_worker_pid(self.ws))

    def test_cli_entrypoints_expand_tilde_workspace(self):
        ws = self.ws / "youtube_tilde_workspace"
        (ws / "chunks").mkdir(parents=True)
        (ws / "chunks" / "chunk_00.txt").write_text("[00:00:00] hi\n", encoding="utf-8")
        with patch.dict(os.environ, {"HOME": str(self.ws)}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc_status = ccl.main(["~/youtube_tilde_workspace", "status"])
            self.assertEqual(rc_status, 0)
            with patch.object(pcl, "resolve_endpoint", return_value="http://localhost:1234/v1/chat/completions"), \
                 patch.object(pcl, "resolve_model", return_value="test-model"), \
                 patch.object(pcl, "ensure_mood_555"), \
                 patch.object(pcl, "_prepare_transcript_mappings", return_value=([], [], False)), \
                 patch.object(pcl, "_load_or_detect_signals", return_value={}), \
                 patch.object(pcl, "_load_or_discover_glossary", return_value={}), \
                 patch.object(pcl, "_dispatch_pipeline_mode"), \
                 patch("sys.argv", ["process_chunks_local.py", "~/youtube_tilde_workspace", "--no-knowledge-reader"]):
                pcl.main()


if __name__ == "__main__":
    unittest.main()
