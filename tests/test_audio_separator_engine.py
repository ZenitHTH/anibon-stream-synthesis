"""Unit tests for audio_separator_engine following Clean Code standards."""
from __future__ import annotations

import base64
import io
import json
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
    _decode_and_save_stems,
    calculate_audio_duration,
    convert_audio_to_16k_mono,
    ensure_44k_stereo_wav,
    recover_speech_from_mixed_audio,
    run_stem_separation,
    run_whisper_transcription,
    separate_via_audiocpp_api,
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
    def test_ensure_44k_stereo_wav_invokes_ffmpeg(self, mock_run: MagicMock) -> None:
        src = Path("/tmp/in_48k.wav")
        dst = Path("/tmp/out_44k.wav")
        res = ensure_44k_stereo_wav(src, dst)
        self.assertEqual(res, dst)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-ar", args)
        self.assertIn("44100", args)
        self.assertIn("-ac", args)
        self.assertIn("2", args)

    def test_decode_and_save_stems(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            sample_data = base64.b64encode(b"RIFFdummydata").decode("utf-8")
            outputs = [
                {"id": "vocals", "audio": sample_data},
                {"id": "other", "audio": sample_data},
            ]
            voc, inst = _decode_and_save_stems(outputs, out_dir)
            self.assertTrue(voc.exists())
            self.assertTrue(inst.exists())
            self.assertEqual(voc.read_bytes(), b"RIFFdummydata")

    @patch("urllib.request.urlopen")
    @patch("process.audio_separator_engine.ensure_44k_stereo_wav")
    def test_separate_via_audiocpp_api(self, mock_resample: MagicMock, mock_urlopen: MagicMock) -> None:
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            in_file = out_dir / "in.wav"
            in_file.write_bytes(b"dummy")

            # Mock 44k resample file write
            resampled = out_dir / "input_44k.wav"
            resampled.write_bytes(b"dummy44k")

            mock_resp = MagicMock()
            payload = {
                "named_audio_outputs": [
                    {"id": "vocals", "audio": base64.b64encode(b"voc").decode("utf-8")},
                    {"id": "other", "audio": base64.b64encode(b"inst").decode("utf-8")},
                ]
            }
            mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            voc, inst = separate_via_audiocpp_api(in_file, out_dir)
            self.assertEqual(voc.name, "vocals.wav")
            self.assertEqual(inst.name, "other.wav")

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
