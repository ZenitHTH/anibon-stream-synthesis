"""Reaction onset verification orchestrator and Task 4 exports."""
from __future__ import annotations

from process.reaction_prompt import (
    PROTECTED_MILESTONE_TAGS,
    CoTriggerSignals,
    ParseConstraints,
    PromptContext,
    ReactionVerifyResult,
    build_face_reaction_prompt,
    needs_reaction_verify,
    parse_snapped_response,
    resolve_monotonic_snap,
)

__all__ = [
    "PROTECTED_MILESTONE_TAGS",
    "CoTriggerSignals",
    "ParseConstraints",
    "PromptContext",
    "ReactionVerifyResult",
    "build_face_reaction_prompt",
    "needs_reaction_verify",
    "parse_snapped_response",
    "resolve_monotonic_snap",
]
