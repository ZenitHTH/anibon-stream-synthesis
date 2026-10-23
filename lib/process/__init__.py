"""
anibon.process — Core livestream timestamping, prompting, summarization, and verification pipeline.
"""

from __future__ import annotations

from process.assembly import finalize_and_assemble_timestamps
from process.audit import (
    audit_timestamps_against_glossary,
    sanitize_and_audit_timestamps,
)
from process.garbled_collector import run_garbled_collector
from process.knowledge import extract_entity_glossary, save_entity_glossary
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
from process.signals import detect_signals_for_chunks, get_domain_guidance
from process.summarizer import (
    assemble_parts,
    enforce_byte_cap,
    generate_part_summary,
    prune_essential,
    run_local_summarizer_pass,
)
from process.vision_verify import apply_vision_verify
from process.world_sanitizer import audit_and_sanitize_final_markdown

__all__ = [
    "finalize_and_assemble_timestamps",
    "sanitize_and_audit_timestamps",
    "audit_timestamps_against_glossary",
    "run_garbled_collector",
    "extract_entity_glossary",
    "save_entity_glossary",
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
    "assemble_parts",
    "enforce_byte_cap",
    "generate_part_summary",
    "prune_essential",
    "run_local_summarizer_pass",
    "apply_vision_verify",
    "audit_and_sanitize_final_markdown",
]
