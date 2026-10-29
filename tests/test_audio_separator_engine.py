"""Unit tests for audio_separator_engine following Clean Code standards."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

_LIB = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.audio_separator_engine import (
    SeparationResult,
    calculate_audio_duration,
    convert_audio_to_16k_mono,
    recover_speech_from_mixed_audio,
    run_whisper_transcription,
)


class TestAudioSeparatorEngine(unittest.TestCase):
    @patch("subprocess.run")
    def test_convert_audio_to_16k_mono_invokes_ffmpeg(self, mock_run: MagicMock) -> None:
        src = Path("/tmp/in.wav")
        dst = Path("/tmp/out.wav")
        res = convert_audio_to_16k_mono(src, dst)
        self.assertEqual(res, dst)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-ar", args)
        self.assertIn("16000", args)

    @patch("subprocess.run")
    def test_run_whisper_transcription_cleans_stdout(self, mock_run: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout = "main: init\nสตรีมเมอร์ปู่โบ๊ตกำลังพูด\nsystem_info: ok\nเล่นเกมมายคราฟ\n"
        mock_run.return_value = mock_proc

        text = run_whisper_transcription(
            Path("/tmp/audio.wav"),
            cli_path="/bin/echo",
            model_path="/tmp/model.bin",
        )
        self.assertIn("สตรีมเมอร์ปู่โบ๊ตกำลังพูด", text)
        self.assertIn("เล่นเกมมายคราฟ", text)
        self.assertNotIn("main: init", text)

    @patch("process.audio_separator_engine.calculate_audio_duration", return_value=30.0)
    @patch("process.audio_separator_engine.run_whisper_transcription", return_value="ข้อความถอดเสียงถูกต้อง")
    @patch("process.audio_separator_engine.convert_audio_to_16k_mono")
    @patch("process.audio_separator_engine.run_stem_separation")
    def test_recover_speech_orchestration(
        self,
        mock_sep: MagicMock,
        mock_conv: MagicMock,
        mock_whisper: MagicMock,
        mock_dur: MagicMock,
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            voc = out_dir / "test_(Vocals).wav"
            inst = out_dir / "test_(Instrumental).wav"
            mock_sep.return_value = (voc, inst)

            result = recover_speech_from_mixed_audio(Path("/tmp/test.wav"), out_dir)
            self.assertIsInstance(result, SeparationResult)
            self.assertEqual(result.vocals_path, voc)
            self.assertEqual(result.transcript_text, "ข้อความถอดเสียงถูกต้อง")
            self.assertEqual(result.duration_sec, 30.0)


if __name__ == "__main__":
    unittest.main()
