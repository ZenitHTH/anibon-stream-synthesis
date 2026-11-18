"""Pure-stdlib RGB24 motion kinematics, Dual-Box fusion, and 4-keyframe selection."""
from __future__ import annotations

import statistics
from typing import Dict, List, Optional, Tuple

from common.time import fmt_ts
from video.motion_features import extract_features
from video.motion_scoring import score_dual_regimes
from video.motion_types import FaceMotionSample, KeyframePick, MotionRegime, RegimeThresholds


def _frame_stats(frame: bytes, n_pix: int) -> Tuple[Tuple[float, float, float], float]:
    """Return per-channel u8 means and spatial contrast in [0..1]."""
    means = (sum(frame[0::3]) / n_pix, sum(frame[1::3]) / n_pix, sum(frame[2::3]) / n_pix)
    cont = sum(abs(p - means[c]) for c in (0, 1, 2) for p in frame[c::3]) / (n_pix * 3.0 * 255.0)
    return (means, cont)


def compute_frame_delta(frame_a: bytes, frame_b: bytes) -> Tuple[float, float, float, float, float]:
    """Compute (blended_mad, raw_mad, struct_mad, upper_mad, lower_mad) between RGB24 frames."""
    n = min(len(frame_a), len(frame_b))
    if n < 3:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    half = (n // 6) * 3
    up_d = sum(abs(a - b) for a, b in zip(frame_a[:half], frame_b[:half]))
    lo_d = sum(abs(a - b) for a, b in zip(frame_a[half:n], frame_b[half:n]))
    raw = (up_d + lo_d) / (n * 255.0)
    up_m, lo_m = up_d / (max(1, half) * 255.0), lo_d / (max(1, n - half) * 255.0)
    m_a, c_a = _frame_stats(frame_a[:n], n // 3)
    m_b, c_b = _frame_stats(frame_b[:n], n // 3)
    if min(c_a, c_b) < 0.012:
        return (raw, raw, 0.0, up_m, lo_m)
    dr = (m_a[0] - m_b[0], m_a[1] - m_b[1], m_a[2] - m_b[2])
    s_diff = sum(abs((a - b) - dr[c]) for c in (0, 1, 2) for a, b in zip(frame_a[c:n:3], frame_b[c:n:3]))
    struct = s_diff / (n * 255.0)
    return (0.45 * raw + 0.55 * struct, raw, struct, up_m, lo_m)


def _pick_anchor_index(vel_1s: List[float], fps: float) -> int:
    """Pick calmest pre-peak resting baseline frame index."""
    n = len(vel_1s)
    if n <= 2:
        return 0
    smooth = [sum(vel_1s[max(1, i - 1) : min(n, i + 2)]) / max(1, min(n, i + 2) - max(1, i - 1)) for i in range(n)]
    peak_idx = max(range(n), key=lambda i: vel_1s[i])
    search_end = peak_idx if peak_idx >= max(2, int(round(fps))) else max(2, int(round(0.45 * n)))
    best_pre = min(range(0, max(1, search_end)), key=lambda i: (smooth[i], i))
    g_min = min(smooth)
    return best_pre if smooth[best_pre] <= max(g_min * 1.6, g_min + 0.012) else min(range(n), key=lambda i: (smooth[i], i))


def _step_deltas(frames: List[bytes], lag_1s: int) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Compute step, 1s-lag, upper, and lower frame deltas."""
    n = len(frames)
    v_s, v_1, up, lo = [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n):
        b, _, _, u, l = compute_frame_delta(frames[i - 1], frames[i])
        v_s[i], up[i], lo[i] = b, u, l
        prev = max(0, i - lag_1s)
        v_1[i] = b if prev == i - 1 else compute_frame_delta(frames[prev], frames[i])[0]
    return (v_s, v_1, up, lo)


def _series_fps(samples: List[FaceMotionSample]) -> float:
    if len(samples) > 1 and samples[1].rel_sec > samples[0].rel_sec:
        return round(1.0 / (samples[1].rel_sec - samples[0].rel_sec), 2)
    return 2.0


def score_motion_series(
    frames: List[bytes], fps: float = 2.0, abs_offset_sec: float = 0.0
) -> Tuple[List[FaceMotionSample], int]:
    """Compute normalized pixel delta, local baseline, and modified Z-score series."""
    n = len(frames)
    if n == 0:
        return ([], 0)
    v_s, v_1, up, lo = _step_deltas(frames, max(1, int(round(fps))))
    anchor_idx = _pick_anchor_index(v_1, fps)
    poses = [compute_frame_delta(frames[anchor_idx], f)[0] for f in frames]
    med_v = statistics.median(v_1[1:]) if n > 1 else 0.0
    sig_v = max(1.4826 * (statistics.median([abs(v - med_v) for v in v_1[1:]]) if n > 1 else 0.0), 0.008)
    samples = [FaceMotionSample(
        i, round(i / fps, 3), round(abs_offset_sec + i / fps, 3), fmt_ts(abs_offset_sec + i / fps),
        round(v_s[i], 5), round(v_1[i], 5), round(up[i], 5), round(lo[i], 5),
        round(poses[i], 5), round((v_1[i] - med_v) / sig_v, 3), round(max(v_1[i], 0.85 * poses[i]), 5),
    ) for i in range(n)]
    return (samples, anchor_idx)


def _pick_post_idx(samples: List[FaceMotionSample], feat: Dict[str, float], regime: str) -> int:
    """Pick post-peak state index (extended +2.5..+12s settled hold for posture_act)."""
    n, peak_idx, fps = len(samples), int(feat["pk_m_idx"]), _series_fps(samples)
    if regime == "stunned_freeze" and int(feat["frz_mid"]) > 0:
        return int(feat["frz_mid"])
    if regime == "posture_act":
        lo = min(n - 1, peak_idx + max(1, int(round(2.5 * fps))))
        hi = min(n, peak_idx + max(2, int(round(12.0 * fps))) + 1)
        if lo < hi:
            return min(range(lo, hi), key=lambda i: (samples[i].vel_1s + 0.5 * samples[i].vel_step, -samples[i].pose_shift))
    lo, hi = min(n - 1, peak_idx + 1), min(n, peak_idx + max(2, int(round(4.0 * fps))))
    return max(range(lo, hi), key=lambda i: samples[i].pose_shift) if lo < hi else min(n - 1, peak_idx + 1)


def _dedup_keyframes(samples: List[FaceMotionSample], raw: List[Tuple[str, int]]) -> Tuple[KeyframePick, ...]:
    """Ensure all 4 keyframe picks map to distinct indices in causal order."""
    n, seen, picks = len(samples), set(), []
    for role, idx in raw:
        idx = max(0, min(n - 1, idx))
        if idx in seen and n >= 4:
            idx = next((idx + d for d in (1, -1, 2, -2, 3, -3) if 0 <= idx + d < n and (idx + d) not in seen), idx)
        if idx in seen:
            continue
        seen.add(idx)
        s = samples[idx]
        picks.append(KeyframePick(role, idx, s.rel_sec, s.abs_sec, s.ts, s.vel_1s, s.pose_shift, s.z_score))
    return tuple(picks)


def _local_anchor(samples: List[FaceMotionSample], onset_idx: int, fps: float) -> int:
    """Keep pre_onset_baseline within 15s before onset when clip is long."""
    max_lag = max(4, int(round(15.0 * fps)))
    if onset_idx <= max_lag:
        return 0
    lo_a, hi_a = max(0, onset_idx - max_lag), max(1, onset_idx - 1)
    return min(range(lo_a, hi_a), key=lambda i: (samples[i].vel_1s + 0.5 * samples[i].vel_step, i))


def select_dynamic_keyframes(
    samples: List[FaceMotionSample], feat: Dict[str, float], regime: str
) -> Tuple[KeyframePick, ...]:
    """Select 4 distinct transition keyframes with local 15s pre-onset baseline."""
    if not samples:
        return ()
    fps = _series_fps(samples)
    onset_idx = int(feat["frz_onset"]) if regime == "stunned_freeze" else int(feat["onset_idx"])
    peak_idx = int(feat["pk_v_idx"]) if regime == "shock_burst" else int(feat["pk_m_idx"])
    if regime == "stunned_freeze" and peak_idx == onset_idx and int(feat["frz_start"]) > onset_idx:
        peak_idx = int(feat["frz_start"])
    anchor_idx = _local_anchor(samples, onset_idx, fps)
    if onset_idx == peak_idx:
        onset_idx = peak_idx - 1 if peak_idx > anchor_idx + 1 else onset_idx
        peak_idx = peak_idx + 1 if onset_idx == peak_idx and peak_idx + 1 < len(samples) else peak_idx
    post_idx = _pick_post_idx(samples, feat, regime)
    if onset_idx == anchor_idx and peak_idx > anchor_idx + 1:
        onset_idx = anchor_idx + max(1, (peak_idx - anchor_idx) // 2)
    return _dedup_keyframes(samples, [("pre_onset_baseline", anchor_idx), ("onset_inflection", onset_idx),
                                      ("peak_delta", peak_idx), ("post_peak_state", post_idx)])


def _pick_winning_regime(scores: Dict[str, float]) -> str:
    """Resolve highest-priority regime from calibrated scores."""
    non_calm = max(v for k, v in scores.items() if k != "calm_news")
    if scores["calm_news"] >= 0.85 and non_calm < 0.65:
        return "calm_news"
    prio = {"posture_act": 6, "shock_burst": 5, "angry": 4, "joy_flex": 3, "playful_tease": 2, "stunned_freeze": 1, "calm_news": 0}
    return sorted(scores.items(), key=lambda kv: (kv[1], prio.get(kv[0], 0)), reverse=True)[0][0]


def _build_regime_result(
    ref_samples: List[FaceMotionSample], scores: Dict[str, float], telemetry: Tuple[str, Dict[str, float], Dict[str, float]]
) -> MotionRegime:
    """Construct final MotionRegime dataclass from selected reference series."""
    regime, f_feat, w_feat = telemetry
    ref_feat = w_feat if regime in ("posture_act", "shock_burst") and w_feat["z_max"] >= f_feat["z_max"] else f_feat
    onset_idx = int(ref_feat["frz_onset"]) if regime == "stunned_freeze" else int(ref_feat["onset_idx"])
    peak_idx = int(ref_feat["pk_v_idx"]) if regime == "shock_burst" else int(ref_feat["pk_m_idx"])
    o_s, p_s = (ref_samples[onset_idx], ref_samples[peak_idx]) if ref_samples else (None, None)
    return MotionRegime(
        regime=regime, trigger_vlm=(regime != "calm_news"), confidence=scores[regime],
        onset_rel_sec=o_s.rel_sec if o_s else 0.0, onset_abs_sec=o_s.abs_sec if o_s else 0.0,
        onset_ts=o_s.ts if o_s else "00:00:00", peak_rel_sec=p_s.rel_sec if p_s else 0.0,
        peak_abs_sec=p_s.abs_sec if p_s else 0.0, peak_ts=p_s.ts if p_s else "00:00:00",
        webcam_z_max=w_feat["z_max"], w_pose_shift=w_feat["peak_pose"],
        freeze_duration_sec=f_feat["frz_dur"], freeze_drop_ratio=f_feat["frz_drop"],
        burst_width_sec=ref_feat["bw"], keyframes=select_dynamic_keyframes(ref_samples, ref_feat, regime),
        scores=scores, features=ref_feat,
    )


def classify_dual_regime(
    face_samples: List[FaceMotionSample], webcam_samples: List[FaceMotionSample],
    thresholds: Optional[RegimeThresholds] = None,
) -> MotionRegime:
    """Classify Dual-Box F+W kinematics into reaction regime and 4 keyframes."""
    thr = thresholds or RegimeThresholds()
    f_feat, w_feat = extract_features(face_samples, thr.fps, thr), extract_features(webcam_samples or face_samples, thr.fps, thr)
    scores = score_dual_regimes(f_feat, w_feat, thr)
    regime = "calm_news" if not face_samples else _pick_winning_regime(scores)
    use_w = regime in ("posture_act", "shock_burst") and w_feat["z_max"] >= f_feat["z_max"]
    return _build_regime_result((webcam_samples or face_samples) if use_w else face_samples, scores, (regime, f_feat, w_feat))
