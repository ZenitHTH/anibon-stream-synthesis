"""Cross-VOD offline regression suite and optional real-clip calibration benchmark."""
from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from common.time import fmt_ts
from common.timestamps import deduplicate_consecutive_timestamps
from process.multimodal_situations import score_item_situations
from process.reaction_io import CoTriggerContext, collect_co_triggers
from process.reaction_prompt import (
    ParseConstraints,
    needs_reaction_verify,
    parse_snapped_response,
    resolve_monotonic_snap,
)
from video.audio_envelope import compute_audio_envelope_from_pcm, extract_audio_burst_metrics
from video.face_motion import extract_dual_motion_series
from video.face_motion_metrics import classify_dual_regime, score_motion_series
from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox, RegimeThresholds, WindowBounds
from video.obs_layout import detect_layout_cuts, detect_obs_layout, split_around_cuts

_FIXTURE = Path(__file__).parent / "fixtures" / "cross_vod_reaction_gold.json"
_THEORY_ROOT = Path("/Users/zenithth/.gemini/antigravity/scratch/theory_proof")


def _load_gold() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _rect_rgb(size: int, rect: tuple[int, int, int, int], fg: int = 220) -> bytes:
    buf = bytearray([20] * (size * size * 3))
    x0, y0, x1, y1 = rect
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes((fg, fg, 60))
    return bytes(buf)


def _paint_norm(size: int, box: FaceBox, rgb: tuple[int, int, int]) -> bytes:
    buf = bytearray([15] * (size * size * 3))
    x0, x1 = int(box.x * size), int((box.x + box.w) * size)
    y0, y1 = int(box.y * size), int((box.y + box.h) * size)
    for y in range(max(0, y0), min(size, y1)):
        for x in range(max(0, x0), min(size, x1)):
            idx = (y * size + x) * 3
            buf[idx : idx + 3] = bytes(rgb)
    return bytes(buf)


def _tone_pcm(amp: int, sec: float, sr: int = 8000) -> bytes:
    n = int(round(sec * sr))
    vals = [int(amp * math.sin(2.0 * math.pi * 220.0 * i / sr)) for i in range(n)]
    return struct.pack(f"<{n}h", *vals)


class TestReactionGoldBenchmark(unittest.TestCase):
    def test_rapid_reaction_preservation_and_banter_collapse(self) -> None:
        gold = _load_gold()
        kept = deduplicate_consecutive_timestamps(gold["rapid_reaction_stamps"], min_gap_sec=120, max_dedup_gap_sec=600)
        collapsed = deduplicate_consecutive_timestamps(gold["duplicate_banter_stamps"], min_gap_sec=120, max_dedup_gap_sec=600)
        self.assertEqual(len(kept), 4)
        self.assertEqual(len(collapsed), 1)

    def test_layout_cut_suppression_pip_teleport_and_auto_fallback(self) -> None:
        pre = [_paint_norm(16, FaceBox(0, 0, 1, 1), (20, 20, 20)) for _ in range(16)]
        post = [_paint_norm(16, FaceBox(0, 0, 1, 1), (235, 235, 235)) for _ in range(24)]
        cuts = detect_layout_cuts(pre + post, fps=2.0, cut_mad_floor=0.22)
        lo, hi = split_around_cuts(len(pre + post), cuts, fps=2.0)
        self.assertEqual(cuts, [16])
        self.assertGreaterEqual(lo, 20)
        self.assertEqual(hi, 40)

        h1 = [_paint_norm(48, WEBCAM_BOX_PRESETS["top-right"], ((i * 55) % 250, 70, 90)) for i in range(6)]
        h2 = [_paint_norm(48, FaceBox(0.35, 0.58, 0.22, 0.28), ((i * 55) % 250, 90, 70)) for i in range(6)]
        with patch("video.obs_layout._probe_full_frames", return_value=h1 + h2):
            seg = detect_obs_layout(Path("dummy.mp4"), WindowBounds(0.0, 12.0), preferred="top-right")
        self.assertEqual(seg.layout, "auto-tracked")
        self.assertGreaterEqual(seg.clean_start_sec, 5.0)

    def test_protected_tags_and_45s_monotonic_snap_bounds(self) -> None:
        gold = _load_gold()
        for stamp in gold["protected_milestone_stamps"][:3]:
            raw = json.dumps({"snapped_ts": stamp[:8], "emotion_class": "shock",
                              "tag": "Reaction", "description": "อัปเดตเหตุการณ์สำคัญ", "confidence": 0.9})
            res = parse_snapped_response(raw, stamp, ParseConstraints((0, 20000)))
            self.assertTrue(res.accepted)
            self.assertIn(stamp.split("[", 1)[1].split("]", 1)[0], res.updated)
        quiet_news = gold["co_trigger_cases"]["quiet_news"]
        self.assertFalse(needs_reaction_verify(quiet_news["stamp"], quiet_news["transcript"]))
        r1 = parse_snapped_response('{"snapped_ts":"00:10:00","emotion_class":"shock","tag":"Reaction","description":"ตกใจ","confidence":0.9}', "00:10:05 - [Reaction] A", ParseConstraints((580, 640)))
        r2 = parse_snapped_response('{"snapped_ts":"00:10:20","emotion_class":"shock","tag":"Reaction","description":"ซ้ำ","confidence":0.9}', "00:10:25 - [Reaction] B", ParseConstraints((580, 640)))
        self.assertEqual(len(resolve_monotonic_snap([r1, r2], collision_sec=45)), 1)

    def test_posture_act_bed_retreat_vs_empty_chair_afk(self) -> None:
        f_s, _ = score_motion_series([_rect_rgb(16, (4, 4, 10, 10), 200) for _ in range(12)] + [_rect_rgb(16, (0, 0, 1, 1), 20) for _ in range(28)], fps=2.0)
        w_walk = [_rect_rgb(16, (1 + i, 2, 7 + i, 12), 220) for i in range(6)]
        w_s, _ = score_motion_series([_rect_rgb(16, (5, 5, 10, 10), 210) for _ in range(12)] + w_walk + [_rect_rgb(16, (10, 1, 15, 6), 220) for _ in range(22)], fps=2.0)
        reg = classify_dual_regime(f_s, w_s, RegimeThresholds())
        self.assertEqual(reg.regime, "posture_act")
        post_kf = [k for k in reg.keyframes if k.role == "post_peak_state"][0]
        self.assertGreaterEqual(post_kf.rel_sec - reg.peak_rel_sec, 2.5)
        bed = parse_snapped_response('{"snapped_ts":"00:05:10","emotion_class":"physical_act","pose_cue":"lie_on_bed","tag":"Reaction","description":"ลุกไปนอนแผ่บนเตียง","confidence":0.9}', "00:05:12 - [Reaction] พัก", ParseConstraints((290, 350)))
        afk = parse_snapped_response('{"snapped_ts":"00:05:10","emotion_class":"empty_chair_afk","pose_cue":"none","tag":"Reaction","description":"ไม่มีคน","confidence":0.95}', "00:05:12 - [Reaction] พัก", ParseConstraints((290, 350)))
        self.assertTrue(bed.accepted)
        self.assertFalse(afk.accepted)

    def test_co_trigger_recovery_on_flat_facial_motion(self) -> None:
        cases = _load_gold()["co_trigger_cases"]
        aud = compute_audio_envelope_from_pcm(_tone_pcm(150, 4.0) + _tone_pcm(14000, 1.0) + _tone_pcm(150, 3.0))
        self.assertTrue(aud.has_audio_trigger)
        self.assertGreaterEqual(score_item_situations(cases["motionless_rant"]["transcript"]), 2.0)
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            peak_sec = cases["subtle_tease"]["mood_555_peak_sec"]
            mood = {"chunk_00": {"verdict": "MEME_PULSE", "peak_windows": [{"start": fmt_ts(peak_sec - 20), "end": fmt_ts(peak_sec + 20)}]}}
            (ws / "mood_555.json").write_text(json.dumps(mood), encoding="utf-8")
            sig = collect_co_triggers(ws, peak_sec, CoTriggerContext(cases["subtle_tease"]["transcript"]))
            self.assertEqual(sig.chat_verdict, "MEME_PULSE")
            self.assertTrue(sig.has_any)

    @unittest.skipUnless(_THEORY_ROOT.is_dir(), "Local theory_proof real VOD clips not present")
    def test_real_clip_cross_vod_calibration(self) -> None:
        clips = _load_gold()["real_clips"]
        hits, total = 0, 0
        for row in clips:
            clip = _THEORY_ROOT / row["rel_path"]
            if not clip.is_file():
                continue
            b = WindowBounds(row["start_sec"], row["end_sec"])
            lay = detect_obs_layout(clip, b, preferred=row["preferred_layout"])
            f_s, w_s, _ = extract_dual_motion_series(clip, b, lay)
            reg = classify_dual_regime(f_s, w_s)
            aud = extract_audio_burst_metrics(clip, b)
            pred = reg.trigger_vlm or aud.has_audio_trigger
            hits += int(pred == row["expected_reaction"])
            total += 1
            print(f"[calib] {row['id']} det={lay.layout} reg={reg.regime} trig={reg.trigger_vlm} wz={reg.webcam_z_max:.2f} audZ={aud.rms_z_max:.2f}")
        self.assertGreater(total, 0)
        self.assertGreaterEqual(hits / total, 0.75)


if __name__ == "__main__":
    unittest.main()
