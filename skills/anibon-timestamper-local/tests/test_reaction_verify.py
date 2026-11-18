"""Unit tests for Task 4 & Task 5: reaction prompt, co-triggers, orchestration, and sync."""
from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video.audio_envelope import AudioBurstMetrics
from video.motion_types import FaceBox, FaceMotionSample, KeyframePick, LayoutSegment, MotionRegime


def _sample_regime(regime: str = "stunned_freeze") -> MotionRegime:
    kfs = (
        KeyframePick("pre_onset_baseline", 2, 1.0, 101.0, "00:01:41", 0.01, 0.01, 0.2),
        KeyframePick("onset_inflection", 10, 5.0, 105.0, "00:01:45", 0.08, 0.09, 3.8),
        KeyframePick("peak_delta", 12, 6.0, 106.0, "00:01:46", 0.14, 0.16, 5.4),
        KeyframePick("post_peak_state", 18, 9.0, 109.0, "00:01:49", 0.01, 0.06, 0.1),
    )
    return MotionRegime(
        regime=regime,
        trigger_vlm=True,
        confidence=0.88,
        onset_rel_sec=5.0,
        onset_abs_sec=105.0,
        onset_ts="00:01:45",
        peak_rel_sec=6.0,
        peak_abs_sec=106.0,
        peak_ts="00:01:46",
        webcam_z_max=5.4,
        w_pose_shift=0.16,
        freeze_duration_sec=3.0,
        freeze_drop_ratio=4.2,
        burst_width_sec=1.5,
        keyframes=kfs,
        scores={regime: 0.88},
        features={"z_max": 5.4},
    )


class TestReactionVerifyTask4(unittest.TestCase):
    def test_co_trigger_signals_has_any(self):
        from process.reaction_verify import CoTriggerSignals

        quiet = CoTriggerSignals(0.0, "QUIET", False, AudioBurstMetrics(1.1, None, None, False))
        self.assertFalse(quiet.has_any)
        self.assertTrue(CoTriggerSignals(2.0, "QUIET", False, None).has_any)
        self.assertTrue(CoTriggerSignals(0.0, "MEME_PULSE", True, None).has_any)
        self.assertFalse(CoTriggerSignals(0.0, "MEME_PULSE", False, None).has_any)
        self.assertTrue(
            CoTriggerSignals(0.0, "QUIET", False, AudioBurstMetrics(3.1, 4.0, None, True)).has_any
        )

    def test_needs_reaction_verify_protects_quiet_news_and_allows_co_triggers(self):
        from process.reaction_verify import CoTriggerSignals, needs_reaction_verify

        news = "00:10:00 - [News] รายงานข่าวอัปเดตเกมใหม่ประจำสัปดาห์"
        self.assertFalse(needs_reaction_verify(news, "วันนี้อากาศดีครับ รายงานข่าวต่อ", None))
        self.assertTrue(needs_reaction_verify("00:10:00 - [Reaction] เหวอเมื่อเห็นฉากจบ"))

        meme_trig = CoTriggerSignals(0.0, "MEME_PULSE", True, None)
        self.assertTrue(needs_reaction_verify("00:12:00 - [Talk] แซวสีตัวละครเบาๆ", "", meme_trig))

        audio_trig = CoTriggerSignals(0.0, "QUIET", False, AudioBurstMetrics(3.4, 2.0, None, True))
        self.assertTrue(needs_reaction_verify("00:15:00 - [Talk] บ่นบอสฮีลเลือดเต็ม", "", audio_trig))
        self.assertTrue(needs_reaction_verify(news, "เห้ย เชี่ย อะไรวะเนี่ย", None))

    def test_build_face_reaction_prompt_includes_telemetry_and_pose_calibration(self):
        from process.reaction_verify import CoTriggerSignals, PromptContext, build_face_reaction_prompt

        regime = _sample_regime("posture_act")
        trig = CoTriggerSignals(2.0, "MEME_PULSE", True, AudioBurstMetrics(3.6, 5.0, None, True))
        prompt = build_face_reaction_prompt(
            "00:01:55 - [Reaction] ตกใจหนักมาก",
            regime,
            PromptContext(triggers=trig, transcript_ctx="เห้ย ลงไปนอนเลย"),
        )
        for token in (
            "pre_onset_baseline",
            "00:01:41",
            "regime=posture_act",
            "freeze_duration_sec=3.00",
            "freeze_drop_ratio=4.20",
            "webcam_z_max=5.40",
            "w_pose_shift=0.160",
            "burst_width_sec=1.50",
            "audio_rms_z=3.60",
            "shock",
            "joy_flex",
            "stunned_freeze",
            "angry",
            "playful_tease",
            "physical_act",
            "lean_into_cam",
            "duck_under_desk",
            "slump_on_desk",
            "show_prop_to_cam",
            "praying_bow",
            "lie_on_bed",
            "empty_chair_afk",
        ):
            self.assertIn(token, prompt)

    def test_parse_snapped_response_guards_milestones_empty_chair_and_drift(self):
        from process.reaction_verify import (
            PROTECTED_MILESTONE_TAGS,
            ParseConstraints,
            parse_snapped_response,
        )

        self.assertEqual(
            set(PROTECTED_MILESTONE_TAGS),
            {"Gacha", "Victory", "Boss", "Ending", "Donation"},
        )
        bounds = (90, 140)
        raw_gacha = json.dumps({
            "snapped_ts": "00:01:45",
            "emotion_class": "joy_flex",
            "face_cue": "claps hands",
            "tag": "Reaction",
            "description": "ดีใจออกตัวระดับห้าดาว",
            "confidence": 0.9,
        })
        res_gacha = parse_snapped_response(
            raw_gacha, "00:02:00 - [Gacha] เปิดกาชาลุ้นตัวใหม่", ParseConstraints(bounds, 0.6, 0.14)
        )
        self.assertTrue(res_gacha.accepted)
        self.assertIn("[Gacha]", res_gacha.updated)
        self.assertEqual(res_gacha.snapped_sec, 105)

        for rej_cls in ("calm_talking", "empty_chair_afk"):
            raw_rej = json.dumps({
                "snapped_ts": "00:01:45",
                "emotion_class": rej_cls,
                "face_cue": "none",
                "tag": "Reaction",
                "description": "คุยปกติ",
                "confidence": 0.95,
            })
            res_rej = parse_snapped_response(
                raw_rej, "00:02:00 - [Reaction] อึ้ง", ParseConstraints(bounds)
            )
            self.assertFalse(res_rej.accepted)
            self.assertEqual(res_rej.updated, "00:02:00 - [Reaction] อึ้ง")

        raw_bed = json.dumps({
            "snapped_ts": "00:01:49",
            "emotion_class": "physical_act",
            "pose_cue": "lie_on_bed",
            "face_cue": "ลุกไปนอนแผ่บนเตียงข้างหลัง",
            "tag": "Reaction",
            "description": "ลุกไปนอนแผ่บนเตียงหลังเก้าอี้ขำมุกแชท",
            "confidence": 0.85,
        })
        res_bed = parse_snapped_response(
            raw_bed, "00:02:00 - [Reaction] ขำหนัก", ParseConstraints(bounds)
        )
        self.assertTrue(res_bed.accepted)
        self.assertEqual(res_bed.snapped_sec, 109)

        raw_drift = json.dumps({
            "snapped_ts": "00:05:00",
            "emotion_class": "shock",
            "face_cue": "gasp",
            "tag": "Reaction",
            "description": "หลุดกรอบเวลา",
            "confidence": 0.95,
        })
        res_drift = parse_snapped_response(
            raw_drift, "00:02:00 - [Reaction] ตกใจ", ParseConstraints(bounds)
        )
        self.assertFalse(res_drift.accepted)

    def test_resolve_monotonic_snap_prevents_45s_collisions(self):
        from process.reaction_verify import ReactionVerifyResult, resolve_monotonic_snap

        r1 = ReactionVerifyResult(
            "00:01:00 - [Talk] คุยเปิดประเด็น",
            "00:01:00 - [Talk] คุยเปิดประเด็น",
            60, "calm_talking", "", 0.01, 0.0, False,
        )
        r2 = ReactionVerifyResult(
            "00:02:00 - [Reaction] ตกใจมาก",
            "00:01:20 - [Reaction] สะดุ้งตกใจเสียงดัง",
            80, "shock", "recoil", 0.12, 0.9, True,
        )
        r3 = ReactionVerifyResult(
            "00:03:00 - [Reaction] อึ้งค้าง",
            "00:02:45 - [Reaction] ชะงักนิ่งจ้องหน้าจอ",
            165, "stunned_freeze", "freeze", 0.10, 0.85, True,
        )
        resolved = resolve_monotonic_snap([r1, r2, r3], collision_sec=45)
        self.assertEqual(resolved[0], "00:01:00 - [Talk] คุยเปิดประเด็น")
        self.assertEqual(resolved[1], "00:02:00 - [Reaction] ตกใจมาก")
        self.assertEqual(resolved[2], "00:02:45 - [Reaction] ชะงักนิ่งจ้องหน้าจอ")


class TestReactionVerifyTask5(unittest.TestCase):
    def _write_fake_jpeg(self, out_dir: Path, name: str) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / name
        p.write_bytes(b"fakejpg")
        return p

    def test_apply_reaction_verify_noop_and_missing_video(self):
        from process.reaction_verify import apply_reaction_verify

        stamps = ["00:01:00 - [Talk] คุยเปิดไลฟ์"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            self.assertEqual(
                apply_reaction_verify(stamps, ws, argparse.Namespace(reaction_verify=False)),
                stamps,
            )
            self.assertEqual(
                apply_reaction_verify(stamps, ws, argparse.Namespace(reaction_verify=True)),
                stamps,
            )

    def test_verify_drops_calm_news_without_co_trigger_and_bypasses_with_audio_or_meme(self):
        from process.reaction_verify import VerifyOptions, verify_reaction_stamps

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"mp4")
            (ws / "mood_555.json").write_text(
                json.dumps({
                    "chunk_00": {
                        "verdict": "MEME_PULSE",
                        "peak_windows": [{"start": "00:03:00", "end": "00:04:00", "count": 20}],
                    }
                }),
                encoding="utf-8",
            )
            calls = []
            exported_boxes = []
            quiet_layout = LayoutSegment("top-right", FaceBox(0.76, 0.0, 0.24, 0.30, "top-right"), FaceBox(0.83, 0.01, 0.09, 0.19))

            def fake_motion(src, bounds, layout):
                # Flat calm series -> classify_dual_regime returns calm_news (trigger_vlm=False)
                s = [
                    FaceMotionSample(i, i * 0.5, bounds.start_sec + i * 0.5, "00:01:00", 0.005, 0.005, 0.005, 0.005, 0.005, 0.0, 0.005)
                    for i in range(12)
                ]
                return (s, s, ())

            def fake_export(src, spec):
                exported_boxes.append(spec.box)
                jpg = self._write_fake_jpeg(spec.out_dir, f"{spec.prefix}_01.jpg")
                return {"frames": [{"ts": "00:03:20", "path": str(jpg), "b64": "YWJj"}], "strip_path": None}

            def fake_call(ep, mod, content):
                calls.append(content)
                snapped = "00:04:55" if "00:05:00" in content[0]["text"] else "00:03:18"
                return json.dumps({
                    "snapped_ts": snapped,
                    "emotion_class": "playful_tease",
                    "face_cue": "smirk",
                    "tag": "Reaction",
                    "description": "ยิ้มแซวสีชุดตัวละครตามแชท",
                    "confidence": 0.9,
                })

            # 1. Quiet News without co-trigger -> 0 VLM calls
            opts_quiet = VerifyOptions(
                source=vid, endpoint="http://local", model="m",
                call_fn=fake_call, layout_fn=lambda s, b, preferred="auto": quiet_layout,
                motion_fn=fake_motion, export_fn=fake_export,
                audio_fn=lambda s, b: AudioBurstMetrics(0.5, None, None, False),
                context_fn=lambda sec: "วันนี้อากาศดีครับ รายงานข่าวต่อ",
            )
            out1 = verify_reaction_stamps(["00:01:00 - [News] อ่านข่าวประจำวัน"], ws, opts_quiet)
            self.assertEqual(len(calls), 0)
            self.assertEqual(out1, ["00:01:00 - [News] อ่านข่าวประจำวัน"])

            # 2. MEME_PULSE in mood_555.json bypasses calm_news gate using W box
            out2 = verify_reaction_stamps(["00:03:20 - [Talk] แซวสีตัวละคร"], ws, opts_quiet)
            self.assertEqual(len(calls), 1)
            self.assertEqual(exported_boxes[0], quiet_layout.webcam_box)
            self.assertIn("00:03:18 - [Reaction] ยิ้มแซวสีชุดตัวละครตามแชท", out2[0])

            # 3. Audio burst co-trigger also bypasses calm_news gate
            opts_audio = VerifyOptions(
                source=vid, endpoint="http://local", model="m",
                call_fn=fake_call, layout_fn=lambda s, b, preferred="auto": quiet_layout,
                motion_fn=fake_motion, export_fn=fake_export,
                audio_fn=lambda s, b: AudioBurstMetrics(3.4, 5.0, None, True),
                context_fn=lambda sec: "คุยธรรมดา",
            )
            out3 = verify_reaction_stamps(["00:05:00 - [Talk] บ่นบอสฮีลเลือดเต็ม"], ws, opts_audio)
            self.assertEqual(len(calls), 2)
            self.assertIn("[Reaction]", out3[0])

    def test_verify_caches_in_reaction_verify_log_and_syncs_all_timestamps(self):
        from process.reaction_verify import VerifyOptions, apply_reaction_verify, verify_reaction_stamps

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"mp4")
            orig = "00:02:00 - [Reaction] อึ้งค้างไปเลย"
            (ws / "all_timestamps.txt").write_text(orig + "\n", encoding="utf-8")

            calls = []
            layout = LayoutSegment("top-right", FaceBox(0.76, 0.0, 0.24, 0.30, "top-right"), FaceBox(0.83, 0.01, 0.09, 0.19))
            regime = _sample_regime("stunned_freeze")

            def fake_call(ep, mod, content):
                calls.append(1)
                return json.dumps({
                    "snapped_ts": "00:01:45",
                    "emotion_class": "stunned_freeze",
                    "face_cue": "jaw drop freeze",
                    "tag": "Reaction",
                    "description": "ชะงักนิ่งอึ้งหลังเห็นเฉลย",
                    "confidence": 0.92,
                })

            def fake_export(src, spec):
                jpg = self._write_fake_jpeg(spec.out_dir, f"{spec.prefix}_01.jpg")
                return {"frames": [{"ts": "00:01:45", "path": str(jpg), "b64": "YWJj"}], "strip_path": None}

            opts = VerifyOptions(
                source=vid, endpoint="http://local", model="m",
                call_fn=fake_call, layout_fn=lambda s, b, preferred="auto": layout,
                motion_fn=lambda s, b, l: ([], [], ()),
                export_fn=fake_export,
                audio_fn=lambda s, b: AudioBurstMetrics(3.0, 2.0, None, True),
            )
            with patch("process.reaction_verify.classify_dual_regime", return_value=regime):
                out1 = verify_reaction_stamps([orig], ws, opts)
                out2 = verify_reaction_stamps([orig], ws, opts)
            self.assertEqual(len(calls), 1)
            self.assertEqual(out1, out2)
            self.assertTrue((ws / "reaction_verify_log.json").is_file())

            args = argparse.Namespace(reaction_verify=True, video_file=str(vid), endpoint="http://local", vision_model="m")
            with patch("process.reaction_verify.verify_reaction_stamps", return_value=out1):
                synced = apply_reaction_verify([orig], ws, args)
            self.assertEqual(synced, out1)
            self.assertIn("00:01:45 - [Reaction]", (ws / "all_timestamps.txt").read_text(encoding="utf-8"))

    def test_assembly_runs_reaction_verify_after_prune(self):
        from process.assembly import _prune_and_verify_timestamps

        order = []
        args = argparse.Namespace(vision_verify=False, reaction_verify=True)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("process.assembly.prune_essential", side_effect=lambda *a, **kw: (order.append("prune"), ["00:01:00 - [Reaction] x"])[1]):
                with patch("process.assembly.apply_reaction_verify", side_effect=lambda s, w, r: (order.append("reaction"), s)[1]):
                    _prune_and_verify_timestamps(["00:01:00 - [Reaction] x"], Path(tmp), "http://x", "m", 0.1, args, False)
        self.assertEqual(order, ["prune", "reaction"])

    def test_verify_calls_detect_obs_layout_fresh_per_stamp_without_caching(self):
        from process.reaction_verify import VerifyOptions, verify_reaction_stamps

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"mp4")
            b1 = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
            b2 = FaceBox(0.0, 0.38, 0.22, 0.24, "mid-left")
            layouts = [
                LayoutSegment("top-right", b1, b1.derive_tight_face()),
                LayoutSegment("mid-left", b2, b2.derive_tight_face()),
            ]
            seen_windows = []
            exported_boxes = []

            def fake_layout(src, bounds, preferred="auto"):
                seen_windows.append((bounds.start_sec, bounds.end_sec, preferred))
                return layouts[len(seen_windows) - 1]

            def fake_export(src, spec):
                exported_boxes.append(spec.box)
                jpg = self._write_fake_jpeg(spec.out_dir, f"{spec.prefix}_01.jpg")
                return {"frames": [{"ts": "00:02:00", "path": str(jpg), "b64": "YWJj"}], "strip_path": None}

            def fake_call(ep, mod, content):
                ts = "00:01:55" if "00:02:00" in content[0]["text"] else "00:04:55"
                return json.dumps({
                    "snapped_ts": ts, "emotion_class": "shock", "face_cue": "gasp",
                    "tag": "Reaction", "description": "ตกใจจังหวะสำคัญ", "confidence": 0.9,
                })

            opts = VerifyOptions(
                source=vid, endpoint="http://local", model="m",
                call_fn=fake_call, layout_fn=fake_layout,
                motion_fn=lambda s, b, l: ([], [], ()),
                export_fn=fake_export,
                audio_fn=lambda s, b: AudioBurstMetrics(3.0, 2.0, None, True),
            )
            regime = _sample_regime("shock_burst")
            with patch("process.reaction_verify.classify_dual_regime", return_value=regime):
                verify_reaction_stamps(
                    ["00:02:00 - [Reaction] อึ้ง", "00:05:00 - [Reaction] เหวอ"], ws, opts
                )
            self.assertEqual(len(seen_windows), 2)
            self.assertEqual(exported_boxes, [b1, None, b2, None])

    def test_high_res_video_priority_and_audio_stream_split(self):
        import subprocess
        from process.reaction_source import resolve_reaction_audio_source, resolve_reaction_source

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            low = ws / "video_360p.mp4"
            hi = ws / "video.mp4"
            low.write_bytes(b"360")
            hi.write_bytes(b"1080")
            self.assertEqual(resolve_reaction_source(ws, argparse.Namespace(remote_snap=True)), hi)
            hi.unlink()
            low.unlink()
            (ws / ".video_url").write_text("https://youtu.be/abc", encoding="utf-8")
            seen_fmts = []
            def fake_run(cmd, **kw):
                seen_fmts.append(cmd[cmd.index("-f") + 1])
                return subprocess.CompletedProcess(cmd, 0, stdout="https://stream.example/u\n", stderr="")
            with patch("process.reaction_source.subprocess.run", side_effect=fake_run):
                resolve_reaction_source(ws, argparse.Namespace(remote_snap=True))
                resolve_reaction_audio_source(ws, argparse.Namespace(remote_snap=True))
            self.assertIn("1080", seen_fmts[0])
            self.assertIn("bestaudio", seen_fmts[1])

    def test_transient_ffmpeg_error_retried_without_crashing_and_cache_persisted(self):
        from process.reaction_verify import VerifyOptions, verify_reaction_stamps

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            vid = ws / "video.mp4"
            vid.write_bytes(b"mp4")
            b1 = FaceBox(0.76, 0.0, 0.24, 0.30, "top-right")
            seg = LayoutSegment("top-right", b1, b1.derive_tight_face())

            def fake_motion(src, bounds, layout):
                if bounds.start_sec < 100:
                    raise RuntimeError("Failed to resolve hostname manifest.googlevideo.com")
                return [], [], ()

            def fake_export(src, spec):
                jpg = self._write_fake_jpeg(spec.out_dir, f"{spec.prefix}_01.jpg")
                return {"frames": [{"ts": "00:05:00", "path": str(jpg), "b64": "YWJj"}], "strip_path": None}

            def fake_call(ep, mod, content):
                return json.dumps({
                    "snapped_ts": "00:04:55", "emotion_class": "shock", "face_cue": "gasp",
                    "tag": "Reaction", "description": "ตกใจจังหวะสำคัญ", "confidence": 0.9,
                })

            opts = VerifyOptions(
                source=vid, endpoint="http://local", model="m", call_fn=fake_call,
                layout_fn=lambda s, b, preferred="auto": seg,
                motion_fn=fake_motion, export_fn=fake_export,
                audio_fn=lambda s, b: AudioBurstMetrics(3.0, 2.0, None, True),
            )
            regime = _sample_regime("shock_burst")
            with patch("process.reaction_verify.classify_dual_regime", return_value=regime), patch("process.reaction_io.time.sleep"):
                out = verify_reaction_stamps(["00:01:00 - [Reaction] อึ้ง", "00:05:00 - [Reaction] เหวอ"], ws, opts)
            self.assertEqual(out[0], "00:01:00 - [Reaction] อึ้ง")
            self.assertTrue(out[1].startswith("00:04:55"))
            saved = json.loads((ws / "reaction_verify_log.json").read_text(encoding="utf-8"))
            self.assertIn("00:05:00 - [Reaction] เหวอ", saved)
            self.assertNotIn("00:01:00 - [Reaction] อึ้ง", saved)

    def test_reaction_prompt_preserves_gameplay_review_and_forbids_ungrounded_names(self):
        from process.reaction_prompt import ParseConstraints, PromptContext, build_face_reaction_prompt, parse_snapped_response

        prompt = build_face_reaction_prompt(
            "04:50:31 - [Gameplay] ปรับเปลี่ยน Formation",
            _sample_regime("calm_news"),
            PromptContext(transcript_ctx="มูมเสถียรขึ้น ไม่มีปัญหา Emulator"),
        )
        self.assertIn("Gameplay|Review", prompt)
        self.assertIn("ปู่โบ๊ต", prompt)
        raw = json.dumps({
            "snapped_ts": "04:50:33",
            "emotion_class": "playful_tease",
            "tag": "Gameplay",
            "description": "ทดสอบปรับ Formation บน Emulator",
            "confidence": 0.9,
        })
        res = parse_snapped_response(raw, "04:50:31 - [Gameplay] ปรับเปลี่ยน Formation", ParseConstraints((17400, 17460)))
        self.assertTrue(res.accepted)
        self.assertIn("- [Gameplay] ", res.updated)


if __name__ == "__main__":
    unittest.main()
