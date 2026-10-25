import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_LIB = Path(__file__).resolve().parent.parent.parent.parent / "lib"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import process_chunks_local as pcl


class TestProcessChunksResumeAndCleanSlate(unittest.TestCase):
    def test_no_resume_purges_stale_recursive_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] สวัสดีครับ\n", encoding="utf-8")

            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()
            stale_file = out_dir / "chunk_05.json"
            stale_file.write_text('{"chunk": "chunk_05", "timestamps": ["00:25:00 - [Talk] Stale"]}', encoding="utf-8")

            with patch.object(pcl, "call_local", return_value='{"is_continuation": false, "timestamps": ["00:00:00 - [Talk] เริ่มสตรีม"], "chunk_summary": "เริ่ม", "updated_summary": "เริ่ม", "new_topic_title": "เริ่ม"}'), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", ["00:00:00 - [Talk] เริ่มสตรีม"])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertFalse(stale_file.exists(), "Stale chunk_05.json must be deleted when no_resume=True")
            self.assertTrue((out_dir / "chunk_00.json").exists())

    def test_resume_restores_multiple_timestamps_from_chunk_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] A\n", encoding="utf-8")

            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()
            (out_dir / "chunk_00.json").write_text(json.dumps({
                "chunk": "chunk_00",
                "timestamps": [
                    "00:01:00 - [Talk] ประเด็นแรก",
                    "00:03:00 - [News] ประเด็นสอง",
                ],
                "timestamp": "00:01:00 - [Talk] ประเด็นแรก",
                "current_topic_title": "ข่าว",
                "rolling_summary": "สรุป",
            }), encoding="utf-8")

            captured = {}
            def fake_finalize(workspace, all_timestamps, **kwargs):
                captured["stamps"] = list(all_timestamps)
                return workspace / "anibon_timestamps.md", list(all_timestamps)

            with patch.object(pcl, "finalize_and_assemble_timestamps", side_effect=fake_finalize):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=False,
                    max_chunks=None,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertEqual(
                captured.get("stamps"),
                ["00:01:00 - [Talk] ประเด็นแรก", "00:03:00 - [News] ประเด็นสอง"],
            )

    def test_no_resume_unlinks_state_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] Test\n", encoding="utf-8")
            state_file = ws / "anibon_timestamper_state.json"
            state_file.write_text('{"phase": "prior"}', encoding="utf-8")

            with patch.object(pcl, "call_local", return_value='{"is_continuation": true, "chunk_summary": "ok", "updated_summary": "ok"}'), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", [])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            # Newly saved state for chunk_00 should reflect chunk 1, not the stale prior state
            self.assertTrue(state_file.exists())
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved.get("current_chunk"), 1)

    def test_cli_flags_forwarded_to_sample_chunk_keyframes(self):
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] Test\n", encoding="utf-8")
            slides_dir = ws / "frames" / "slides_clean"
            slides_dir.mkdir(parents=True)
            (slides_dir / "slide_0001.jpg").write_bytes(b"dummy")

            fake_args = argparse.Namespace(
                multimodal_chunks=True,
                no_scene_dedup=True,
                scene_delta_threshold=0.12,
                max_chunk_frames=8,
                eval_batch_size=4096,
                video_url=None,
            )

            captured_kwargs = {}
            def fake_sample(*args, **kwargs):
                captured_kwargs.update(kwargs)
                return [("00:00:00", Path("/tmp/t.jpg"), "b64")]

            with patch.object(pcl, "sample_chunk_keyframes", side_effect=fake_sample), \
                 patch.object(pcl, "prepare_storyboard_slides", return_value=slides_dir), \
                 patch.object(pcl, "call_multimodal", return_value='{"is_continuation": true, "chunk_summary": "ok", "updated_summary": "ok"}'), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", [])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                    args=fake_args,
                )

            self.assertFalse(captured_kwargs.get("scene_dedup"))
            self.assertEqual(captured_kwargs.get("delta_threshold"), 0.12)
            self.assertEqual(captured_kwargs.get("num_frames"), 8)
            self.assertEqual(captured_kwargs.get("eval_batch_size"), 4096)

    def test_chunk_redo_on_timeout_does_not_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] สวัสดีครับ\n", encoding="utf-8")
            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()

            import urllib.error
            calls = {"count": 0}
            def fake_call_local(*args, **kwargs):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise urllib.error.URLError("Operation timed out")
                return '{"is_continuation": false, "timestamps": ["00:00:00 - [Talk] สำเร็จ"], "chunk_summary": "ok", "updated_summary": "ok", "new_topic_title": "สำเร็จ"}'

            with patch.object(pcl, "call_local", side_effect=fake_call_local), \
                 patch("process.runners.recursive.is_host_reachable", return_value=True), \
                 patch("process.runners.recursive.time.sleep", return_value=None), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", [])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertTrue((out_dir / "chunk_00.json").exists(), "Chunk 00 must be retried and saved, never skipped")
            self.assertGreaterEqual(calls["count"], 2, "Must have retried after timeout failure")

    def test_chunk_redo_on_unparseable_json_does_not_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks_dir = ws / "chunks"
            chunks_dir.mkdir()
            (chunks_dir / "chunk_00.txt").write_text("[00:00:00] สวัสดีครับ\n", encoding="utf-8")
            out_dir = ws / "recursive_outputs"
            out_dir.mkdir()

            responses = [
                "Not JSON at all",
                '{"is_continuation": false, "timestamps": ["00:00:00 - [Talk] ผ่าน"], "chunk_summary": "ok", "updated_summary": "ok", "new_topic_title": "ผ่าน"}'
            ]
            def fake_call_local(*args, **kwargs):
                return responses.pop(0)

            with patch.object(pcl, "call_local", side_effect=fake_call_local), \
                 patch("process.runners.recursive.time.sleep", return_value=None), \
                 patch.object(pcl, "finalize_and_assemble_timestamps", return_value=(ws / "anibon_timestamps.md", [])):
                pcl.run_recursive_mode(
                    workspace=ws,
                    chunk_files=[chunks_dir / "chunk_00.txt"],
                    endpoint="http://localhost:1234/v1/chat/completions",
                    model="test-model",
                    lang="th",
                    max_tokens=500,
                    temperature=0.2,
                    signals_map={},
                    mappings=[],
                    no_resume=True,
                    max_chunks=1,
                    no_summarizer_pass=True,
                    block_size=40,
                )

            self.assertTrue((out_dir / "chunk_00.json").exists(), "Chunk 00 must be retried and saved on invalid JSON")

    def test_update_topic_flow_unfreezes_title_on_mid_chunk_shift_and_chains_summary(self):
        from process.runners.recursive import _update_topic_flow
        chunk = {"start_sec": 300, "end_sec": 600}
        all_ts = ["00:00:00 - [WatchParty] เปิดสตรีม"]
        # Model sets is_continuation=True (mid-chunk shift) but provides new_topic_title
        res1 = {
            "is_continuation": True,
            "timestamps": ["00:06:00 - [WatchParty] ส่องฉลอง 7.5 ปี Arknights"],
            "chunk_summary": "เริ่มดู PV Arknights 7.5 ปี",
            "updated_summary": "เปลี่ยนจากคุยทั่วไปมาดู PV Arknights 7.5 ปี",
            "new_topic_title": "ส่องอัปเดต 7.5 ปี Arknights",
        }
        _, _, title1, sum1 = _update_topic_flow(res1, chunk, all_ts, "เปิดสตรีมดูอนิเมะ", "ทักทายผู้ชมช่วงเปิดไลฟ์")
        self.assertEqual(title1, "ส่องอัปเดต 7.5 ปี Arknights")
        self.assertIn("ทักทายผู้ชมช่วงเปิดไลฟ์ -> เปลี่ยนจากคุยทั่วไปมาดู PV Arknights 7.5 ปี", sum1)

        # String literal "null" in new_topic_title must NOT overwrite current_topic_title
        res2 = {
            "is_continuation": True,
            "timestamps": [],
            "chunk_summary": "วิเคราะห์สกิลตัวละครใหม่ต่อ",
            "updated_summary": "วิเคราะห์สกิลตัวละครใหม่ใน Arknights",
            "new_topic_title": "null",
        }
        _, _, title2, sum2 = _update_topic_flow(res2, chunk, all_ts, title1, sum1)
        self.assertEqual(title2, "ส่องอัปเดต 7.5 ปี Arknights")
        self.assertEqual(len(sum2.split(" -> ")), 3)


if __name__ == "__main__":
    unittest.main()
