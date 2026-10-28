"""
process — Core livestream timestamping, prompting, summarization, and verification pipeline.
"""

from __future__ import annotations

from process.assembly import finalize_and_assemble_timestamps
from process.audit import (
    audit_timestamps_against_glossary,
    sanitize_and_audit_timestamps,
)
from process.garbled_collector import (
    GarbledCollectorOptions,
    LlmTarget,
    resolve_garbled_notes,
    run_garbled_collector,
)
from process.knowledge import (
    enrich_with_sqlite_databases,
    extract_entity_glossary,
    resolve_entities_for_chunk,
    resolve_reference_file,
    save_entity_glossary,
)
from process.livechat import (
    align_livechat_feed,
    download_livechat,
    find_livechat_file,
    has_aligned_livechat,
    parse_livechat_feed,
    prepare_livechat,
)
from process.multimodal import (
    build_multimodal_content,
    call_multimodal,
    prepare_storyboard_slides,
    sample_chunk_keyframes,
)
from process.parity_gates import ensure_mood_555, run_parity_gates
from process.prompts import (
    WORLD_IDENTITY_DIR,
    build_group_prompt,
    build_recursive_prompt,
    load_world_identity_context,
)
from process.runners import run_group_mode, run_recursive_mode
from process.signals import (
    clean_transcript_noise,
    compute_idf_stats,
    detect_signals_for_chunks,
    get_domain_guidance,
    load_garbled_replacements,
    load_knowledge,
    load_mappings,
    match_chunk,
    normalize_transcript,
)
from process.summarizer import (
    assemble_parts,
    enforce_byte_cap,
    generate_part_summary,
    prune_essential,
    run_local_summarizer_pass,
)
from process.vision_verify import apply_vision_verify
from process.whisper_dispatcher import dispatch_verification
from process.world_sanitizer import audit_and_sanitize_final_markdown

__all__ = [
    "finalize_and_assemble_timestamps",
    "sanitize_and_audit_timestamps",
    "audit_timestamps_against_glossary",
    "resolve_garbled_notes",
    "run_garbled_collector",
    "LlmTarget",
    "GarbledCollectorOptions",
    "dispatch_verification",
    "extract_entity_glossary",
    "save_entity_glossary",
    "enrich_with_sqlite_databases",
    "resolve_entities_for_chunk",
    "resolve_reference_file",
    "build_multimodal_content",
    "call_multimodal",
    "prepare_storyboard_slides",
    "sample_chunk_keyframes",
    "ensure_mood_555",
    "run_parity_gates",
    "WORLD_IDENTITY_DIR",
    "build_group_prompt",
    "build_recursive_prompt",
    "load_world_identity_context",
    "run_group_mode",
    "run_recursive_mode",
    "detect_signals_for_chunks",
    "get_domain_guidance",
    "load_knowledge",
    "load_mappings",
    "load_garbled_replacements",
    "clean_transcript_noise",
    "compute_idf_stats",
    "match_chunk",
    "normalize_transcript",
    "assemble_parts",
    "enforce_byte_cap",
    "generate_part_summary",
    "prune_essential",
    "run_local_summarizer_pass",
    "apply_vision_verify",
    "audit_and_sanitize_final_markdown",
    "align_livechat_feed",
    "download_livechat",
    "find_livechat_file",
    "has_aligned_livechat",
    "parse_livechat_feed",
    "prepare_livechat",
]
