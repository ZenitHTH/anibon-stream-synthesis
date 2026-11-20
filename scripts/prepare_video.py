#!/usr/bin/env python3
"""scripts/prepare_video.py - Download and chunk a YouTube transcript for AI timestamping."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_LIB_DIR = str(_SCRIPT_DIR.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from interface import (
    DEFAULT_SUB_LANGS,
    clean_text,
    correct_transcript,
    download_storyboard,
    download_transcript,
    load_default_mappings,
    load_replacements,
    load_transcript,
    prepare_livechat,
    save_metadata,
    write_chunk_json,
    write_chunk_txt,
    write_chunk_xml,
)
from process.signals.detector import extract_and_clean_music_anchors, save_music_anchors


def _extract_and_save_anchors(cleaned: list, workspace: Path) -> None:
    compiled_replacements = load_replacements()
    anchors = []
    for item in cleaned:
        offset_ms = int(item.get("start", 0) * 1000)
        clean_t, item_anchors = extract_and_clean_music_anchors(item.get("text", ""), offset_ms=offset_ms)
        item["text"] = clean_text(clean_t, compiled_replacements)
        anchors.extend(item_anchors)
    if anchors:
        save_music_anchors(anchors, workspace)


@dataclass(frozen=True)
class ChunkBuildOptions:
    """Chunking window parameters for transcript splitting."""

    block: int = 150
    overlap: int = 15
    fmt: str = "json"


def _load_cleaned_transcript(workspace: Path) -> list:
    """Load, correct, and extract music anchors from workspace transcript."""
    transcript = load_transcript(workspace)
    cleaned = correct_transcript(transcript, load_default_mappings())
    if cleaned:
        _extract_and_save_anchors(cleaned, workspace)
    return cleaned


def _write_single_chunk(
    chunk_dir: Path, idx: int, window: tuple[int, int, list], opts: ChunkBuildOptions
) -> None:
    """Write one chunk file in txt, xml, or json format."""
    start, end, items = window
    path = chunk_dir / f"chunk_{idx:02d}.{opts.fmt}"
    if opts.fmt == "txt":
        write_chunk_txt(path, idx, start, end, opts.overlap, items)
    elif opts.fmt == "xml":
        write_chunk_xml(path, idx, start, end, items)
    else:
        write_chunk_json(path, start, end, items)


def _write_chunk_windows(
    workspace: Path, opts: ChunkBuildOptions, include_empty: tuple[bool]
) -> int:
    """Split cleaned transcript into sequential chunk files."""
    cleaned = _load_cleaned_transcript(workspace)
    if not cleaned:
        return 0
    chunk_dir = workspace / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    total = int(cleaned[-1]["start"] + cleaned[-1].get("duration", 0))
    step = max(1, opts.block - opts.overlap)
    idx = 0
    keep_empty = include_empty[0]
    for start in range(0, total, step):
        end = start + opts.block
        items = [x for x in cleaned if start <= x["start"] < end]
        if not items and not keep_empty:
            continue
        _write_single_chunk(chunk_dir, idx, (start, end, items), opts)
        idx += 1
    return idx


def chunk_transcript(workspace: Path, block: int, overlap: int, fmt: str) -> int:
    """Load transcript, clean, and write non-empty chunk files. Returns count."""
    return _write_chunk_windows(workspace, ChunkBuildOptions(block, overlap, fmt), (False,))


def chunk_transcript_with_silent_windows(workspace: Path, opts: ChunkBuildOptions) -> int:
    """Load transcript, clean, and write all windows including silent gaps."""
    return _write_chunk_windows(workspace, opts, (True,))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Download and chunk a YouTube transcript for AI timestamping."
    )
    ap.add_argument("url", help="YouTube video URL or ID")
    ap.add_argument(
        "--format",
        choices=["json", "txt", "xml"],
        default="json",
        help="Output format: json (Gemini), xml (Claude), or txt (local). Default: json",
    )
    ap.add_argument(
        "--block",
        type=int,
        default=150,
        help="Chunk block size in seconds (default: 150 = 2.5 min)",
    )
    ap.add_argument(
        "--overlap",
        type=int,
        default=15,
        help="Chunk overlap in seconds (default: 15)",
    )
    ap.add_argument(
        "--vision",
        action="store_true",
        help="Extract and annotate visual frames for ambiguous pronoun cues",
    )
    ap.add_argument(
        "--no-storyboard",
        action="store_true",
        help="Skip downloading YouTube storyboard mhtml slides",
    )
    ap.add_argument(
        "--sub-langs",
        default=DEFAULT_SUB_LANGS,
        help=f"Subtitle language priority (default: {DEFAULT_SUB_LANGS})",
    )
    ap.add_argument(
        "--live-chat",
        action="store_true",
        help="Download, parse, and align YouTube live_chat replay into livechat/ chunks",
    )
    ap.add_argument(
        "--keep-silent-chunks",
        action="store_true",
        help="Emit placeholder chunk files for empty-transcript silent windows",
    )
    ap.add_argument(
        "--workspace",
        "-o",
        default=None,
        help="Target workspace directory (default: ~/youtube_<video_id>_workspace)",
    )
    args = ap.parse_args()

    # Extract video_id from URL or use as-is
    url = args.url
    vid = url.split("v=")[-1].split("&")[0].split("/")[-1].split("?")[0]

    if args.workspace:
        workspace = Path(args.workspace).expanduser().resolve()
    else:
        workspace = Path.home() / f"youtube_{vid}_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    print(f"[*] Workspace: {workspace}", file=sys.stderr)

    (workspace / ".video_url").write_text(url.strip(), encoding="utf-8")
    save_metadata(url, workspace)
    download_transcript(url, workspace, sub_langs=args.sub_langs)
    if not args.no_storyboard:
        download_storyboard(url, workspace)
    opts = ChunkBuildOptions(block=args.block, overlap=args.overlap, fmt=args.format)
    if args.keep_silent_chunks:
        n = chunk_transcript_with_silent_windows(workspace, opts)
    else:
        n = chunk_transcript(workspace, block=args.block, overlap=args.overlap, fmt=args.format)
    if args.live_chat:
        prepare_livechat(url, workspace)

    print(f"[*] Done! Wrote {n} chunks ({args.format}) to {workspace}/chunks/")


if __name__ == "__main__":
    main()
