"""
anibon.garbled_resolver — LLM phonetic alignment for resolving garbled ASR notes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from common.lmstudio import call_local, resolve_endpoint, resolve_model
from process.garbled_grounding import (
    GroundingContext,
    is_grounded_target,
    load_grounding_context,
)
from process.garbled_rules import (
    BATCH_SIZE,
    is_safe_replacement,
    is_valid_candidate_token,
    load_raw_transcript_compact,
    strip_filler_prefix,
)


@dataclass(frozen=True)
class LlmTarget:
    endpoint: Optional[str] = None
    model: Optional[str] = None


def _build_candidate_line(item: dict) -> str:
    garbled_val = json.dumps(item["garbled"], ensure_ascii=False)
    google_val = json.dumps(item.get("google_sentence", ""), ensure_ascii=False)
    whisper_val = json.dumps(item.get("whisper_segment", ""), ensure_ascii=False)
    return f"- garbled: {garbled_val}\n  google: {google_val}\n  whisper: {whisper_val}"


def _build_resolution_prompt(batch: List[dict], domain_hint: str) -> str:
    items_txt = "\n".join(_build_candidate_line(it) for it in batch)
    return (
        "You are an ASR phonetic alignment specialist for Thai gaming/anime livestreams.\n"
        f"{domain_hint}\n\n"
        "Align each `garbled` token in `google` with the spoken word in `whisper` (acoustic ground truth).\n"
        "Rules:\n"
        "1. Map `garbled` to its exact canonical English/proper-noun spelling "
        "(e.g. 'Blue Archive', 'Nexon', 'Yostar', 'Twitter', 'Snowbreak', 'Heaven Burns Red').\n"
        "2. Output null if `whisper` is repetitive/inconclusive, if `garbled` is a normal Thai word/profanity, or if uncertain.\n"
        "3. Return ONLY a valid JSON object mapping each `garbled` string to its canonical string or null.\n\n"
        f"Candidates:\n{items_txt}\n\nJSON:"
    )


def _parse_llm_json(raw_reply: str) -> Dict[str, Optional[str]]:
    match = re.search(r"\{.*\}", raw_reply, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_grounded_replacements(
    batch: List[dict],
    llm_map: Dict[str, Optional[str]],
    context: GroundingContext,
) -> Dict[str, str]:
    whisper_map = {item.get("garbled", ""): item.get("whisper_segment", "") for item in batch}
    results: Dict[str, str] = {}
    for garbled, target in llm_map.items():
        if not target or not is_safe_replacement(garbled, target):
            continue
        whisper = whisper_map.get(garbled, "")
        if is_grounded_target(target, whisper, context):
            results[garbled] = target.strip()
    return results


def _invoke_llm(prompt: str, target: LlmTarget) -> str:
    import sys
    collector = sys.modules.get("process.garbled_collector")
    caller = getattr(collector, "call_local", call_local) if collector else call_local
    return caller(
        endpoint=target.endpoint or "",
        model=target.model or "",
        prompt=prompt,
        max_tokens=1024,
        temperature=0.1,
    )


def _resolve_single_batch(
    batch: List[dict], context: GroundingContext, target: LlmTarget
) -> Dict[str, str]:
    prompt = _build_resolution_prompt(batch, context.domain_hint)
    try:
        reply = _invoke_llm(prompt, target)
        return _extract_grounded_replacements(batch, _parse_llm_json(reply), context)
    except Exception as e:
        print(f"[garbled] Warning: LLM resolution batch failed ({e}).")
        return {}


def _resolve_candidate_batches(
    candidates: List[dict], context: GroundingContext, target: LlmTarget
) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    for idx in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[idx : idx + BATCH_SIZE]
        resolved.update(_resolve_single_batch(batch, context, target))
    return resolved


def _is_eligible_pending(note: dict, seen: set[str], raw_compact: str) -> bool:
    garbled = note.get("garbled", "")
    if note.get("correct") or not is_valid_candidate_token(garbled) or garbled in seen:
        return False
    if raw_compact and re.sub(r"\s+", "", garbled) not in raw_compact:
        return False
    return True


def _collect_pending_notes(workspace: Path, notes: List[dict]) -> List[dict]:
    raw_compact = load_raw_transcript_compact(workspace)
    pending: List[dict] = []
    seen: set[str] = set()
    for note in notes:
        cleaned = strip_filler_prefix(note.get("garbled", ""))
        note["garbled"] = cleaned
        if _is_eligible_pending(note, seen, raw_compact):
            seen.add(cleaned)
            pending.append(note)
    return pending


def _coerce_llm_target(
    target: Optional[Union[LlmTarget, Tuple[Optional[str], Optional[str]], str]],
    kwargs: Dict[str, Any],
) -> LlmTarget:
    if isinstance(target, LlmTarget):
        return target
    if isinstance(target, tuple):
        return LlmTarget(target[0], target[1] if len(target) > 1 else None)
    ep = target if isinstance(target, str) else kwargs.get("endpoint")
    return LlmTarget(endpoint=ep, model=kwargs.get("model"))


def _align_pending_notes(
    workspace: Path, pending: List[dict], target: LlmTarget
) -> Dict[str, str]:
    context = load_grounding_context(workspace)
    ep = resolve_endpoint(target.endpoint)
    if "/v1/chat/completions" in ep:
        ep = ep.replace("/v1/chat/completions", "/api/v1/chat")
    mdl = resolve_model(target.model or "auto", ep)
    return _resolve_candidate_batches(pending, context, LlmTarget(ep, mdl))


def _apply_resolved_notes(notes: List[dict], resolved: Dict[str, str]) -> int:
    count = 0
    for note in notes:
        garbled = note.get("garbled", "")
        if not note.get("correct") and garbled in resolved:
            note["correct"] = resolved[garbled]
            count += 1
    return count


def _save_notes_json(notes_json: Path, data: dict) -> None:
    notes_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_garbled_notes(
    workspace: Path,
    notes_json: Path,
    target: Optional[Union[LlmTarget, str]] = None,
    **kwargs: Any,
) -> int:
    """Resolve null 'correct' fields in garbled_notes.json via acoustic + LLM alignment."""
    if not notes_json.is_file():
        return 0
    data = json.loads(notes_json.read_text(encoding="utf-8"))
    notes = data.get("notes", [])
    pending = _collect_pending_notes(workspace, notes)
    if not pending:
        return 0
    resolved = _align_pending_notes(workspace, pending, _coerce_llm_target(target, kwargs))
    count = _apply_resolved_notes(notes, resolved)
    _save_notes_json(notes_json, data)
    print(f"[garbled] Resolved {count}/{len(notes)} garbled candidate(s) via acoustic alignment.")
    return count
