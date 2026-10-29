from __future__ import annotations

from process.media.phonetic import phonetic_phrase_similarity
from process.media.types import ChunkMediaInput, MediaCandidate, load_media_catalog

SIMILARITY_THRESHOLD = 0.65


def _matches_alias(candidate: MediaCandidate, text: str) -> bool:
    return any(alias and alias in text for alias in candidate.aliases)


def _matches_garble(candidate: MediaCandidate, lines: tuple[str, ...]) -> bool:
    return any(
        pattern in line
        for line in lines
        for pattern in candidate.garble_patterns
        if pattern
    )


def _matches_phonetic(candidate: MediaCandidate, lines: tuple[str, ...]) -> bool:
    for phrase in candidate.canonical_phrases:
        if not phrase:
            continue
        if any(phonetic_phrase_similarity(line, phrase) >= SIMILARITY_THRESHOLD for line in lines):
            return True
    return False


def _is_candidate_active(candidate: MediaCandidate, media_input: ChunkMediaInput) -> bool:
    combined_chat = " ".join(media_input.livechat_lines)
    combined_raw = " ".join(media_input.raw_lines)
    if _matches_alias(candidate, combined_chat) or _matches_alias(candidate, combined_raw):
        return True
    if _matches_garble(candidate, media_input.raw_lines):
        return True
    return _matches_phonetic(candidate, media_input.raw_lines)


def identify_active_media(
    media_input: ChunkMediaInput,
    catalog: list[MediaCandidate] | None = None,
) -> list[MediaCandidate]:
    candidates = catalog if catalog is not None else load_media_catalog()
    return [c for c in candidates if _is_candidate_active(c, media_input)]
