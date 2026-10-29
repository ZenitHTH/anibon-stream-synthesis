# tests/test_whisper_repetition_watchdog.py
from __future__ import annotations

import unittest
from process.whisper_dispatcher import detect_repetition_anomaly, scrub_repetition_loop

class TestWhisperRepetitionWatchdog(unittest.TestCase):
    def test_single_token_loop(self):
        text = "คุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณ"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_multi_token_loop(self):
        text = "เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_normal_speech(self):
        text = "วันนี้เรามาสร้างบ้านกลางลาวาในมายคราฟกันนะครับทุกคน"
        self.assertFalse(detect_repetition_anomaly(text))

    def test_whisper_hum_loop(self):
        text = "มมมมมมมมมมมมมมมมมมมมมมมมม"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_whisper_repeated_interjection(self):
        text = "เฮ้ย เฮ้ย เฮ้ย เฮ้ย เฮ้ย เฮ้ย เฮ้ย"
        self.assertTrue(detect_repetition_anomaly(text))

    def test_normal_speech_with_short_repetition(self):
        text = "เดี๋ยวเราไปดูบ้านใหม่กันนะครับทุกคน สวยมากๆๆ และมีของเยอะมาก"
        self.assertFalse(detect_repetition_anomaly(text))

    def test_scrub_repetition_loop(self):
        loop_single = "คุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณคุณ"
        self.assertEqual(scrub_repetition_loop(loop_single), "")

        loop_phrase = "เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย เกิดไปโร่ของเมืองไทย"
        self.assertEqual(scrub_repetition_loop(loop_phrase), "เกิดไปโร่ของเมืองไทย")

        loop_hum = "มมมมมมมมมมมมมมมมมมมมมมมมม"
        self.assertEqual(scrub_repetition_loop(loop_hum), "")


if __name__ == "__main__":
    unittest.main()
