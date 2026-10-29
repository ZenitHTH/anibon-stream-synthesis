from __future__ import annotations

from process.media.types import ChunkMediaInput, MediaTriggerResult

TURN_THRESHOLD = 6
SCORE_THRESHOLD = 2.0
SCORE_TURNS = 0.75
SCORE_TRANSCRIPT_CUE = 1.5
SCORE_CHAT_GENERIC = 1.0
SCORE_CHAT_TITLE = 1.0

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
    "ผีไม่ได้ดักเจ้า",
    "พี่ไม่ได้ดักเจ้า",
    "พี่ไม่รักน้องเจ้า",
    "คืนความสุข",
    "เราจะทำตามสัญญา",
    "มหาจุฬาลงกรณ์",
    "น้ำใจน้องพี่สีชมพู",
)

CHAT_GENERIC_CUES: tuple[str, ...] = (
    "เพลง",
    "ร้องสด",
    "เปิดคลิป",
    "รีมิกซ์",
    "remix",
)

CHAT_TITLE_CUES: tuple[str, ...] = (
    "ไม้ร่ม",
    "อาจารย์ไม้ร่ม",
    "ลุงตู่",
    "คืนความสุข",
    "จุฬา",
)


def _count_turn_markers(lines: tuple[str, ...]) -> int:
    return sum(1 for line in lines if ">>" in line)


def _find_transcript_cues(lines: tuple[str, ...]) -> list[str]:
    combined = " ".join(lines)
    return [cue for cue in MEDIA_INTENT_CUES if cue in combined]


def _find_chat_hints(chat_lines: tuple[str, ...]) -> list[str]:
    combined = " ".join(chat_lines)
    all_cues = CHAT_GENERIC_CUES + CHAT_TITLE_CUES
    return [cue for cue in all_cues if cue in combined]


def _calculate_chat_score(chat_lines: tuple[str, ...]) -> float:
    chat_str = " ".join(chat_lines)
    generic = SCORE_CHAT_GENERIC if any(c in chat_str for c in CHAT_GENERIC_CUES) else 0.0
    title = SCORE_CHAT_TITLE if any(c in chat_str for c in CHAT_TITLE_CUES) else 0.0
    return generic + title


def detect_media_trigger(media_input: ChunkMediaInput) -> MediaTriggerResult:
    score = _calculate_chat_score(media_input.livechat_lines)
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
        reasons.append(f"chat_hints:{','.join(chat_hints[:3])}")
    return MediaTriggerResult(score >= SCORE_THRESHOLD, score, tuple(reasons), tuple(chat_hints))
