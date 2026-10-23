"""
chunk — Chunk management, file I/O, state tracking, and boundary analysis.
"""

from __future__ import annotations

from chunk.analyzer import (
    calculate_youtube_blocks,
    classify_chunk,
    detect_timeline_gaps,
)
from chunk.chunk_io import (
    chunk_sort_key,
    load_chunks,
    load_chunks_list,
    write_chunk_json,
    write_chunk_txt,
    write_chunk_xml,
)
from chunk.parsers import parse_timestamp_line, parse_timestamps
from chunk.state import (
    discover_chunks,
    load_chunk_activity,
    load_chunk_livechat,
    load_chunk_mood,
    load_state,
    save_state,
)
from chunk.topic_scanner import extract_macro_anchor, scan_chunk_topic_pivot

__all__ = [
    "calculate_youtube_blocks",
    "classify_chunk",
    "detect_timeline_gaps",
    "chunk_sort_key",
    "load_chunks",
    "load_chunks_list",
    "write_chunk_json",
    "write_chunk_txt",
    "write_chunk_xml",
    "discover_chunks",
    "load_state",
    "save_state",
    "load_chunk_activity",
    "load_chunk_livechat",
    "load_chunk_mood",
    "parse_timestamp_line",
    "parse_timestamps",
    "extract_macro_anchor",
    "scan_chunk_topic_pivot",
]
