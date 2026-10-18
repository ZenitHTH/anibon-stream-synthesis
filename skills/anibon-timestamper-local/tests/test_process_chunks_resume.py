import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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


if __name__ == "__main__":
    unittest.main()
