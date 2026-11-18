"""Dual-Box co-triggered webcam reaction verification orchestrator."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.config import (
    DEFAULT_MODEL, FACE_MAX_FRAMES, FACE_MOTION_THRESHOLD, ONSET_SNAP_POST_SEC,
    ONSET_SNAP_PRE_SEC, REACTION_STORYBOARD_FRAMES, STAMP_COLLISION_SEC, WEBCAM_CORNER,
)
from common.lmstudio import resolve_endpoint
from common.log import format_duration, log_info, log_ok, log_stage, log_warn
from process.multimodal import build_multimodal_content, call_multimodal
from process.reaction_io import (
    CoTriggerContext, ReactionRunConfig, collect_co_triggers, load_chunk_context, load_reaction_log,
    log_reaction_dispatch, log_reaction_result, resolve_reaction_audio_source, resolve_reaction_source,
    result_from_cache, result_to_cache, save_reaction_log, sync_raw_timestamps,
)
from process.reaction_prompt import (
    PROTECTED_MILESTONE_TAGS, CoTriggerSignals, ParseConstraints, PromptContext, ReactionVerifyResult,
    build_face_reaction_prompt, needs_reaction_verify, parse_snapped_response, resolve_monotonic_snap,
)
from process.vision_verify import stamp_seconds
from video.face_motion import FrameExportSpec, expand_reaction_keyframes, export_vlm_keyframes, extract_dual_motion_series, pick_storyboard_keyframes
from video.webcam_storyboard import pack_exported_webcam_storyboard
from video.face_motion_metrics import classify_dual_regime
from video.motion_types import LayoutSegment, MotionRegime, RegimeThresholds, WindowBounds
from video.obs_layout import detect_obs_layout


@dataclass(frozen=True)
class VerifyOptions:
    """Injected dependencies and thresholds for verify_reaction_stamps."""
    source: Optional[Path | str] = None
    audio_source: Optional[Path | str] = None
    endpoint: str = ""
    model: str = DEFAULT_MODEL
    preferred_corner: str = WEBCAM_CORNER
    face_threshold: float = FACE_MOTION_THRESHOLD
    context_fn: Optional[Callable[[int], str]] = None
    call_fn: Optional[Callable[..., str]] = None
    layout_fn: Optional[Callable[..., LayoutSegment]] = None
    motion_fn: Optional[Callable[..., tuple]] = None
    export_fn: Optional[Callable[..., Dict[str, object]]] = None
    audio_fn: Optional[Callable[..., Any]] = None


@dataclass(frozen=True)
class _StampEval:
    """Bundled per-stamp evaluation inputs for VLM verification."""
    idx: int
    stamp: str
    bounds: WindowBounds
    regime: MotionRegime
    layout: LayoutSegment
    triggers: CoTriggerSignals
    transcript_ctx: str


def _is_valid_source(source: Optional[Path | str]) -> bool:
    """Check whether source is an accessible URL or existing local file."""
    return bool(source) and (str(source).startswith(("http://", "https://")) or Path(str(source)).is_file())


def _unchanged(stamp: str) -> ReactionVerifyResult:
    """Return an unaccepted ReactionVerifyResult keeping original stamp."""
    return ReactionVerifyResult(stamp, stamp, stamp_seconds(stamp), "unchanged", "", 0.0, 0.0, False)


def _build_reaction_frames(wb_items: List[tuple], sb_exported: Dict[str, object]) -> List[tuple]:
    """Combine webcam storyboard/frames and full-screen storyboard frames for VLM."""
    sb = [
        (f["ts"], Path(f["path"]), f["b64"], f"STORYBOARD SCREEN ({f.get('role') or 'screen'})")
        for f in (sb_exported.get("frames") or ())
    ]
    return wb_items + sb


def _export_reaction_pair(ev: _StampEval, workspace: Path, opts: VerifyOptions) -> Tuple[List[tuple], dict]:
    """Export dynamically balanced webcam storyboard vs full-screen storyboard frames."""
    export_fn = opts.export_fn or export_vlm_keyframes
    out_dir = workspace / "frames_reaction"
    high_wc = ev.regime.regime in ("posture_act", "shock_burst", "angry", "joy_flex") or ev.regime.webcam_z_max >= 5.0 or ev.regime.w_pose_shift >= 0.14
    wb_cap = FACE_MAX_FRAMES if high_wc else min(4, FACE_MAX_FRAMES)
    sb_cap = min(2, REACTION_STORYBOARD_FRAMES) if high_wc else REACTION_STORYBOARD_FRAMES
    wb_kfs = expand_reaction_keyframes(ev.regime.keyframes, wb_cap)
    wb_exp = export_fn(opts.source, FrameExportSpec(wb_kfs, ev.layout.webcam_box, out_dir, f"rx_{ev.idx:03d}", out_size=320))
    wb_items = pack_exported_webcam_storyboard(wb_exp, out_dir / f"wb_sheet_{ev.idx:03d}.jpg")
    sb_exp: Dict[str, object] = {"frames": [], "strip_path": None}
    if ev.layout.layout != "fullscreen":
        sb_kfs = pick_storyboard_keyframes(ev.regime.keyframes, sb_cap)
        sb_exp = export_fn(opts.source, FrameExportSpec(sb_kfs, None, out_dir, f"sb_{ev.idx:03d}", out_size=320))
    return wb_items, sb_exp


def _run_vlm_on_w_frames(ev: _StampEval, workspace: Path, opts: VerifyOptions) -> ReactionVerifyResult:
    """Export expanded webcam storyboard + screen context frames and query VLM."""
    wb_items, sb_exp = _export_reaction_pair(ev, workspace, opts)
    kf_list = _build_reaction_frames(wb_items, sb_exp)
    if not kf_list:
        log_warn("reaction", f"[{ev.idx + 1:02d}] {ev.stamp[:8]} | keyframe export empty -> kept original")
        return _unchanged(ev.stamp)
    aud_z = ev.triggers.audio.rms_z_max if ev.triggers.audio else 0.0
    hdr = f"[{ev.idx + 1:02d}] {ev.stamp[:8]} | layout={ev.layout.layout} | {ev.regime.regime} (W_z={ev.regime.webcam_z_max:.1f}, aud_z={aud_z:.1f})"
    log_reaction_dispatch(hdr, wb_items, sb_exp)
    prompt = build_face_reaction_prompt(ev.stamp, ev.regime, PromptContext(ev.triggers, ev.transcript_ctx))
    raw = (opts.call_fn or call_multimodal)(opts.endpoint, opts.model, build_multimodal_content(prompt, kf_list))
    res = parse_snapped_response(raw, ev.stamp, ParseConstraints((int(ev.bounds.start_sec), int(ev.bounds.end_sec)), peak_motion=ev.regime.webcam_z_max))
    log_reaction_result(ev.idx, ev.stamp, res)
    return res


def _eval_kinematics(idx: int, stamp: str, ctx: tuple) -> ReactionVerifyResult:
    """Run layout detection, Dual-Box kinematics, and co-trigger VLM gate."""
    workspace, opts, triggers, transcript_ctx = ctx
    sec = stamp_seconds(stamp)
    bounds = WindowBounds(max(0.0, sec - ONSET_SNAP_PRE_SEC), sec + ONSET_SNAP_POST_SEC)
    layout = (opts.layout_fn or detect_obs_layout)(opts.source, bounds, preferred=opts.preferred_corner)
    if layout.webcam_box is None:
        log_warn("reaction", f"[{idx + 1:02d}] {stamp[:8]} | layout=none -> kept original")
        return _unchanged(stamp)
    f_s, w_s, _ = (opts.motion_fn or extract_dual_motion_series)(opts.source, bounds, layout)
    regime = classify_dual_regime(f_s, w_s, RegimeThresholds(motion_threshold=opts.face_threshold))
    if not regime.trigger_vlm and not triggers.has_any:
        log_info("reaction", f"[{idx + 1:02d}] {stamp[:8]} | layout={layout.layout} | low-motion (W_z={regime.webcam_z_max:.1f}) -> kept original")
        return _unchanged(stamp)
    return _run_vlm_on_w_frames(_StampEval(idx, stamp, bounds, regime, layout, triggers, transcript_ctx), workspace, opts)


def _evaluate_stamp(idx: int, stamp: str, ctx: tuple) -> ReactionVerifyResult:
    """Evaluate one timestamp with cache lookup, co-triggers, and kinematics."""
    workspace, opts, cache = ctx
    if stamp in cache:
        res = result_from_cache(stamp, cache[stamp])
        log_info("reaction", f"[{idx + 1:02d}] {stamp[:8]} | CACHED -> {res.updated[:8]} ({res.emotion_class or 'kept'})")
        return res
    sec = stamp_seconds(stamp)
    transcript_ctx = (opts.context_fn or (lambda s: load_chunk_context(workspace, s)))(sec)
    aud_src = opts.audio_source if opts.audio_source is not None else opts.source
    triggers = collect_co_triggers(workspace, sec, CoTriggerContext(transcript_ctx, aud_src, opts.audio_fn))
    if not needs_reaction_verify(stamp, transcript_ctx, triggers):
        return _unchanged(stamp)
    res = _eval_kinematics(idx, stamp, (workspace, opts, triggers, transcript_ctx))
    cache[stamp] = result_to_cache(res)
    return res


def verify_reaction_stamps(
    stamps: List[str], workspace: Path, options: Optional[VerifyOptions] = None
) -> List[str]:
    """Run Dual-Box + co-triggered reaction verification and resolve monotonically."""
    opts = options or VerifyOptions()
    ws = Path(workspace)
    if not stamps or not _is_valid_source(opts.source):
        return list(stamps)
    t0 = time.monotonic()
    log_stage(f"PASS 2 :: WEBCAM REACTION VERIFY ({len(stamps)} stamps, corner={opts.preferred_corner})")
    log_path = ws / "reaction_verify_log.json"
    cache = load_reaction_log(log_path)
    results = [_evaluate_stamp(i, s, (ws, opts, cache)) for i, s in enumerate(stamps)]
    save_reaction_log(log_path, cache)
    snapped = sum(1 for r in results if r.accepted)
    resolved = resolve_monotonic_snap(results, collision_sec=STAMP_COLLISION_SEC)
    log_ok("reaction", f"summary: checked={len(stamps)}, snapped={snapped}, elapsed={format_duration(time.monotonic() - t0)}")
    return resolved


def apply_reaction_verify(stamps: List[str], workspace: Path, runtime: Any) -> List[str]:
    """Apply reaction onset verification when --reaction-verify is active."""
    args = runtime.args if isinstance(runtime, ReactionRunConfig) else runtime
    if not getattr(args, "reaction_verify", False):
        return stamps
    ws = Path(workspace)
    source = resolve_reaction_source(ws, args)
    if not _is_valid_source(source):
        return stamps
    model = (runtime.model if isinstance(runtime, ReactionRunConfig) else "") or getattr(args, "vision_model", None) or DEFAULT_MODEL
    opts = VerifyOptions(
        source=source, audio_source=resolve_reaction_audio_source(ws, args) or source,
        endpoint=resolve_endpoint(getattr(args, "endpoint", None)), model=model,
        preferred_corner=getattr(args, "webcam_corner", WEBCAM_CORNER),
        face_threshold=float(getattr(args, "face_threshold", FACE_MOTION_THRESHOLD)),
    )
    verified = verify_reaction_stamps(stamps, ws, opts)
    if len(verified) == len(stamps):
        sync_raw_timestamps(ws, {o: u for o, u in zip(stamps, verified) if o != u})
    return verified


__all__ = [
    "PROTECTED_MILESTONE_TAGS", "CoTriggerContext", "CoTriggerSignals", "ParseConstraints",
    "PromptContext", "ReactionRunConfig", "ReactionVerifyResult", "VerifyOptions",
    "apply_reaction_verify", "build_face_reaction_prompt", "collect_co_triggers",
    "needs_reaction_verify", "parse_snapped_response", "resolve_monotonic_snap",
    "verify_reaction_stamps",
]
