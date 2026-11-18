"""Multi-anchor OBS webcam consensus picker for mid-chunk flashes and corner switches."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from video.pixel_tones import face_tone_fraction, green_chat_fraction
from video.dynamic_balance import decode_tile_box
from video.face_motion_metrics import compute_frame_delta
from video.motion_types import FaceBox, LayoutSegment, WindowBounds
from video.obs_layout import _crop_rgb_box, _probe_full_frames, _region_mad, detect_layout_cuts, detect_obs_layout, split_around_cuts

RankFn = Callable[[List[bytes], Sequence[tuple]], List[Tuple[bool, float, FaceBox]]]
_STRONG_ACTIVE_FLOOR = 0.16
_NEARBY_SB_WINDOW_SEC = 90.0
_CHAT_OVERLAP_WEIGHT = 0.65
_SB_STEADY_CAP = 0.19
_CENTER_CAM_BOX = FaceBox(0.22, 0.0, 0.56, 0.68, "fullscreen")
_CENTER_CAM_TONE_FLOOR = 0.25


def _parse_hhmmss(label: str) -> Optional[float]:
    """Convert HH:MM:SS or MM:SS timestamp label to seconds."""
    parts = label.strip().split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    if len(vals) == 2:
        return vals[0] * 60.0 + vals[1]
    return vals[0] * 3600.0 + vals[1] * 60.0 + vals[2]


def _filter_nearby_sb(sb_frames: Sequence[tuple], center_sec: float) -> Sequence[tuple]:
    """Return storyboard frames within window of center_sec when at least 3 match."""
    nearby = [
        f for f in sb_frames
        if (t := _parse_hhmmss(str(f[0]))) is not None and abs(t - center_sec) <= _NEARBY_SB_WINDOW_SEC
    ]
    return nearby if len(nearby) >= 3 else sb_frames


def _clean_probe_segment(raw: List[bytes]) -> List[bytes]:
    """Keep the longest contiguous non-cut segment from a raw full-frame probe."""
    if len(raw) < 2:
        return raw
    cuts = detect_layout_cuts(raw)
    if not cuts:
        return raw
    lo, hi = split_around_cuts(len(raw), cuts)
    seg = raw[lo:hi]
    return seg if len(seg) >= 2 else raw


def _mean_color_drift(means: Sequence[Tuple[float, float, float]]) -> float:
    """Return mean normalized RGB deviation across frames."""
    if not means:
        return 1.0
    mr = sum(m[0] for m in means) / len(means)
    mg = sum(m[1] for m in means) / len(means)
    mb = sum(m[2] for m in means) / len(means)
    return sum((abs(m[0] - mr) + abs(m[1] - mg) + abs(m[2] - mb)) / 765.0 for m in means) / len(means)


def _pixel_tone_stats(raws: Sequence[bytes]) -> Tuple[float, float, float]:
    """Compute (face_tone_fraction, color_drift, green_chat_fraction) across tile RGB buffers."""
    face_ratios, green_ratios, means = [], [], []
    for rgb in raws:
        n = len(rgb) // 3
        if n < 16:
            continue
        rs, gs, bs = rgb[0 : n * 3 : 3], rgb[1 : n * 3 : 3], rgb[2 : n * 3 : 3]
        face_ratios.append(face_tone_fraction(rgb))
        green_ratios.append(green_chat_fraction(rgb))
        means.append((sum(rs) / n, sum(gs) / n, sum(bs) / n))
    if not means:
        return 0.0, 1.0, 0.0
    return sum(face_ratios) / len(face_ratios), _mean_color_drift(means), sum(green_ratios) / len(green_ratios)


def _score_persistent_box(sb_frames: Sequence[tuple], box: FaceBox, fallback_mad: float) -> float:
    """Rank an active OBS corner by steady studio motion + face tones vs color drift/chat bars."""
    raws = [r for x in sb_frames[:12] if x and len(x) > 1 and (r := decode_tile_box(Path(x[1]), box))]
    if len(raws) < 2:
        return fallback_mad
    mads = [compute_frame_delta(raws[i - 1], raws[i])[0] for i in range(1, len(raws))]
    sb_mad = sum(mads) / len(mads)
    steady = sb_mad if sb_mad <= _SB_STEADY_CAP else max(0.02, _SB_STEADY_CAP - 1.5 * (sb_mad - _SB_STEADY_CAP))
    face_tone, drift, green = _pixel_tone_stats(raws)
    chat_bias = _CHAT_OVERLAP_WEIGHT if box.name == "bottom-right" else 1.0
    return chat_bias * steady * (0.04 + face_tone) / (0.015 + drift + 2.0 * green)


def _maybe_center_fallback(
    clean: Sequence[bytes],
    best: Tuple[FaceBox, float],
) -> Tuple[FaceBox, float]:
    """Promote fullscreen center crop when chosen corner lacks face and center shows active person."""
    box, score = best
    if not clean or len(clean[0]) < 48 * 48 * 3:
        return best
    inner = box.derive_tight_face()
    corner_tone = sum(face_tone_fraction(_crop_rgb_box(f, 48, inner)) for f in clean) / len(clean)
    if corner_tone >= 0.025:
        return best
    center_inner = _CENTER_CAM_BOX.derive_tight_face()
    center_tone = sum(face_tone_fraction(_crop_rgb_box(f, 48, center_inner)) for f in clean) / len(clean)
    center_mad = _region_mad(list(clean), 48, center_inner)
    if center_tone >= _CENTER_CAM_TONE_FLOOR and center_mad >= 0.008:
        return _CENTER_CAM_BOX, max(score, 0.25)
    return best


def _is_live_in_clean(clean: Sequence[bytes], box: FaceBox) -> bool:
    """Return True when the 6s probe shows skin without LiveChat green overlay bars."""
    crops = [_crop_rgb_box(f, 48, box.derive_tight_face()) for f in clean]
    tone = sum(face_tone_fraction(c) for c in crops) / len(crops)
    green = sum(green_chat_fraction(c) for c in crops) / len(crops)
    return tone >= 0.025 and green < 0.06


def _probe_best_active(
    source: Path | str,
    center_sec: int,
    sb_frames: Sequence[tuple],
    rank_fn: RankFn,
) -> Optional[Tuple[int, float, FaceBox]]:
    """Probe a short window around center_sec and return (active_count, quality_score, top_box)."""
    raw = _probe_full_frames(source, WindowBounds(max(0.0, center_sec - 2.0), center_sec + 4.0))
    clean = _clean_probe_segment(raw)
    if len(clean) < 2:
        return None
    active = [(item[2], _score_persistent_box(sb_frames, item[2], item[1])) for item in rank_fn(clean, sb_frames) if item[0]]
    if not active:
        return None
    live = [pair for pair in active if _is_live_in_clean(clean, pair[0])]
    best_box, best_score = _maybe_center_fallback(clean, max(live or active, key=lambda item: item[1]))
    return len(active), best_score, best_box


def _tally_anchor_winners(hits: Sequence[Tuple[float, FaceBox]]) -> Optional[FaceBox]:
    """Choose the corner winning the most anchors, breaking ties by highest persistence MAD."""
    if not hits:
        return None
    counts = Counter(box.name for _, box in hits)
    best_by_name: dict[str, Tuple[float, FaceBox]] = {}
    for mad, box in hits:
        prev = best_by_name.get(box.name)
        if prev is None or mad > prev[0]:
            best_by_name[box.name] = (mad, box)
    winner_name = max(best_by_name, key=lambda name: (counts[name], best_by_name[name][0]))
    return best_by_name[winner_name][1]


def pick_consensus_corner(
    source: Path | str,
    bounds: Tuple[int, int],
    sb_frames: Sequence[tuple],
    rank_fn: RankFn,
) -> Optional[FaceBox]:
    """Pick persistent OBS corner at midpoint; query 1/4 & 3/4 anchors when midpoint is ambiguous."""
    lo, hi = bounds
    span = max(0, hi - lo)
    mid = lo + span // 2
    mid_res = _probe_best_active(source, mid, sb_frames, rank_fn)
    if mid_res and mid_res[0] >= 2 and mid_res[1] >= _STRONG_ACTIVE_FLOOR:
        return mid_res[2]
    hits: List[Tuple[float, FaceBox]] = [(mid_res[1], mid_res[2])] if mid_res else []
    if span >= 30:
        for anchor in (lo + span // 4, lo + (3 * span) // 4):
            res = _probe_best_active(source, anchor, sb_frames, rank_fn)
            if res:
                hits.append((res[1], res[2]))
    return _tally_anchor_winners(hits)


def make_segment_layout_fn(
    sb_frames: Sequence[tuple],
    rank_fn: RankFn,
) -> Callable[..., LayoutSegment]:
    """Build a subwindow layout resolver backed by nearby storyboard persistence."""
    def _resolve(source: Path | str, bounds: WindowBounds, preferred: str = "auto") -> LayoutSegment:
        if preferred != "auto":
            return detect_obs_layout(source, bounds, preferred=preferred)
        center = (bounds.start_sec + bounds.end_sec) / 2.0
        sub_sb = _filter_nearby_sb(sb_frames, center)
        res = _probe_best_active(source, int(center), sub_sb, rank_fn)
        if res is not None:
            box = res[2]
            return LayoutSegment(box.name, box, box.derive_tight_face())
        obs = detect_obs_layout(source, bounds, preferred=preferred)
        if obs.webcam_box and obs.webcam_box.name != "auto-tracked":
            return obs
        return LayoutSegment("none", None, None)

    return _resolve
