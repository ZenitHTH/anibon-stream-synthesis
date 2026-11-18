"""Telemetry-injected 6-mood + physical-act reaction VLM prompt, parser, and resolver."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from common.config import STAMP_COLLISION_SEC
from common.time import fmt_ts, parse_ts
from common.timestamps import sanitize_timestamp_line
from process.multimodal_situations import score_item_situations
from process.vision_verify import stamp_seconds
from video.audio_envelope import AudioBurstMetrics
from video.motion_types import MotionRegime

PROTECTED_MILESTONE_TAGS: Tuple[str, ...] = ("Gacha", "Victory", "Boss", "Ending", "Donation")
_REJECTED_CLASSES = ("calm_talking", "empty_chair_afk")
_STAMP_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]\s*(.*)$")


@dataclass(frozen=True)
class CoTriggerSignals:
    """Multi-modal co-triggers overriding silent-video suppression."""
    situation_score: float = 0.0
    chat_verdict: str = "QUIET"
    chat_peak_in_window: bool = False
    audio: Optional[AudioBurstMetrics] = None

    @property
    def has_any(self) -> bool:
        audio_hit = bool(self.audio and self.audio.has_audio_trigger)
        meme_hit = self.chat_verdict == "MEME_PULSE" and self.chat_peak_in_window
        return self.situation_score >= 2.0 or meme_hit or audio_hit


@dataclass(frozen=True)
class PromptContext:
    """Optional co-trigger and transcript context for reaction prompt building."""
    triggers: Optional[CoTriggerSignals] = None
    transcript_ctx: str = ""


@dataclass(frozen=True)
class ParseConstraints:
    """Bounds and confidence thresholds for VLM reaction response validation."""
    bounds: Tuple[int, int]
    min_conf: float = 0.6
    peak_motion: float = 0.0


@dataclass(frozen=True)
class ReactionVerifyResult:
    """Validated reaction onset snap and emotion classification result."""
    original: str
    updated: str
    snapped_sec: int
    emotion_class: str
    face_cue: str
    peak_motion: float
    confidence: float
    accepted: bool


def needs_reaction_verify(stamp: str, transcript_ctx: str = "", triggers: Optional[CoTriggerSignals] = None) -> bool:
    """Decide whether a stamp qualifies for reaction onset visual verification."""
    m = _STAMP_RE.match(stamp.strip())
    if m and m.group(2).strip() == "Reaction":
        return True
    if triggers is not None and triggers.has_any:
        return True
    return score_item_situations(transcript_ctx) >= 2.0 or score_item_situations(stamp) >= 2.0


def _format_telemetry(regime: MotionRegime, triggers: Optional[CoTriggerSignals]) -> str:
    """Format Dual-Box kinematic and audio telemetry lines for VLM prompt."""
    audio_z = triggers.audio.rms_z_max if (triggers and triggers.audio) else 0.0
    frames = ", ".join(f"[{k.role}@{k.ts} rel={k.rel_sec:.1f}s]" for k in regime.keyframes)
    return (
        f"Keyframes (W full webcam scene incl. chair + bed behind chair): {frames}\n"
        f"Telemetry: regime={regime.regime}, freeze_duration_sec={regime.freeze_duration_sec:.2f}, "
        f"freeze_drop_ratio={regime.freeze_drop_ratio:.2f}, webcam_z_max={regime.webcam_z_max:.2f}, "
        f"w_pose_shift={regime.w_pose_shift:.3f}, burst_width_sec={regime.burst_width_sec:.2f}, "
        f"audio_rms_z={audio_z:.2f}"
    )


def _calibration_rules() -> str:
    """Return compact Thai VLM mood and body/bed-pose calibration rules."""
    return (
        "Calibration:\n"
        "1) Startle recoil + narrow burst (webcam_z_max>=5.0) = shock (not joy_flex).\n"
        "2) Sustained drop (freeze_duration_sec>=2.0, freeze_drop_ratio>=2.0) with fixed stare = stunned_freeze (never confuse with calm news or empty chair).\n"
        "3) Deadpan/tilted rant with audio_rms_z spike or swearing = angry (vs playful_tease mugging).\n"
        "4) Inspect BOTH foreground chair AND bed/background behind chair: camera/desk gags (lean_into_cam, duck_under_desk, "
        "slump_on_desk, show_prop_to_cam, praying_bow) or getting up to lie_on_bed = physical_act (accepted; truthful Thai). "
        "If chair AND bed are empty with no gag = empty_chair_afk (never fabricate [Reaction])."
    )


def build_face_reaction_prompt(
    stamp: str, regime: MotionRegime, context: Optional[PromptContext] = None
) -> str:
    """Build telemetry-injected VLM prompt for webcam reaction onset and mood."""
    ctx = context or PromptContext()
    telemetry = _format_telemetry(regime, ctx.triggers)
    rules = _calibration_rules()
    transcript = f"\nTranscript: {ctx.transcript_ctx[:600]}" if ctx.transcript_ctx else ""
    return (
        f"Draft timestamp: {stamp}{transcript}\n{telemetry}\n{rules}\n"
        "Inspect BOTH [WEBCAM STORYBOARD] / [WEBCAM ONLY] panels (left-to-right top-to-bottom; face/hands/bed for onset+emotion) "
        "AND [STORYBOARD SCREEN] frames (full game/web screen for what triggered the reaction). "
        "Preserve accurate proper nouns from Draft timestamp. "
        "Image 1 is [pre_onset_baseline] within 15s of onset. Return JSON ONLY:\n"
        '{"snapped_ts":"HH:MM:SS","emotion_class":"shock|stunned_freeze|playful_tease|angry|'
        'joy_flex|physical_act|calm_talking|empty_chair_afk","pose_cue":"none|lean_into_cam|'
        'duck_under_desk|slump_on_desk|show_prop_to_cam|praying_bow|lie_on_bed",'
        '"face_cue":"<cue>","tag":"Reaction|Talk","description":"<Thai Caveman headline>","confidence":0.0}'
    )


def _reject(original: str, meta: Tuple[str, float], peak: float) -> ReactionVerifyResult:
    """Build an unaccepted ReactionVerifyResult preserving the original stamp."""
    emotion, conf = meta
    return ReactionVerifyResult(original, original, stamp_seconds(original), emotion, "", peak, conf, False)


def _resolve_tag(orig_tag: str, req_tag: str) -> str:
    """Protect milestone tags from downgrading to Reaction or Talk."""
    if orig_tag in PROTECTED_MILESTONE_TAGS:
        return orig_tag
    cleaned = req_tag.strip()
    return cleaned if cleaned in ("Reaction", "Talk") else orig_tag


def _extract_json_payload(raw: str) -> Optional[Dict[str, object]]:
    """Extract first JSON object from VLM response text."""
    if not raw or not isinstance(raw, str):
        return None
    jm = re.search(r"(\{.*\})", raw, re.DOTALL)
    if not jm:
        return None
    try:
        data = json.loads(jm.group(1))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _parse_valid_sec(data: Dict[str, object], original: str, bounds: Tuple[int, int]) -> Optional[int]:
    """Parse snapped_ts and reject values outside [lo, hi] bounds."""
    snapped_raw = str(data.get("snapped_ts") or "").strip()
    sec = parse_ts(snapped_raw) if re.match(r"^\d{2}:\d{2}:\d{2}$", snapped_raw) else stamp_seconds(original)
    lo, hi = bounds
    return sec if (sec is not None and lo <= sec <= hi) else None


def parse_snapped_response(raw: str, original: str, constraints: ParseConstraints) -> ReactionVerifyResult:
    """Validate VLM JSON reaction response against bounds, milestones, and empty-chair guards."""
    data = _extract_json_payload(raw)
    if not data:
        return _reject(original, ("parse_error", 0.0), constraints.peak_motion)
    emotion = str(data.get("emotion_class") or "").strip()
    conf = float(data.get("confidence") or 0.0)
    if emotion in _REJECTED_CLASSES or conf < constraints.min_conf:
        return _reject(original, (emotion or "low_conf", conf), constraints.peak_motion)
    sec = _parse_valid_sec(data, original, constraints.bounds)
    m = _STAMP_RE.match(original.strip())
    if sec is None or not m:
        return _reject(original, (emotion, conf), constraints.peak_motion)
    tag = _resolve_tag(m.group(2).strip(), str(data.get("tag") or m.group(2)))
    desc = _STAMP_RE.sub(r"\3", str(data.get("description") or m.group(3)).strip()).strip()
    updated = sanitize_timestamp_line(f"{fmt_ts(sec)} - [{tag}] {desc}") or original
    cue = str(data.get("pose_cue") or data.get("face_cue") or "").strip()
    return ReactionVerifyResult(original, updated, sec, emotion, cue, constraints.peak_motion, conf, True)


def resolve_monotonic_snap(results: List[ReactionVerifyResult], collision_sec: int = STAMP_COLLISION_SEC) -> List[str]:
    """Resolve snapped timestamps monotonically while preventing < collision_sec collisions."""
    resolved: List[Tuple[int, str]] = []
    for r in results:
        cand_sec = r.snapped_sec if r.accepted else stamp_seconds(r.original)
        cand_str = r.updated if r.accepted else r.original
        if resolved and (cand_sec - resolved[-1][0]) < collision_sec:
            orig_sec = stamp_seconds(r.original)
            if (orig_sec - resolved[-1][0]) >= collision_sec:
                cand_sec, cand_str = orig_sec, r.original
            else:
                continue
        resolved.append((cand_sec, cand_str))
    return [line for _, line in resolved]
