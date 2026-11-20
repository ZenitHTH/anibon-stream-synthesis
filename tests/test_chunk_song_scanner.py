from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_LIB = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.music.chunk_scanner import (
    SongScanConfig,
    SongScanRequest,
    SongTriggerInput,
    scan_and_recover_chunk_song,
    should_scan_chunk_for_song,
)
from process.music.sensor import TrackMetadata


class TestChunkSongScanner(unittest.TestCase):
    def test_should_scan_triggers_on_anchor_or_chat_surge(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 450, "items": []}
        self.assertTrue(should_scan_chunk_for_song(SongTriggerInput(chunk, (), [{"offset_ms": 350000}])))
        self.assertFalse(should_scan_chunk_for_song(SongTriggerInput(chunk, ("สวัสดี", "เล่นเกมต่อ"), ())))

    def test_scan_runs_shazam_then_audiocpp_then_whisper_and_offsets_timestamps(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        segs = [{"offsets": {"from": 4500, "to": 7000}, "text": "อันนี้เพลงโปรดเลย"}]
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            vocals = work_dir / "vocals.wav"
            vocals.write_bytes(b"RIFF")
            req = SongScanRequest(chunk, Path("audio.m4a"), work_dir)
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Bury the Light", "Casey Edwards"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", return_value=(vocals, work_dir / "inst.wav")) as mock_sep, \
                 patch("process.music.chunk_scanner.convert_audio_to_16k_mono"), \
                 patch("process.music.chunk_scanner.find_whisper_cli", return_value="/usr/bin/whisper-cli"), \
                 patch("process.music.chunk_scanner.find_whisper_model", return_value="/models/ggml.bin"), \
                 patch("process.music.chunk_scanner.run_whisper_slice", return_value=("อันนี้เพลงโปรดเลย", segs)):
                res = scan_and_recover_chunk_song(req, SongScanConfig())
        self.assertIsNotNone(res)
        mock_sep.assert_called_once()
        self.assertEqual(res.title, "Bury the Light")
        self.assertEqual(res.recovered_items[0]["timestamp"], "00:05:04")
        self.assertEqual(res.recovered_items[0]["text"], "อันนี้เพลงโปรดเลย")

    def test_scan_returns_none_when_shazam_times_out(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        async def slow_shazam(_path: str):
            await asyncio.sleep(0.5)
            return TrackMetadata("Slow", "Artist")
        with tempfile.TemporaryDirectory() as tmp:
            req = SongScanRequest(chunk, Path("audio.m4a"), Path(tmp))
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=slow_shazam):
                res = scan_and_recover_chunk_song(req, SongScanConfig(shazam_timeout_sec=0.05))
        self.assertIsNone(res)

    def test_scan_degrades_gracefully_when_audiocpp_or_whisper_unavailable(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        with tempfile.TemporaryDirectory() as tmp:
            req = SongScanRequest(chunk, Path("audio.m4a"), Path(tmp))
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Ao no Sumika", "Tatsuya Kitani"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", side_effect=RuntimeError("connection refused")):
                res = scan_and_recover_chunk_song(req, SongScanConfig())
        self.assertIsNotNone(res)
        self.assertEqual(res.title, "Ao no Sumika")
        self.assertEqual(res.recovered_items, ())

    def test_scan_handles_no_shazam_match_and_whisper_errors(self) -> None:
        chunk = {"start_sec": 300, "end_sec": 360, "items": []}
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            vocals = work_dir / "vocals.wav"
            vocals.write_bytes(b"RIFF")
            req = SongScanRequest(chunk, Path("audio.m4a"), work_dir)
            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=None)):
                self.assertIsNone(scan_and_recover_chunk_song(req, SongScanConfig()))

            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Song", "Art"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", return_value=(vocals, work_dir / "inst.wav")), \
                 patch("process.music.chunk_scanner.find_whisper_cli", return_value=None):
                res_no_bin = scan_and_recover_chunk_song(req, SongScanConfig())
            self.assertIsNotNone(res_no_bin)
            self.assertEqual(res_no_bin.recovered_items, ())

            with patch("process.music.chunk_scanner._slice_wav_range", return_value=True), \
                 patch("process.music.chunk_scanner.recognize_shazam_slice", new=AsyncMock(return_value=TrackMetadata("Song", "Art"))), \
                 patch("process.music.chunk_scanner.separate_via_audiocpp_api", return_value=(vocals, work_dir / "inst.wav")), \
                 patch("process.music.chunk_scanner.find_whisper_cli", return_value="/bin/w"), \
                 patch("process.music.chunk_scanner.find_whisper_model", return_value="/m.bin"), \
                 patch("process.music.chunk_scanner.convert_audio_to_16k_mono"), \
                 patch("process.music.chunk_scanner.run_whisper_slice", side_effect=RuntimeError("whisper crash")):
                res_err = scan_and_recover_chunk_song(req, SongScanConfig())
            self.assertIsNotNone(res_err)
            self.assertEqual(res_err.recovered_items, ())

    def test_should_scan_triggers_on_spectral_music_probe(self) -> None:
        chunk = {"start_sec": 0, "end_sec": 60, "items": []}
        with patch("process.music.chunk_scanner._probe_spectral_music", return_value=True):
            self.assertTrue(should_scan_chunk_for_song(SongTriggerInput(chunk, (), (), Path("a.m4a"))))


if __name__ == "__main__":
    unittest.main()
