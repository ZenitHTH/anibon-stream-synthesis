"""
anibon.common — Foundational shared utilities, configuration, time, cleaner, and models.
"""

from __future__ import annotations

from common.cleaner import clean_text, clean_text_with_count, compile_mapping_entries, load_replacements
from common.config import load_config, reload_config
from common.lmstudio import call_local, call_vision, resolve_endpoint, resolve_model
from common.resources import resource_path
from common.time import fmt_hhmmss, fmt_ts, parse_ts
from common.timestamps import (
    TAG_REMAP,
    TAGS,
    is_continuation,
    normalize_tag,
    parse_timestamps,
    sanitize_timestamp_line,
    validate_timestamps,
)

__all__ = [
    "clean_text",
    "clean_text_with_count",
    "compile_mapping_entries",
    "load_replacements",
    "load_config",
    "reload_config",
    "call_local",
    "call_vision",
    "resolve_endpoint",
    "resolve_model",
    "resource_path",
    "fmt_hhmmss",
    "fmt_ts",
    "parse_ts",
    "TAGS",
    "TAG_REMAP",
    "is_continuation",
    "normalize_tag",
    "parse_timestamps",
    "sanitize_timestamp_line",
    "validate_timestamps",
]
