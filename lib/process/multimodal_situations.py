"""Situation-aware keyframe cue scoring, silence-gap detection, and HUD delta helpers."""
from __future__ import annotations

from typing import List, Optional, Tuple

DEICTIC_CUES: Tuple[str, ...] = (
    "ดูอันนี้", "ดูนี่", "เนี่ยดูดิ", "เปิดดู", "ในจอ", "ตรงนี้", "จุดนี้", "นี่ไง",
    "ดูคลิป", "ตัวละครนี้", "สกินนี้", "การ์ดนี้", "เกมนี้", "หน้านี้", "รูปนี้",
    "คลิปนี้", "ภาพนี้", "[?]",
)

BOSS_COMBAT_CUES: Tuple[str, ...] = (
    "สู้บอส", "เจอบอส", "ปะทะ", "เฟสสอง", "เฟส 2", "ชนะแล้ว", "ปราบได้",
    "ผ่านแล้ว", "บอสตัวนี้", "ท่านี้",
)

GEAR_GACHA_UI_CUES: Tuple[str, ...] = (
    "อาวุธนี้", "อาวุธใหม่", "อัปเกรด", "อัปสกิล", "สกิลนี้", "ของชิ้นนี้",
    "เปิดตู้", "กดกาชา", "ออกทอง", "ออกรุ้ง", "หลุดเรท",
)

TOPIC_SHIFT_CUES: Tuple[str, ...] = (
    "ข่าวต่อไป", "เรื่องต่อไป", "มาดูตัวอย่าง", "เทรลเลอร์", "ประกาศใหม่",
    "เปิดตัว", "เปลี่ยนเกม",
)

EMOTION_REACTION_CUES: Tuple[str, ...] = (
    "เห้ย", "เชี่ย", "แม่ง", "ว้าว", "โอ้โห", "ห๊ะ", "ตกใจ", "ขนลุก",
    "ขิง", "เกลือ", "เอาจริงดิ", "โคตรโหด", "หัวร้อน", "เดือดจัด",
    "ฟิวส์ขาด", "บ้าไปแล้ว", "พัง", "บัค",
)

SOFT_DEICTIC_CUES: Tuple[str, ...] = (
    "อันนี้", "ตัวนี้", "แบบนี้", "หน้าตา", "ใครเนี่ย", "อะไรเนี่ย",
    "โอ้โห", "เฮ้ย", "โห", "ดูดิ", "เนี่ย",
)

STRONG_VISUAL_CUES: Tuple[str, ...] = (
    DEICTIC_CUES
    + BOSS_COMBAT_CUES
    + GEAR_GACHA_UI_CUES
    + TOPIC_SHIFT_CUES
    + EMOTION_REACTION_CUES
)

INCOMPLETE_CONTEXT_CUES: Tuple[str, ...] = STRONG_VISUAL_CUES + SOFT_DEICTIC_CUES

_WEIGHTED_GROUPS: Tuple[Tuple[Tuple[str, ...], float], ...] = (
    (DEICTIC_CUES, 3.0),
    (BOSS_COMBAT_CUES, 2.5),
    (GEAR_GACHA_UI_CUES, 2.0),
    (TOPIC_SHIFT_CUES, 2.0),
    (EMOTION_REACTION_CUES, 2.0),
    (SOFT_DEICTIC_CUES, 1.0),
)


def score_item_situations(text: str, pinned_only: bool = False) -> float:
    """Score a transcript line across visual livestream situations."""
    if not text:
        return 0.0
    score = 0.0
    groups = _WEIGHTED_GROUPS[:-1] if pinned_only else _WEIGHTED_GROUPS
    for cues, weight in groups:
        for cue in cues:
            if cue in text:
                score += weight
    return score


def detect_silence_gap_seconds(
    items: Optional[List[dict]], start_sec: int, end_sec: int, min_gap_sec: int = 20
) -> List[Tuple[float, int]]:
    """Detect non-speech gaps (cutscenes, trailers, intense boss action) in dense chunks."""
    if not items or len(items) < 8:
        return []
    in_window = [
        int(it.get("start", 0))
        for it in items
        if start_sec <= int(it.get("start", 0)) <= end_sec
    ]
    gaps: List[Tuple[float, int]] = []
    for prev_s, next_s in zip(in_window, in_window[1:]):
        gap = next_s - prev_s
        if gap >= min_gap_sec:
            mid = (prev_s + next_s) // 2
            gaps.append((0.85 + min(0.14, gap / 300.0), mid))
    return gaps


def collect_situational_candidates(
    items: Optional[List[dict]],
    start_sec: int,
    end_sec: int,
    pinned_only: bool = False,
) -> List[Tuple[float, int]]:
    """Collect scored (priority, sec) candidates from spoken cues and silence gaps."""
    candidates: List[Tuple[float, int]] = []
    for it in (items or []):
        sec = int(it.get("start", 0))
        if start_sec <= sec <= end_sec:
            score = score_item_situations(it.get("text", ""), pinned_only=pinned_only)
            if score > 0:
                candidates.append((score, sec))
    candidates.extend(detect_silence_gap_seconds(items, start_sec, end_sec))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates


def select_spaced_seconds(
    scored_candidates: List[Tuple[float, int]],
    existing: List[int],
    min_spacing: int,
    max_count: int,
) -> List[int]:
    """Pick candidate seconds respecting minimum temporal spacing up to max_count."""
    chosen = list(existing)
    for _, sec in scored_candidates:
        if len(chosen) >= max_count:
            break
        if all(abs(sec - s) >= min_spacing for s in chosen):
            chosen.append(sec)
    return chosen


def compute_regional_rgb_delta(bytes_a: bytes, bytes_b: bytes) -> float:
    """Blend whole-frame diff with 3-band (top HUD, center, bottom HUD) max diff."""
    total_diff = sum(abs(b1 - b2) for b1, b2 in zip(bytes_a, bytes_b))
    global_delta = total_diff / (len(bytes_a) * 255.0)
    band_size = len(bytes_a) // 3
    if band_size <= 0:
        return global_delta
    band_deltas = [
        sum(abs(b1 - b2) for b1, b2 in zip(bytes_a[i : i + band_size], bytes_b[i : i + band_size]))
        / (band_size * 255.0)
        for i in range(0, band_size * 3, band_size)
    ]
    return max(global_delta, 0.70 * max(band_deltas))
