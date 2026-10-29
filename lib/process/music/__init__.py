from __future__ import annotations

from process.music.acoustic import (
    AcousticFeatures,
    analyze_acoustic_features,
    is_music_spectral,
)
from process.music.lore import SongContextBrief, fetch_song_lore_summary
from process.music.sensor import (
    TrackMetadata,
    has_music_chat_surge,
    scan_chat_music_density,
)
from process.music.subtractor import (
    process_subtraction_files,
    subtract_reference_signal,
)

__all__ = [
    "AcousticFeatures",
    "SongContextBrief",
    "TrackMetadata",
    "analyze_acoustic_features",
    "fetch_song_lore_summary",
    "has_music_chat_surge",
    "is_music_spectral",
    "process_subtraction_files",
    "scan_chat_music_density",
    "subtract_reference_signal",
]
