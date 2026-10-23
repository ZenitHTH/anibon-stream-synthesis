import json
import tempfile
import unittest
from pathlib import Path
from download.transcript_source import detect_transcript_source, is_youtube_auto_transcript


class TestTranscriptSource(unittest.TestCase):
    def test_detect_youtube_auto_transcript_by_json3(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "raw_transcript.th.json3").write_text("{}", encoding="utf-8")
            self.assertEqual(detect_transcript_source(tmp_path), "youtube-auto")
            self.assertTrue(is_youtube_auto_transcript(tmp_path))

    def test_detect_youtube_auto_transcript_by_wiremagic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "raw_transcript.json").write_text('{"wireMagic": "pb3", "events": []}', encoding="utf-8")
            self.assertEqual(detect_transcript_source(tmp_path), "youtube-auto")
            self.assertTrue(is_youtube_auto_transcript(tmp_path))

    def test_detect_whisper_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "whisper_output.json").write_text('[]', encoding="utf-8")
            self.assertEqual(detect_transcript_source(tmp_path), "whisper")
            self.assertFalse(is_youtube_auto_transcript(tmp_path))

    def test_detect_whisper_by_audio_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "audio_recovered.json").write_text('[]', encoding="utf-8")
            self.assertEqual(detect_transcript_source(tmp_path), "whisper")
            self.assertFalse(is_youtube_auto_transcript(tmp_path))

    def test_detect_source_by_info_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "info.json").write_text(json.dumps({"transcript_source": "whisper"}), encoding="utf-8")
            self.assertEqual(detect_transcript_source(tmp_path), "whisper")
            self.assertFalse(is_youtube_auto_transcript(tmp_path))


if __name__ == "__main__":
    unittest.main()
