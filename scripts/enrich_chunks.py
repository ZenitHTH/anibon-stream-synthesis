#!/usr/bin/env python3
"""CLI runner for pre-timestamp audio, webcam, and Shazam chunk enrichment."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from common.config import WEBCAM_CORNER
from process.audio_separator_engine import DEFAULT_AUDIOCPP_URL
from process.chunk_enrichment import ChunkEnrichConfig, enrich_workspace_chunks, resolve_workspace_media
from process.music.chunk_scanner import SongScanConfig


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for pre-chunk enrichment."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace", type=Path, help="Workspace directory")
    ap.add_argument("--video-file", default=None, help="Local video file path")
    ap.add_argument("--video-url", default=None, help="YouTube stream URL")
    ap.add_argument("--remote-snap", action="store_true", help="Resolve remote yt-dlp streams")
    ap.add_argument("--webcam-corner", default=WEBCAM_CORNER, help="Preferred OBS webcam corner")
    ap.add_argument("--audiocpp-url", default=DEFAULT_AUDIOCPP_URL, help="audio.cpp server URL")
    ap.add_argument("--force", action="store_true", help="Recompute existing enrichment caches")
    return ap


def main() -> None:
    args = build_parser().parse_args()
    ws = args.workspace.expanduser().resolve()
    audio_src, video_src = resolve_workspace_media(ws, args)
    cfg = ChunkEnrichConfig(
        workspace=ws,
        audio_source=audio_src,
        video_source=video_src,
        webcam_corner=args.webcam_corner,
        song_cfg=SongScanConfig(audiocpp_url=args.audiocpp_url),
        force=args.force,
    )
    count = enrich_workspace_chunks(cfg)
    print(f"[*] Enriched {count} chunks in {ws}")


if __name__ == "__main__":
    main()
