#!/usr/bin/env python3
"""scripts/prepare_video.py - Download and chunk a YouTube transcript for AI timestamping."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_LIB_DIR = str(_SCRIPT_DIR.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from interface import (
    correct_transcript,
    download_storyboard,
    download_transcript,
    load_default_mappings,
    load_transcript,
    write_chunk_json,
    write_chunk_txt,
    write_chunk_xml,
)


def chunk_transcript(workspace: Path, block: int, overlap: int, fmt: str) -> int:
    """Load transcript, clean, and write chunk files. Returns number of chunks."""
    transcript = load_transcript(workspace)
    mappings = load_default_mappings()
    cleaned = correct_transcript(transcript, mappings)

    if not cleaned:
        return 0

    chunk_dir = workspace / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    total = int(cleaned[-1]["start"] + cleaned[-1].get("duration", 0))
    step = block - overlap
    idx = 0

    for start in range(0, total, step):
        end = start + block
        items = [x for x in cleaned if start <= x["start"] < end]
        if not items:
            continue
        path = chunk_dir / f"chunk_{idx:02d}.{fmt}"
        if fmt == "txt":
            write_chunk_txt(path, idx, start, end, overlap, items)
        elif fmt == "xml":
            write_chunk_xml(path, idx, start, end, items)
        else:
            write_chunk_json(path, start, end, items)
        idx += 1
    return idx


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
        default=300,
        help="Chunk block size in seconds (default: 300 = 5 min)",
    )
    ap.add_argument(
        "--overlap",
        type=int,
        default=30,
        help="Chunk overlap in seconds (default: 30)",
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
    download_transcript(url, workspace)
    if not args.no_storyboard:
        download_storyboard(url, workspace)
    n = chunk_transcript(workspace, block=args.block, overlap=args.overlap, fmt=args.format)

    if args.vision and args.format in ["json", "xml"]:
        from interface import process as _proc

        _proc.vision.run(workspace, url)

    print(f"[*] Done! Wrote {n} chunks ({args.format}) to {workspace}/chunks/")


if __name__ == "__main__":
    main()
