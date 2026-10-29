from __future__ import annotations

import re

from process.media.identifier import identify_active_media
from process.media.phonetic import phonetic_phrase_similarity
from process.media.trigger import detect_media_trigger
from process.media.types import (
    ChunkMediaInput,
    MediaCandidate,
    SeparatedSegment,
)

BOAT_MARKERS: tuple[str, ...] = (
    "แป๊บนึง",
    "ใครไม่พร้อม",
    "ใครได้บอก",
    "ออกจากช่องกู",
    "ออกจากห้อง",
    "ไอ้สัตว์",
    "ไอ้เหี้ย",
    "เดี๋ยวนะ",
    "กูมีเวท",
    "ผมมีเวท",
    "เไม่ได้รักไง",
    "พี่ไม่ได้รักไง",
    "เค้าไม่เข้าใจไง",
    "ก็ไม่เข้าใจไง",
    "ช่องแชท",
    "กูว่ากู",
    "กูกลาย",
    "เผลอลบดาบ",
    "สติเริ่มหลุด",
)


def _parse_line(line: str) -> tuple[str, str]:
    m = re.match(r"^\((\d{2}:\d{2}:\d{2})\)\s*(.*)$", line.strip())
    if not m:
        return "", line.strip().lstrip("> ").strip()
    return m.group(1), m.group(2).lstrip("> ").strip()


def _is_gameplay(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords if kw)


def _match_media(text: str, candidate: MediaCandidate) -> bool:
    if any(len(g) >= 4 and g in text for g in candidate.garble_patterns if g):
        return True
    for p in candidate.canonical_phrases:
        if not p or len(p) < 4:
            continue
        if p in text or phonetic_phrase_similarity(text, p) >= 0.65:
            return True
    return False


def _find_candidate(text: str, candidates: list[MediaCandidate]) -> MediaCandidate | None:
    return next((c for c in candidates if _match_media(text, c)), None)


def _find_midline_split(
    text: str,
    candidates: list[MediaCandidate],
) -> tuple[str, str, MediaCandidate] | None:
    earliest_idx = -1
    for marker in BOAT_MARKERS:
        idx = text.find(marker)
        if idx >= 4 and (earliest_idx < 0 or idx < earliest_idx):
            earliest_idx = idx
    if earliest_idx < 0:
        return None
    prefix = text[:earliest_idx].strip()
    suffix = text[earliest_idx:].strip()
    matched = _find_candidate(prefix, candidates)
    if not matched:
        return None
    return prefix, suffix, matched


def _classify_segment(
    ts: str,
    text: str,
    cand: MediaCandidate | None,
) -> SeparatedSegment:
    if cand:
        gt = f"เนื้อเพลง/เสียงคลิป: {cand.title}"
        return SeparatedSegment(ts, "MEDIA_AUDIO", text, gt, cand.title)
    return SeparatedSegment(ts, "BOAT_SPEECH", text, text, "")


def _process_line(
    line: str,
    candidates: list[MediaCandidate],
    keywords: tuple[str, ...],
) -> list[SeparatedSegment]:
    ts, text = _parse_line(line)
    if not text:
        return []
    if any(text.startswith(m) for m in BOAT_MARKERS):
        label = "BOAT_GAMEPLAY" if _is_gameplay(text, keywords) else "BOAT_SPEECH"
        return [SeparatedSegment(ts, label, text, text, "")]
    split = _find_midline_split(text, candidates)
    if split:
        prefix, suffix, cand = split
        s1 = SeparatedSegment(ts, "MEDIA_AUDIO", prefix, f"เนื้อเพลง/เสียงคลิป: {cand.title}", cand.title)
        label2 = "BOAT_GAMEPLAY" if _is_gameplay(suffix, keywords) else "BOAT_SPEECH"
        s2 = SeparatedSegment(ts, label2, suffix, suffix, "")
        return [s1, s2]
    if _is_gameplay(text, keywords):
        return [SeparatedSegment(ts, "BOAT_GAMEPLAY", text, text, "")]
    matched = _find_candidate(text, candidates)
    return [_classify_segment(ts, text, matched)]


def separate_chunk_media(
    media_input: ChunkMediaInput,
    candidates: list[MediaCandidate] | None = None,
) -> list[SeparatedSegment]:
    active = candidates if candidates is not None else identify_active_media(media_input)
    segments: list[SeparatedSegment] = []
    for line in media_input.raw_lines:
        segments.extend(_process_line(line, active, media_input.gameplay_keywords))
    return segments


def _format_segment_line(seg: SeparatedSegment) -> str:
    ts_prefix = f"({seg.timestamp}) " if seg.timestamp else ""
    if seg.label == "MEDIA_AUDIO":
        return f"- {ts_prefix}[MEDIA_AUDIO: {seg.media_title}] {seg.ground_truth} (Raw: {seg.raw_text})"
    return f"- {ts_prefix}[{seg.label}] {seg.raw_text}"


def _build_block_header(titles: str) -> list[str]:
    return [
        "## DETECTED MEDIA & LYRIC SEPARATION (GROUND TRUTH)",
        f"> Active Media/Song: {titles}",
        "> CRITICAL RULE: Lines marked [MEDIA_AUDIO] are external audio / song lyrics playing in background. "
        "NEVER attribute lyrics or ASR-garbled singing to Pu Boat's own speech! "
        "Pu Boat's actual spoken commentary is marked [BOAT_SPEECH] or [BOAT_GAMEPLAY].",
        "",
    ]


def build_media_separation_prompt_block(media_input: ChunkMediaInput) -> str:
    if not detect_media_trigger(media_input).triggered:
        return ""
    candidates = identify_active_media(media_input)
    if not candidates:
        return ""
    segments = separate_chunk_media(media_input, candidates)
    if not any(s.label == "MEDIA_AUDIO" for s in segments):
        return ""
    lines = _build_block_header(", ".join(c.title for c in candidates))
    lines.extend(_format_segment_line(s) for s in segments)
    return "\n".join(lines)

