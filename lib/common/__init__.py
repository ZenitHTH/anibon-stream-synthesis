"""
common — Foundational shared utilities, configuration, time, cleaner, and models.
"""

from __future__ import annotations

from common.cleaner import (
    clean_chunk,
    clean_text,
    clean_text_with_count,
    compile_mapping_entries,
    correct_transcript,
    load_replacements,
)
from common.config import (
    CHUNK_MAX_TOKENS,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CHAT_PATH,
    DEFAULT_GROUP_SIZE,
    DEFAULT_PORT,
    DEFAULT_TEMPERATURE,
    EVAL_BATCH_SIZE,
    FACE_MOTION_THRESHOLD,
    PRIMARY_HOST,
    REACTION_VERIFY,
    SCENE_DELTA_THRESHOLD,
    WEBCAM_CORNER,
    cfg_bool,
    cfg_float,
    cfg_int,
    cfg_str,
    load_config,
    reload_config,
)
from common.corruption import (
    analyze_transcript,
    detect_segment_hallucination,
    is_hallucinated,
)
from common.lmstudio import (
    call_local,
    call_vision,
    get_loaded_models,
    resolve_endpoint,
    resolve_model,
)
from common.lm_think_log import (
    configure_lm_think_logging,
    summarize_lm_trace,
)
from common.log import (
    format_duration,
    format_progress,
    log_banner,
    log_block,
    log_cont,
    log_error,
    log_info,
    log_items,
    log_kv,
    log_ok,
    log_stage,
    log_warn,
)
from common.markdown import format_markdown, write_parts_json
from common.resources import load_default_mappings, plugin_root, resource_path
from common.time import fmt_hhmmss, fmt_ts, parse_ts
from common.timestamps import (
    TAG_REMAP,
    TAGS,
    deduplicate_consecutive_timestamps,
    is_continuation,
    normalize_tag,
    parse_timestamps,
    sanitize_timestamp_line,
    validate_timestamps,
)

__all__ = [
    # Cleaner
    "clean_chunk",
    "clean_text",
    "clean_text_with_count",
    "compile_mapping_entries",
    "correct_transcript",
    "load_replacements",
    # Config
    "load_config",
    "reload_config",
    "cfg_bool",
    "cfg_int",
    "cfg_float",
    "cfg_str",
    "CHUNK_MAX_TOKENS",
    "DEFAULT_BLOCK_SIZE",
    "DEFAULT_CHAT_PATH",
    "DEFAULT_GROUP_SIZE",
    "DEFAULT_PORT",
    "DEFAULT_TEMPERATURE",
    "EVAL_BATCH_SIZE",
    "FACE_MOTION_THRESHOLD",
    "PRIMARY_HOST",
    "REACTION_VERIFY",
    "SCENE_DELTA_THRESHOLD",
    "WEBCAM_CORNER",
    # LM Studio
    "call_local",
    "call_vision",
    "configure_lm_think_logging",
    "summarize_lm_trace",
    "resolve_endpoint",
    "resolve_model",
    "get_loaded_models",
    # Log
    "format_duration",
    "format_progress",
    "log_banner",
    "log_block",
    "log_cont",
    "log_error",
    "log_info",
    "log_items",
    "log_kv",
    "log_ok",
    "log_stage",
    "log_warn",
    # Resources
    "resource_path",
    "plugin_root",
    "load_default_mappings",
    # Time
    "fmt_hhmmss",
    "fmt_ts",
    "parse_ts",
    # Timestamps
    "TAGS",
    "TAG_REMAP",
    "is_continuation",
    "normalize_tag",
    "parse_timestamps",
    "sanitize_timestamp_line",
    "validate_timestamps",
    "deduplicate_consecutive_timestamps",
    # Corruption
    "analyze_transcript",
    "detect_segment_hallucination",
    "is_hallucinated",
    # Markdown
    "format_markdown",
    "write_parts_json",
]
