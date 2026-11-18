"""Feature extraction, freeze plateau, oscillation, and onset inflection helpers."""
from __future__ import annotations

import math
import statistics
from typing import Dict, List, Tuple

from video.motion_types import FaceMotionSample, RegimeThresholds


def _med(vals: List[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def _eval_freeze_span(
    samples: List[FaceMotionSample], span: Tuple[int, int], fps: float
) -> Tuple[float, float, float, float]:
    """Compute (dur_sec, drop_ratio, pre_peak, plat_pose) for a freeze run."""
    i, j = span
    pre_lo = max(0, i - max(2, int(round(3.0 * fps))))
    pre_peak = max((samples[k].vel_1s for k in range(pre_lo, i + 1)), default=0.0)
    pre_min = min((samples[k].pose_shift for k in range(pre_lo, i)), default=samples[i].pose_shift)
    pre_max = max((samples[k].pose_shift for k in range(pre_lo, i)), default=samples[i].pose_shift)
    plat_vel = sum(samples[k].vel_step for k in range(i, j)) / (j - i)
    plat_pose = sum(samples[k].pose_shift for k in range(i, j)) / (j - i)
    if plat_pose < 0.45 * pre_max or (pre_peak < 0.045 and (plat_pose - pre_min) < 0.035):
        return (0.0, 0.0, 0.0, 0.0)
    return ((j - i) / fps, pre_peak / max(plat_vel, 0.004), pre_peak, plat_pose)


def _advance_freeze(samples: List[FaceMotionSample], start: int, thr: RegimeThresholds) -> int:
    """Advance index across a contiguous low-velocity shifted-pose plateau."""
    j, lag_1s = start, max(1, int(round(thr.fps)))
    while (
        j < len(samples) and samples[j].vel_step <= thr.freeze_vel_ceiling
        and samples[j].pose_shift >= thr.freeze_pose_floor
        and ((j - start) < lag_1s or samples[j].vel_1s <= 0.032)
    ):
        j += 1
    return j


def detect_freeze_plateau(
    samples: List[FaceMotionSample], fps: float, thr: RegimeThresholds
) -> Dict[str, float]:
    """Find best sustained near-zero freeze plateau following an entry shift or spike."""
    best: Dict[str, float] = {"dur": 0.0, "drop": 0.0, "pre_peak": 0.0, "start": 0.0, "mid": 0.0, "pose": 0.0}
    i, min_len = 1, max(2, int(round(thr.min_freeze_sec * fps)))
    while i < len(samples):
        if samples[i].vel_step <= thr.freeze_vel_ceiling and samples[i].pose_shift >= thr.freeze_pose_floor:
            j = _advance_freeze(samples, i, thr)
            if (j - i) >= min_len:
                dur, drop, pre_pk, p_pose = _eval_freeze_span(samples, (i, j), fps)
                if dur > best["dur"]:
                    best = {"dur": round(dur, 3), "drop": round(drop, 3), "pre_peak": round(pre_pk, 5),
                            "start": float(i), "mid": float((i + j - 1) // 2), "pose": round(p_pose, 5)}
            i = j + 1
        else:
            i += 1
    return best


def _count_cycles(poses: List[float], fps: float) -> int:
    """Count distinct rhythmic pose excursion peaks separated by valleys."""
    med_p = _med(poses)
    floor = max(0.045, med_p + max(0.025, 0.35 * med_p))
    min_sep, max_sep = max(1, int(round(0.6 * fps))), max(4, int(round(4.5 * fps)))
    peaks: List[int] = []
    for i in range(1, len(poses) - 1):
        if poses[i] >= floor and poses[i] >= poses[i - 1] and poses[i] >= poses[i + 1]:
            if not peaks or (i - peaks[-1]) >= min_sep:
                peaks.append(i)
    if not peaks:
        return 0
    return 1 + sum(1 for a, b in zip(peaks, peaks[1:])
                   if (b - a) <= max_sep and min(poses[a : b + 1]) <= max(poses[a], poses[b]) * 0.65)


def _count_reversals(poses: List[float], med_p: float, max_sep: int) -> int:
    """Count smoothed directional reversals exceeding noise threshold."""
    revs, last_dir, last_idx, thresh = 0, 0, -999, max(0.015, 0.25 * med_p)
    for i in range(1, len(poses)):
        diff = poses[i] - poses[i - 1]
        if abs(diff) < thresh:
            continue
        cur_dir = 1 if diff > 0 else -1
        if last_dir != 0 and cur_dir != last_dir and (i - last_idx) <= max_sep:
            revs += 1
        if last_dir == 0 or cur_dir != last_dir:
            last_idx = i
        last_dir = cur_dir
    return revs


def count_oscillations(samples: List[FaceMotionSample], fps: float) -> Tuple[int, int]:
    """Count rhythmic pose cycles and directional reversals after binomial smoothing."""
    n = len(samples)
    if n < 5:
        return (0, 0)
    raw = [s.pose_shift for s in samples]
    poses = [raw[0]] + [0.25 * raw[i - 1] + 0.5 * raw[i] + 0.25 * raw[i + 1] for i in range(1, n - 1)] + [raw[-1]]
    return (_count_cycles(poses, fps), _count_reversals(poses, _med(poses), max(4, int(round(4.5 * fps)))))


def find_onset_index(samples: List[FaceMotionSample], ref_idx: int, fps: float) -> int:
    """Snap to earliest suprathreshold burst inflection preceding or at ref_idx."""
    if len(samples) <= 1 or ref_idx <= 0:
        return 0
    early = next((i for i in range(1, ref_idx + 1) if samples[i].z_score >= 3.5 and samples[i].vel_1s >= 0.060), ref_idx)
    anchor = min(ref_idx, early)
    pre = samples[:anchor]
    base_v = _med([s.vel_1s for s in pre[1:]]) if len(pre) > 2 else samples[0].vel_1s
    base_p = _med([s.pose_shift for s in pre]) if pre else 0.0
    v_gate = max(base_v + 0.35 * max(0.0, max(samples[anchor].vel_1s, samples[anchor].vel_step) - base_v), 0.032)
    p_gate = max(base_p + 0.35 * max(0.0, samples[anchor].pose_shift - base_p), 0.035)
    onset = anchor
    for k in range(anchor, max(0, anchor - max(2, int(round(3.0 * fps)))), -1):
        if samples[k].vel_1s >= v_gate or samples[k].pose_shift >= p_gate:
            onset = k
        else:
            break
    return onset


def _burst_width_sec(samples: List[FaceMotionSample], peak_idx: int, fps: float) -> float:
    """Measure contiguous width around peak_idx above half-peak burst floor."""
    peak_v = max(samples[peak_idx].vel_1s, samples[peak_idx].vel_step)
    thresh, lo, hi = max(0.045, 0.45 * peak_v), peak_idx, peak_idx
    while lo > 1 and max(samples[lo - 1].vel_1s, samples[lo - 1].vel_step) >= thresh:
        lo -= 1
    while hi + 1 < len(samples) and max(samples[hi + 1].vel_1s, samples[hi + 1].vel_step) >= thresh:
        hi += 1
    return (hi - lo + 1) / fps


def _empty_features(n: int) -> Dict[str, float]:
    keys = ("dur", "peak_vel", "mean_vel", "med_vel", "rms_vel", "rms_step", "peak_pose", "z_max",
            "bw", "duty", "vel_duty", "cycles", "revs", "post_vel", "post_pose", "pk_v_idx",
            "pk_m_idx", "onset_idx", "frz_dur", "frz_drop", "frz_pre", "frz_lag", "frz_pose",
            "frz_start", "frz_mid", "frz_onset")
    out = {k: 0.0 for k in keys}
    out["n"], out["sr"] = float(n), 1.0
    return out


def _vel_pose_stats(samples: List[FaceMotionSample], fps: float) -> Dict[str, float]:
    """Compute velocity, pose, and duty-cycle summary metrics."""
    n, vels = len(samples), [max(s.vel_1s, s.vel_step) for s in samples[1:]]
    steps = [s.vel_step for s in samples[1:]]
    pk_v_idx = max(range(n), key=lambda i: max(samples[i].vel_1s, samples[i].vel_step))
    pk_m_idx = max(range(n), key=lambda i: samples[i].motion_score)
    pk_v, med_v = max(samples[pk_v_idx].vel_1s, samples[pk_v_idx].vel_step), _med(vels)
    post = samples[min(n - 1, pk_m_idx + 1) : min(n, pk_m_idx + max(2, int(round(5.0 * fps))))]
    return {
        "n": float(n), "dur": round((n - 1) / fps, 3), "peak_vel": round(pk_v, 5),
        "mean_vel": round(sum(vels) / len(vels), 5), "med_vel": round(med_v, 5),
        "rms_vel": round(math.sqrt(sum(v * v for v in vels) / len(vels)), 5),
        "rms_step": round(math.sqrt(sum(v * v for v in steps) / len(steps)), 5),
        "peak_pose": round(max(s.pose_shift for s in samples), 5), "z_max": round(max(s.z_score for s in samples), 3),
        "sr": round(pk_v / max(med_v, 0.012), 3), "bw": round(_burst_width_sec(samples, pk_v_idx, fps), 3),
        "duty": round(sum(1 for s in samples[1:] if max(s.vel_1s, s.vel_step) >= 0.045 or s.pose_shift >= 0.060) / len(vels), 3),
        "vel_duty": round(sum(1 for s in samples[1:] if max(s.vel_1s, s.vel_step) >= 0.055) / len(vels), 3),
        "post_vel": round(sum(s.vel_step for s in post) / len(post), 5) if post else 0.0, "post_pose": round(sum(s.pose_shift for s in post) / len(post), 5) if post else 0.0,
        "pk_v_idx": float(pk_v_idx), "pk_m_idx": float(pk_m_idx),
    }


def _build_feature_dict(
    samples: List[FaceMotionSample], fps: float, frz: Dict[str, float]
) -> Dict[str, float]:
    """Assemble numeric kinematic feature dictionary from precomputed samples."""
    feat = _vel_pose_stats(samples, fps)
    cycles, revs = count_oscillations(samples, fps)
    feat.update({
        "cycles": float(cycles), "revs": float(revs),
        "frz_dur": frz["dur"], "frz_drop": frz["drop"], "frz_pre": frz["pre_peak"],
        "frz_lag": round((frz["start"] - feat["pk_v_idx"]) / fps, 3) if frz["dur"] > 0 else 0.0,
        "frz_pose": frz["pose"], "frz_start": frz["start"], "frz_mid": frz["mid"],
    })
    return feat


def extract_features(samples: List[FaceMotionSample], fps: float, thr: RegimeThresholds) -> Dict[str, float]:
    """Compute calibrated summary transition features across a sample window."""
    if len(samples) < 2:
        return _empty_features(len(samples))
    frz = detect_freeze_plateau(samples, fps, thr)
    feat = _build_feature_dict(samples, fps, frz)
    onset_idx = find_onset_index(samples, int(feat["pk_v_idx"]), fps)
    frz_onset = find_onset_index(samples, int(frz["start"]), fps) if frz["dur"] >= thr.min_freeze_sec else onset_idx
    feat["onset_idx"], feat["frz_onset"] = float(onset_idx), float(frz_onset)
    return feat
