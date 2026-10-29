from __future__ import annotations

from process.media.identifier import identify_active_media
from process.media.phonetic import phonetic_phrase_similarity, thai_phonetic_skeleton
from process.media.separator import (
    build_media_separation_prompt_block,
    separate_chunk_media,
)
from process.media.trigger import detect_media_trigger
from process.media.types import (
    ChunkMediaInput,
    MediaCandidate,
    MediaTriggerResult,
    SeparatedSegment,
    load_media_catalog,
)

__all__ = [
    "ChunkMediaInput",
    "MediaCandidate",
    "MediaTriggerResult",
    "SeparatedSegment",
    "build_media_separation_prompt_block",
    "detect_media_trigger",
    "identify_active_media",
    "load_media_catalog",
    "phonetic_phrase_similarity",
    "separate_chunk_media",
    "thai_phonetic_skeleton",
]
