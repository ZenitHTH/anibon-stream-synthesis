"""
download — Media, transcript, and external resource downloading.
"""

from __future__ import annotations

from download.transcript_source import detect_transcript_source, is_youtube_auto_transcript
from download.ytdlp import (
    download_storyboard,
    download_transcript,
    download_video,
    flatten_json3,
    load_transcript,
    probe_metadata,
    ytdlp_cmd,
)

__all__ = [
    "download_storyboard",
    "download_transcript",
    "download_video",
    "flatten_json3",
    "load_transcript",
    "probe_metadata",
    "ytdlp_cmd",
    "detect_transcript_source",
    "is_youtube_auto_transcript",
]
