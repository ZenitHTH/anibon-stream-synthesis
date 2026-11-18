"""Tests for pure-stdlib PCM s16le audio RMS envelope and silence-drop detection."""
from __future__ import annotations

import math
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from video.audio_envelope import (
    AudioBurstMetrics,
    compute_audio_envelope_from_pcm,
    extract_audio_burst_metrics,
)
from video.motion_types import WindowBounds


def _tone_pcm(amp: int, duration_sec: float, sample_rate: int = 8000) -> bytes:
    n = int(round(duration_sec * sample_rate))
    samples = [int(amp * math.sin(2.0 * math.pi * 220.0 * i / sample_rate)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


class TestAudioEnvelope(unittest.TestCase):
    def test_quiet_baseline_with_shout_triggers_rms_z(self) -> None:
        pcm = _tone_pcm(150, 4.0) + _tone_pcm(14000, 1.0) + _tone_pcm(150, 3.0)
        res = compute_audio_envelope_from_pcm(pcm, sample_rate=8000, bin_sec=0.5)
        self.assertGreaterEqual(res.rms_z_max, 2.5)
        self.assertTrue(res.has_audio_trigger)
        self.assertIsNotNone(res.shout_sec)
        self.assertAlmostEqual(res.shout_sec, 4.0, delta=0.5)

    def test_steady_speech_suppresses_audio_trigger(self) -> None:
        bins = [_tone_pcm(3000 + (i % 3) * 150, 0.5) for i in range(16)]
        res = compute_audio_envelope_from_pcm(b"".join(bins), sample_rate=8000, bin_sec=0.5)
        self.assertFalse(res.has_audio_trigger)
        self.assertIsNone(res.shout_sec)
        self.assertIsNone(res.silence_drop_sec)

    def test_sudden_silence_drop_after_speech_captured(self) -> None:
        pcm = _tone_pcm(4000, 4.0) + _tone_pcm(40, 3.0)
        res = compute_audio_envelope_from_pcm(pcm, sample_rate=8000, bin_sec=0.5)
        self.assertIsNotNone(res.silence_drop_sec)
        self.assertAlmostEqual(res.silence_drop_sec, 4.0, delta=0.6)
        self.assertTrue(res.has_audio_trigger)

    def test_extract_audio_burst_metrics_handles_ffmpeg_failure_gracefully(self) -> None:
        bounds = WindowBounds(start_sec=0.0, end_sec=10.0)
        with patch("video.audio_envelope.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = b""
            res = extract_audio_burst_metrics(Path("missing.mp4"), bounds, z_thresh=2.5)
        self.assertEqual(res, AudioBurstMetrics(0.0, None, None, False))


if __name__ == "__main__":
    unittest.main()
