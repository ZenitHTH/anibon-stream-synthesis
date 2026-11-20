"""Prompt formatting helper for pre-chunk audio, webcam, and Shazam enrichment."""
from __future__ import annotations

from typing import List, Optional

from common.time import fmt_ts


def _format_cue_lines(cues: list) -> List[str]:
    return [
        f"- ({fmt_ts(int(c.get('sec', 0)))}) {c.get('event_type', 'cue')} ({c.get('note', '')})"
        for c in cues
        if isinstance(c, dict)
    ]


def _format_recovered_lines(items: list) -> List[str]:
    return [
        f"({it.get('timestamp', '')}) {it.get('text', '').strip()}"
        for it in items
        if isinstance(it, dict) and (it.get("text") or "").strip()
    ]


def format_enrichment_context(enrichment: Optional[dict]) -> str:
    """Render detected song, recovered speech, and audio/silence cues for prompts."""
    if not enrichment or not isinstance(enrichment, dict):
        return ""
    blocks: List[str] = []
    song = enrichment.get("song")
    if isinstance(song, dict) and song.get("title"):
        blocks.append(
            f"[DETECTED SONG]: {song.get('title')} - {song.get('artist', 'Unknown')} "
            "(Vocals split via audio.cpp; do NOT attribute background lyrics to Pu Boat.)"
        )
    rec = _format_recovered_lines(enrichment.get("recovered_items") or [])
    if rec:
        blocks.append("[RECOVERED SPEAKER SPEECH (audio.cpp + whisper.cpp)]:\n" + "\n".join(rec))
    cues = _format_cue_lines(enrichment.get("audio_cues") or [])
    if cues:
        blocks.append("[AUDIO/SILENCE WEBCAM CUES]:\n" + "\n".join(cues))
    return "\n".join(blocks)
