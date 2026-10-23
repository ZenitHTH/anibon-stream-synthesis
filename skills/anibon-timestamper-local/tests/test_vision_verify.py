import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from process.vision_verify import (
    is_ambiguous,
    stamp_seconds,
    parse_verify_response,
    build_verify_prompt,
    extract_frame,
    verify_ambiguous_stamps,
    apply_vision_verify,
)

ORIG = "03:52:49 - [Gameplay] เซเวนกับไหมกีนิด"


class TestVisionVerify(unittest.TestCase):
    def test_is_ambiguous_cases(self):
        self.assertTrue(is_ambiguous("03:51:33 - [Donation] ขอบคุณคุณนี้น่ะ"))
        self.assertTrue(is_ambiguous("03:28:41 - [Talk] Zelda"))
        self.assertTrue(is_ambiguous("04:00:04 - [Gameplay] ปู่บอทสู้มอนสเตอร์ในเกมแล้วไม่ไหวจนเกือบตาย"))
        self.assertTrue(is_ambiguous("00:01:00 - [Talk] [?] มาแล้วทุกคน"))
        self.assertFalse(is_ambiguous("02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ"))

    def test_stamp_seconds(self):
        self.assertEqual(stamp_seconds("01:02:03 - [Talk] x"), 3723)
        self.assertEqual(stamp_seconds("00:00:15 - [Greeting] เริ่มสตรีม"), 15)

    def test_parse_accepts_valid(self):
        raw = '{"corrected": "03:52:49 - [Gameplay] วิเคราะห์ฮีโร่ Seven และ McGinnis ใน Deadlock", "confidence": 0.8}'
        result = parse_verify_response(raw, ORIG)
        self.assertEqual(result, "03:52:49 - [Gameplay] วิเคราะห์ฮีโร่ Seven และ McGinnis ใน Deadlock")

    def test_parse_rejects_non_json(self):
        self.assertEqual(parse_verify_response("I think this is Deadlock", ORIG), ORIG)

    def test_parse_rejects_changed_time_or_tag(self):
        self.assertEqual(parse_verify_response('{"corrected": "03:53:00 - [Gameplay] x y z", "confidence": 0.9}', ORIG), ORIG)
        self.assertEqual(parse_verify_response('{"corrected": "03:52:49 - [Talk] x y z", "confidence": 0.9}', ORIG), ORIG)

    def test_parse_rejects_low_confidence(self):
        self.assertEqual(parse_verify_response('{"corrected": "03:52:49 - [Gameplay] Seven", "confidence": 0.3}', ORIG), ORIG)

    def test_build_verify_prompt(self):
        prompt = build_verify_prompt(ORIG, "context transcript")
        self.assertIn("03:52:49", prompt)
        self.assertTrue("Seven" not in prompt or "McGinnis" not in prompt)
        self.assertIn("JSON", prompt)

    def test_verify_corrects_only_ambiguous(self):
        calls = []

        def fake_call(e, m, p, img, **k):
            calls.append(img)
            return '{"corrected": "03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock", "confidence": 0.9}'

        def fake_frame(v, s, o):
            o.write_bytes(b"image")
            return o

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "v.mp4"
            video.write_bytes(b"video")
            stamps = [
                "02:15:28 - [News] วิเคราะห์กรณี Ironmouse กับประเด็นการใช้ Generative AI ในงานศิลปะ",
                ORIG,
            ]
            out = verify_ambiguous_stamps(
                stamps,
                tmp_path,
                video,
                "http://mock",
                "mock-model",
                call_fn=fake_call,
                frame_fn=fake_frame,
            )
            self.assertEqual(out[0], stamps[0])
            self.assertIn("McGinnis", out[1])
            self.assertEqual(len(calls), 1)

    def test_verify_skips_without_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = verify_ambiguous_stamps(
                [ORIG],
                tmp_path,
                tmp_path / "missing.mp4",
                "http://mock",
                "mock-model",
            )
            self.assertEqual(out, [ORIG])

    def test_verify_keeps_original_on_exception(self):
        def boom(*a, **k):
            raise OSError("down")

        def fake_frame(v, s, o):
            o.write_bytes(b"image")
            return o

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "v.mp4"
            video.write_bytes(b"video")
            out = verify_ambiguous_stamps(
                [ORIG],
                tmp_path,
                video,
                "http://mock",
                "mock-model",
                call_fn=boom,
                frame_fn=fake_frame,
            )
            self.assertEqual(out, [ORIG])

    def test_verify_uses_cache(self):
        calls = []

        def fake_call(e, m, p, img, **k):
            calls.append(img)
            return '{"corrected": "03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock", "confidence": 0.9}'

        def fake_frame(v, s, o):
            o.write_bytes(b"image")
            return o

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "v.mp4"
            video.write_bytes(b"video")
            stamps = [ORIG]

            # First run
            out1 = verify_ambiguous_stamps(
                stamps,
                tmp_path,
                video,
                "http://mock",
                "mock-model",
                call_fn=fake_call,
                frame_fn=fake_frame,
            )
            self.assertEqual(len(calls), 1)
            self.assertIn("Seven", out1[0])

            # Second run should read cache and not call model again
            def boom(*a, **k):
                raise RuntimeError("Should not be called")

            out2 = verify_ambiguous_stamps(
                stamps,
                tmp_path,
                video,
                "http://mock",
                "mock-model",
                call_fn=boom,
                frame_fn=fake_frame,
            )
            self.assertEqual(out2, out1)
            self.assertEqual(len(calls), 1)

    def test_apply_vision_verify_noop_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = argparse.Namespace(vision_verify=False)
            stamps = [ORIG]
            with patch("process.vision_verify.verify_ambiguous_stamps") as mock_fn:
                out = apply_vision_verify(stamps, tmp_path, args, "model")
                self.assertEqual(out, stamps)
                mock_fn.assert_not_called()

    def test_apply_vision_verify_calls_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "video_360p.mp4"
            video.write_bytes(b"dummy")
            args = argparse.Namespace(
                vision_verify=True,
                video_file=None,
                vision_model="custom-vision",
                endpoint="http://127.0.0.1:1234/v1/chat/completions",
            )
            stamps = [ORIG]
            with patch("process.vision_verify.verify_ambiguous_stamps") as mock_fn:
                mock_fn.return_value = ["03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock"]
                out = apply_vision_verify(stamps, tmp_path, args, "default-model")
                self.assertEqual(out, ["03:52:49 - [Gameplay] Seven และ McGinnis ใน Deadlock"])
                mock_fn.assert_called_once()
                call_args = mock_fn.call_args
                self.assertEqual(call_args[0][0], stamps)
                self.assertEqual(call_args[0][1], tmp_path)
                self.assertEqual(call_args[0][2], video)
                self.assertEqual(call_args[0][3], "http://127.0.0.1:1234/v1/chat/completions")
                self.assertEqual(call_args[0][4], "custom-vision")
                # Verify all_timestamps.txt was updated
                saved = (tmp_path / "all_timestamps.txt").read_text(encoding="utf-8")
                self.assertIn("Seven และ McGinnis", saved)


if __name__ == "__main__":
    unittest.main()
