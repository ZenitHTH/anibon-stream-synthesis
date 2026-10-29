from __future__ import annotations

from process.media.types import ChunkMediaInput, MediaTriggerResult

TURN_THRESHOLD = 6
SCORE_THRESHOLD = 2.0
SCORE_TURNS = 0.75
SCORE_TRANSCRIPT_CUE = 1.5
SCORE_CHAT_CUE = 1.0

MEDIA_INTENT_CUES: tuple[str, ...] = (
    "เปิดเพลง",
    "ฟังเพลง",
    "เพลงที่ผมจะร้อง",
    "เพลงนี้",
    "ขอเพลง",
    "ฟังศิลปะ",
    "เวอร์ชั่นรีมิก",
    "คอรัส",
    "อินโทร",
    "[เพลง]",
    "♪",
    "โลกุตตระ",
    "ร้องเลียนแบบ",
    "เพลงที่เพราะที่สุด",
)

CHAT_MEDIA_CUES: tuple[str, ...] = (
    "เพลง",
    "ไม้ร่ม",
    "อาจารย์ไม้ร่ม",
    "ลุงตู่",
    "คืนความสุข",
    "จุฬา",
    "ร้องสด",
    "เปิดคลิป",
    "รีมิกซ์",
    "remix",
)


def _count_turn_markers(lines: tuple[str, ...]) -> int:
    return sum(1 for line in lines if ">>" in line)


def _find_transcript_cues(lines: tuple[str, ...]) -> list[str]:
    combined = " ".join(lines)
    return [cue for cue in MEDIA_INTENT_CUES if cue in combined]


def _find_chat_hints(chat_lines: tuple[str, ...]) -> list[str]:
    combined = " ".join(chat_lines)
    return [cue for cue in CHAT_MEDIA_CUES if cue in combined]


def detect_media_trigger(media_input: ChunkMediaInput) -> MediaTriggerResult:
    score = 0.0
    reasons: list[str] = []
    if _count_turn_markers(media_input.raw_lines) >= TURN_THRESHOLD:
        score += SCORE_TURNS
        reasons.append(f"turn_density>={TURN_THRESHOLD}")
    trans_cues = _find_transcript_cues(media_input.raw_lines)
    if trans_cues:
        score += SCORE_TRANSCRIPT_CUE
        reasons.append(f"transcript_cues:{','.join(trans_cues[:3])}")
    chat_hints = _find_chat_hints(media_input.livechat_lines)
    if chat_hints:
        score += SCORE_CHAT_CUE
        reasons.append(f"chat_hints:{','.join(chat_hints[:3])}")
    return MediaTriggerResult(
        triggered=score >= SCORE_THRESHOLD,
        score=score,
        reasons=tuple(reasons),
        chat_hints=tuple(chat_hints),
    )
