from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_LIB = str(Path(__file__).resolve().parents[3] / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from video.audio_envelope import detect_audio_cue_events
from video.audio_webcam_cues import select_audio_webcam_cues
from video.chunk_peak_select import PeakSearchInput, detect_chunk_reaction_peaks
from video.motion_types import WindowBounds


class TestAudioWebcamCues(unittest.TestCase):
    def test_detect_audio_cue_events_captures_loud_peak_silence_drop_and_sustained_silence(self) -> None:
        raw_bins = (
            [(100 + i, 0.08) for i in range(6)]
            + [(106 + i, 0.002) for i in range(8)]
            + [(114, 0.45), (115, 0.08)]
        )
        events = detect_audio_cue_events(raw_bins, bin_sec=1.0, z_thresh=2.5)
        kinds = {kind for _, kind, _ in events}
        self.assertIn("loud_peak", kinds)
        self.assertIn("silence_drop", kinds)
        self.assertIn("sustained_silence", kinds)

    def test_select_audio_webcam_cues_spaces_results_by_15s(self) -> None:
        raw_bins = [(10, 0.45), (15, 0.42), (35, 0.002)] + [(36 + i, 0.002) for i in range(6)]
        with patch("video.audio_webcam_cues.extract_raw_rms_bins", return_value=raw_bins):
            cues = select_audio_webcam_cues(Path("dummy.m4a"), WindowBounds(0, 60), max_cues=4)
        secs = [c.sec for c in cues]
        self.assertIn(10, secs)
        self.assertNotIn(15, secs)
        self.assertTrue(any(c.event_type in ("silence_drop", "sustained_silence") for c in cues))

    def test_detect_chunk_reaction_peaks_promotes_on_silence_drop(self) -> None:
        items = [{"start": 100, "text": "hello"}, {"start": 130, "text": ""}]
        raw_bins = [(100 + i, 0.08) for i in range(5)] + [(105 + i, 0.002) for i in range(8)]
        with patch("video.chunk_peak_select.extract_raw_rms_bins", return_value=raw_bins):
            peaks, _, promote = detect_chunk_reaction_peaks(PeakSearchInput(Path("."), items, "audio.m4a"))
        self.assertTrue(promote)
        self.assertTrue(len(peaks) >= 1)


if __name__ == "__main__":
    unittest.main()
