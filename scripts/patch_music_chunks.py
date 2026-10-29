#!/usr/bin/env python3
"""Stage 1.5 Proactive Music Slicer and Chunk Patcher.

Scans chunks against LiveChat keyword density, acoustic signals, and Stage 0 music anchors.
Patches flagged chunks with [Song Context Briefing] and isolated dialogue.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from process.music.lore import SongContextBrief, fetch_song_lore_summary
from process.music.sensor import has_music_chat_surge


def format_song_context_briefing(brief: SongContextBrief) -> str:
    lines = [
        "[Song Context Briefing]",
        f"- เพลง: {brief.title} โดย {brief.artist}",
        f"- ธีม: {brief.theme}",
    ]
    if brief.meme_lore:
        lines.append(f"- บริบทในไลฟ์: {brief.meme_lore}")
    return "\n".join(lines)


HEADER_TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2})[–-](\d{2}:\d{2}:\d{2})")


def _extract_header(lines: list[str]) -> str:
    if not lines:
        return ""
    first = lines[0].strip()
    if first.startswith("CHUNK ") or first.startswith("[") or HEADER_TIME_RE.search(first):
        return first
    return ""


BRIEFING_BLOCK_RE = re.compile(
    r"\[Song Context Briefing\].*?(?=(?:\n\(\d{2}:\d{2}:\d{2}\)|\Z))",
    flags=re.DOTALL,
)


def _strip_existing_briefings(text: str) -> str:
    cleaned = BRIEFING_BLOCK_RE.sub("", text)
    return cleaned.strip()


def patch_chunk_with_song_lore(
    chunk_path: Path, brief: SongContextBrief, clean_speech: str
) -> None:
    original = chunk_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    header = _extract_header(lines)
    briefing = format_song_context_briefing(brief)
    pure_speech = _strip_existing_briefings(clean_speech)
    parts = [p for p in (header, briefing, pure_speech) if p]
    chunk_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def _is_anchor_in_window(anchor: dict, start_sec: int, end_sec: int) -> bool:
    offset_sec = anchor.get("offset_ms", anchor.get("start_ms", 0)) // 1000
    return start_sec <= offset_sec < end_sec


def score_lore_against_text(brief: SongContextBrief, text: str) -> int:
    t = text.lower()
    score = 0
    if brief.title.lower() in t:
        score += len(brief.title) * 3
    for kw in brief.keywords:
        if kw and kw.lower() in t:
            score += len(kw)
    return score


def find_matching_lore(
    chat_lines: Sequence[str],
    transcript_lines: Sequence[str] = (),
) -> SongContextBrief:
    all_lines = list(chat_lines) + list(transcript_lines)
    best_brief = fetch_song_lore_summary("เพลงคลอหลังฉาก")
    best_score = 0
    candidate_briefs: dict[tuple[str, str], SongContextBrief] = {}
    for line in all_lines:
        b = fetch_song_lore_summary(line)
        if b.artist != "Unknown":
            candidate_briefs[(b.title, b.artist)] = b
    for brief in candidate_briefs.values():
        total_score = sum(score_lore_against_text(brief, line) for line in all_lines)
        if total_score > best_score:
            best_score = total_score
            best_brief = brief
    return best_brief


def find_matching_lore_from_chat(chat_lines: Sequence[str]) -> SongContextBrief:
    return find_matching_lore(chat_lines)


def scan_and_patch_workspace(workspace_dir: Path) -> int:
    chunks_dir = workspace_dir / "chunks"
    if not chunks_dir.exists():
        return 0
    anchors_file = workspace_dir / "music_anchors.json"
    anchors = json.loads(anchors_file.read_text(encoding="utf-8")) if anchors_file.exists() else []
    index_file = workspace_dir / "livechat" / "livechat_index.json"
    chat_idx = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    patched_count = 0
    for chunk_path in sorted(chunks_dir.glob("chunk_*.txt")):
        if _process_single_chunk(chunk_path, anchors, chat_idx):
            patched_count += 1
    return patched_count


def _process_single_chunk(chunk_path: Path, anchors: list[dict], chat_idx: dict) -> bool:
    name = chunk_path.stem
    meta = chat_idx.get(name, {})
    raw_content = _strip_existing_briefings(chunk_path.read_text(encoding="utf-8"))
    lines = raw_content.splitlines()
    chat_lines = []
    if "file" in meta and Path(meta["file"]).exists():
        chat_lines = Path(meta["file"]).read_text(encoding="utf-8").splitlines()
    has_anchor = any(_is_anchor_in_window(a, meta.get("start", 0), meta.get("end", 0)) for a in anchors)
    has_surge = has_music_chat_surge(chat_lines)
    if not (has_anchor or has_surge):
        return False
    brief = find_matching_lore(chat_lines, lines)
    speech = "\n".join(lines[1:]) if len(lines) > 1 else ""
    patch_chunk_with_song_lore(chunk_path, brief, speech)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path, help="Workspace directory")
    args = parser.parse_args()
    count = scan_and_patch_workspace(args.workspace)
    print(f"[*] Patched {count} chunks with song context briefings.")
