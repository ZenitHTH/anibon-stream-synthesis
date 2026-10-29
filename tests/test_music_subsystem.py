# tests/test_music_subsystem.py
from __future__ import annotations

import unittest
import numpy as np
from process.music.acoustic import analyze_acoustic_features, is_music_spectral
from process.music.lore import fetch_song_lore_summary
from process.music.sensor import has_music_chat_surge, scan_chat_music_density
from process.music.subtractor import subtract_reference_signal

class TestMusicSubsystem(unittest.TestCase):
    def test_spectral_flatness_pure_sine(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        feats = analyze_acoustic_features(tone, sr)
        self.assertTrue(is_music_spectral(feats.flatness))

    def test_lore_lookup_mairom(self):
        brief = fetch_song_lore_summary("พี่ไม่ได้ดักเจ้า")
        self.assertIn("ไม้ร่ม", brief.artist)

    def test_chat_music_density(self):
        chat = [
            "สวัสดีครับ",
            "เพลงอะไรเหรอครับเพราะมาก",
            "พี่ไม่ได้ดักเจ้าหน่อยงับ",
            "55555555",
        ]
        self.assertGreater(scan_chat_music_density(chat), 0.25)
        self.assertTrue(has_music_chat_surge(chat, threshold=0.20))

    def test_subtraction_with_negative_offset(self):
        sr = 16000
        ref = np.sin(2 * np.pi * 300 * np.linspace(0, 2.0, 2 * sr, endpoint=False)).astype(np.float32)
        # mixed starts in middle of ref (negative lag) + added speech tone
        mixed_ref = ref[sr // 2 : sr // 2 + sr]
        speech = 0.5 * np.cos(2 * np.pi * 100 * np.linspace(0, 1.0, sr, endpoint=False)).astype(np.float32)
        mixed = mixed_ref + speech
        cleaned = subtract_reference_signal(mixed, ref)
        self.assertEqual(len(cleaned), len(mixed))
        # After subtraction, energy of reference is significantly reduced
        residue_err = float(np.mean((cleaned - speech) ** 2))
        self.assertLess(residue_err, 0.05)


if __name__ == "__main__":
    unittest.main()
