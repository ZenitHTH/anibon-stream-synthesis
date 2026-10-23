"""
anibon-stream-synthesis Core Library Package.

Task-oriented package architecture:
- common:   Foundation, configurations, text cleaners, time, and models.
- download: External downloading, yt-dlp automation, and transcript detection.
- chunk:    Chunk file management, boundary analysis, state tracking, and parsing.
- process:  Timestamping pipeline, signals, knowledge databases, and assembly.

Interface module:
- interface: Unified facade for easy calling across skill scripts.
"""

from __future__ import annotations

try:
    from . import chunk, common, download, interface, process
    from .interface import *  # noqa: F401, F403
except (ImportError, ValueError):
    import chunk  # type: ignore
    import common  # type: ignore
    import download  # type: ignore
    import interface  # type: ignore
    import process  # type: ignore
    from interface import *  # noqa: F401, F403

__all__ = [
    "common",
    "download",
    "chunk",
    "process",
    "interface",
]
