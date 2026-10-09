"""Transcript source detection module for anibon workspaces.

Differentiates between:
- 'youtube-auto': YouTube automatic caption download (prone to multilingual character noise)
- 'whisper': Local/recovered Whisper speech-to-text (clean Thai speech, no multilingual noise)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def detect_transcript_source(workspace: Path) -> str:
    """Detect whether transcript originates from YouTube auto-captions or local Whisper."""
    workspace = Path(workspace)
    if not workspace.is_dir():
        return "unknown"

    # 1. Explicit metadata check in info files
    for info_name in ["info.json", "video_info.json", "transcript_source.json"]:
        p = workspace / info_name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                src = data.get("transcript_source")
                if src in ["youtube-auto", "whisper"]:
                    return src
            except Exception:
                pass

    # 2. Local Whisper / recovery indicators
    whisper_indicators = [
        "whisper_output.json",
        "audio_recovered.json",
        "transcript_recovered_clean.json",
        "audio_base.json",
        "whisper_segments.json",
    ]
    for wf in whisper_indicators:
        if (workspace / wf).is_file():
            return "whisper"

    # 3. YouTube auto-subs JSON3 files
    for f in workspace.glob("*.json3"):
        return "youtube-auto"
    if (workspace / "raw_transcript.th.json3").is_file():
        return "youtube-auto"

    # 4. Probe raw_transcript.json content for YouTube caption wire signature
    raw_p = workspace / "raw_transcript.json"
    if raw_p.is_file():
        try:
            head = raw_p.read_text(encoding="utf-8", errors="ignore")[:600]
            if "wireMagic" in head or "wpWinPositions" in head or "wsWinStyles" in head:
                return "youtube-auto"
        except Exception:
            pass

    return "unknown"


def is_youtube_auto_transcript(workspace: Path) -> bool:
    """Return True only if transcript is confirmed to be from YouTube Auto-captions."""
    src = detect_transcript_source(workspace)
    # If explicitly detected as youtube-auto, True; if whisper, False; fallback False
    return src == "youtube-auto"
