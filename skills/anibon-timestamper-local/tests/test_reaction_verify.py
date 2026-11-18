"""Unit tests for Task 4: telemetry-injected reaction prompt, co-triggers, and resolver."""
from __future__ import annotations

import json
import unittest

from video.audio_envelope import AudioBurstMetrics
from video.motion_types import KeyframePick, MotionRegime


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


if __name__ == "__main__":
    unittest.main()
