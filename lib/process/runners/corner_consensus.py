"""Multi-anchor OBS webcam consensus picker for mid-chunk flashes and corner switches."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from video.pixel_tones import face_tone_fraction
from video.live_corner_score import (
    is_fullscreen_live,
    is_live_webcam_stats,
    measure_corner_stats,
)
from video.motion_types import FaceBox, LayoutSegment, WindowBounds
from video.obs_layout import _crop_rgb_box, _probe_full_frames, _region_mad, detect_layout_cuts, detect_obs_layout, split_around_cuts

RankFn = Callable[[List[bytes], Sequence[tuple]], List[Tuple[bool, float, FaceBox]]]
_STRONG_ACTIVE_FLOOR = 0.16
_CENTER_CAM_BOX = FaceBox(0.22, 0.0, 0.56, 0.68, "fullscreen")
_CENTER_CAM_TONE_FLOOR = 0.25


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


def _select_preferred_or_best(
    active: Sequence[Tuple[FaceBox, float]], preferred: Optional[FaceBox]
) -> Tuple[FaceBox, float]:
    """Keep preferred corner unless another live corner clearly outscores it."""
    best = max(active, key=lambda item: item[1])
    if preferred is not None:
        for box, score in active:
            if box.name == preferred.name and best[1] < score + 0.03:
                return (box, score)
    return best


def _probe_ranked_corner(
    source: Path | str,
    center_sec: int,
    resolver: Tuple[Sequence[tuple], RankFn, Optional[FaceBox]],
) -> Optional[Tuple[int, float, FaceBox]]:
    """Sample frames around center_sec, evaluate rank_fn, and apply continuity/fullscreen checks."""
    sb_frames, rank_fn, preferred = resolver
    raw = _probe_full_frames(source, WindowBounds(max(0.0, center_sec - 2.0), center_sec + 4.0))
    clean = _clean_probe_segment(raw)
    if len(clean) < 2:
        return None
    active = [(item[2], item[1]) for item in rank_fn(clean, sb_frames) if item[0]]
    if not active:
        return (1, 0.30, _CENTER_CAM_BOX) if is_fullscreen_live(clean) else None
    chosen = _select_preferred_or_best(active, preferred)
    best_box, best_score = _maybe_center_fallback(clean, chosen)
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
    """Pick live OBS corner at midpoint; query 1/4 & 3/4 anchors when multiple or weak boxes appear."""
    lo, hi = bounds
    span = max(0, hi - lo)
    mid_res = _probe_ranked_corner(source, lo + span // 2, (sb_frames, rank_fn, None))
    if mid_res and mid_res[0] == 1 and mid_res[1] >= _STRONG_ACTIVE_FLOOR:
        return mid_res[2]
    hits: List[Tuple[float, FaceBox]] = [(mid_res[1], mid_res[2])] if mid_res else []
    if span >= 30:
        for anchor in (lo + span // 4, lo + (3 * span) // 4):
            res = _probe_ranked_corner(source, anchor, (sb_frames, rank_fn, None))
            if res:
                hits.append((res[1], res[2]))
    return _tally_anchor_winners(hits)


def _validated_fallback_obs(obs: LayoutSegment, raw_clean: Sequence[bytes]) -> LayoutSegment:
    """Accept OBS fallback only when it is not auto-tracked and passes live metrics."""
    if not obs.webcam_box or obs.webcam_box.name == "auto-tracked":
        return LayoutSegment("none", None, None)
    if len(raw_clean) >= 2 and not is_live_webcam_stats(measure_corner_stats(raw_clean, obs.webcam_box)):
        return LayoutSegment("none", None, None)
    return obs


def make_segment_layout_fn(
    sb_frames: Sequence[tuple],
    rank_fn: RankFn,
    preferred_box: Optional[FaceBox] = None,
) -> Callable[..., LayoutSegment]:
    """Build a subwindow layout resolver preferring continuity while tracking quick switches."""
    def _resolve(source: Path | str, bounds: WindowBounds, preferred: str = "auto") -> LayoutSegment:
        if preferred != "auto":
            return detect_obs_layout(source, bounds, preferred=preferred)
        center = (bounds.start_sec + bounds.end_sec) / 2.0
        res = _probe_ranked_corner(source, int(center), (sb_frames, rank_fn, preferred_box))
        if res is not None:
            return LayoutSegment(res[2].name, res[2], res[2].derive_tight_face())
        obs = detect_obs_layout(source, bounds, preferred=preferred)
        raw = _clean_probe_segment(_probe_full_frames(source, bounds))
        return _validated_fallback_obs(obs, raw)

    return _resolve
