"""Calibrated Dual-Box F+W regime affinity scoring."""
from __future__ import annotations

from typing import Dict, Tuple

from video.motion_types import RegimeThresholds


def _score_freeze(f: Dict[str, float], thr: RegimeThresholds) -> float:
    """Score stunned_freeze affinity on feature dict."""
    if f["frz_dur"] < thr.min_freeze_sec or f["frz_drop"] < 2.0 or f["frz_pose"] < thr.freeze_pose_floor:
        return 0.0
    sc = min(1.0, 0.60 + 0.14 * (f["frz_dur"] - thr.min_freeze_sec) + 0.06 * min(f["frz_drop"], 5.0))
    if f["z_max"] >= 5.0 and f["peak_vel"] >= 0.10 and (f["frz_lag"] > 6.0 or f["frz_lag"] < -1.0) and f["frz_pre"] < 0.65 * f["peak_vel"]:
        sc *= 0.45
    if f["cycles"] >= 3 and f["duty"] >= 0.55 and f["frz_dur"] < 4.5:
        sc *= 0.70
    return sc


def _score_angry(f: Dict[str, float], thr: RegimeThresholds) -> float:
    """Score sustained angry agitation on tight-face features."""
    is_ang = (f["mean_vel"] >= thr.angry_mean_vel or f["rms_vel"] >= thr.angry_rms_vel) and f["duty"] >= thr.angry_duty_cycle and (
        (f["vel_duty"] >= 0.50 and f["rms_step"] >= 0.090 and f["peak_vel"] >= 0.085)
        or (f["mean_vel"] >= 0.068 and f["vel_duty"] >= 0.48 and f["rms_step"] >= 0.058 and f["peak_vel"] >= 0.250)
    )
    if not is_ang:
        return 0.0
    sc = min(1.0, 0.56 + 2.8 * (f["mean_vel"] - thr.angry_mean_vel) + 0.38 * f["duty"] + 1.5 * max(0.0, f["rms_step"] - 0.055))
    if f["z_max"] < 1.5 and f["sr"] < 1.6 and f["mean_vel"] < 0.085:
        sc *= 0.4
    if f["med_vel"] < 0.035 and f["duty"] < 0.65:
        sc *= 0.65
    return sc


def _score_angry_and_freeze(f: Dict[str, float], thr: RegimeThresholds) -> Tuple[float, float]:
    """Score stunned_freeze and sustained angry on tight-face features."""
    return (_score_freeze(f, thr), _score_angry(f, thr))


def _score_shock_joy(f: Dict[str, float], thr: RegimeThresholds, frz_sc: float) -> Tuple[float, float]:
    """Score shock_burst and joy_flex on a feature dict."""
    eff_sr = max(thr.spike_ratio, 4.6) if (f["med_vel"] >= 0.035 and f["peak_vel"] < 0.250) else thr.spike_ratio
    shk = 0.0
    if f["peak_vel"] >= thr.motion_threshold and f["sr"] >= eff_sr and f["z_max"] >= 2.8 and f["bw"] <= 6.5 and f["vel_duty"] < 0.45:
        shk = min(1.0, 0.55 + 0.08 * min(f["sr"], 6.0) + 0.04 * min(f["z_max"], 8.0) + (0.08 if f["bw"] <= 3.0 else 0.0))
        if frz_sc >= 0.70 and -0.5 <= f["frz_lag"] <= 4.0:
            shk *= 0.40
    joy = 0.0
    if f["peak_pose"] >= thr.pose_threshold and f["peak_vel"] >= thr.motion_threshold and f["post_pose"] >= thr.joy_post_pose_floor and f["post_vel"] >= thr.joy_post_vel_floor and f["vel_duty"] < 0.68:
        if f["med_vel"] < 0.035 or f["sr"] >= 3.2 or f["peak_vel"] >= 0.250:
            joy = min(1.0, 0.55 + 1.8 * (f["post_pose"] - thr.joy_post_pose_floor) + 1.5 * min(f["post_vel"], 0.12))
            if f["z_max"] >= 6.0 and f["sr"] >= 5.0 and f["bw"] <= 4.0 and f["post_vel"] > 0.12:
                joy *= 0.85
    return (shk, joy)


def _score_posture(f_feat: Dict[str, float], w_feat: Dict[str, float], thr: RegimeThresholds) -> float:
    """Detect chair-departure / bed-retreat / full-body camera play from W vs F."""
    wide_move = w_feat["peak_pose"] >= thr.posture_w_pose_floor and w_feat["peak_vel"] >= thr.posture_w_peak_floor
    held = w_feat["post_pose"] >= 0.08
    not_chair_freeze = w_feat["bw"] >= 2.0 or f_feat["frz_dur"] < thr.min_freeze_sec
    if wide_move and held and not_chair_freeze:
        return round(min(0.98, 0.78 + 0.8 * (w_feat["peak_pose"] - thr.posture_w_pose_floor)), 3)
    return 0.0


def _score_tease_and_calm(
    f_feat: Dict[str, float], thr: RegimeThresholds, active: Tuple[float, float, float, float, float]
) -> Tuple[float, float]:
    """Score playful_tease and talking-head calm_news baseline."""
    frz_sc, ang_sc, shk_sc, joy_sc, post_sc = active
    talk = (f_feat["dur"] >= 20.0 and f_feat["med_vel"] >= 0.035 and f_feat["sr"] < 4.5
            and f_feat["peak_vel"] < 0.245 and (f_feat["mean_vel"] / max(f_feat["med_vel"], 0.01)) < 1.32
            and (f_feat["cycles"] / max(f_feat["dur"], 1.0)) < 0.05)
    tease = 0.0
    if (f_feat["cycles"] >= 2 or f_feat["revs"] >= 3) and (f_feat["peak_pose"] >= 0.048 or f_feat["peak_vel"] >= 0.045):
        tease = 0.35 if talk else min(0.98, 0.50 + 0.12 * min(f_feat["cycles"], 4) + 0.03 * min(f_feat["revs"], 4))
    elif f_feat["peak_pose"] >= thr.pose_threshold and max(frz_sc, shk_sc, ang_sc, post_sc) == 0.0 and f_feat["med_vel"] < 0.035:
        tease = min(0.85, 0.45 + 2.0 * (f_feat["peak_pose"] - thr.pose_threshold))
    max_e = max(frz_sc, ang_sc, shk_sc, joy_sc, tease, post_sc)
    calm = max(0.05, 1.0 - max_e) if max_e > 0 else 0.92
    if talk and ang_sc == 0.0 and frz_sc < 0.65 and shk_sc == 0.0 and post_sc == 0.0:
        calm = max(calm, 0.88)
    return (tease, calm)


def score_dual_regimes(
    f_feat: Dict[str, float], w_feat: Dict[str, float], thr: RegimeThresholds
) -> Dict[str, float]:
    """Fuse tight-face F gating with full-webcam W spike & posture_act scores."""
    frz_sc, ang_sc = _score_angry_and_freeze(f_feat, thr)
    w_frz, _ = _score_angry_and_freeze(w_feat, thr)
    f_shk, joy_sc = _score_shock_joy(f_feat, thr, frz_sc)
    w_shk, _ = _score_shock_joy(w_feat, thr, w_frz)
    shk_sc = max(f_shk, w_shk if (w_feat["z_max"] >= 4.0 or w_shk >= 0.70) else 0.0)
    post_sc = _score_posture(f_feat, w_feat, thr)
    if post_sc > 0.0:
        frz_sc = 0.0
        shk_sc *= 0.45
    tease, calm = _score_tease_and_calm(f_feat, thr, (frz_sc, ang_sc, shk_sc, joy_sc, post_sc))
    return {"calm_news": round(calm, 3), "stunned_freeze": round(frz_sc, 3), "playful_tease": round(tease, 3),
            "angry": round(ang_sc, 3), "joy_flex": round(joy_sc, 3), "shock_burst": round(shk_sc, 3), "posture_act": post_sc}
