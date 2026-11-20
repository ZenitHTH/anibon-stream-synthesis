"""Lazy-loading package facade for process.music (avoids eager numpy import on CLI startup)."""
from __future__ import annotations

import importlib
from typing import Any

_EXPORTS = {
    "AcousticFeatures": "process.music.acoustic",
    "analyze_acoustic_features": "process.music.acoustic",
    "is_music_spectral": "process.music.acoustic",
    "SongContextBrief": "process.music.lore",
    "fetch_song_lore_summary": "process.music.lore",
    "TrackMetadata": "process.music.sensor",
    "has_music_chat_surge": "process.music.sensor",
    "scan_chat_music_density": "process.music.sensor",
    "process_subtraction_files": "process.music.subtractor",
    "subtract_reference_signal": "process.music.subtractor",
}


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        mod = importlib.import_module(_EXPORTS[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_EXPORTS.keys())
