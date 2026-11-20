"""Pre-timestamp per-chunk enrichment: audio yell/silence webcam cues and Shazam recovery."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

from chunk.state import load_chunk_file
from common.config import WEBCAM_CORNER
from common.time import fmt_ts
from process.music.chunk_scanner import (
    SongRecoveryResult,
    SongScanConfig,
    SongScanRequest,
    SongTriggerInput,
    scan_and_recover_chunk_song,
    should_scan_chunk_for_song,
)
from process.reaction_source import resolve_reaction_audio_source, resolve_reaction_source
from video.audio_webcam_cues import AudioWebcamCue, select_audio_webcam_cues
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
from video.motion_types import WindowBounds

_LOCAL_AUDIO_NAMES = ("audio.m4a", "audio.opus", "audio.wav", "audio.mp3")
_ENRICH_MARKER = "--- PRE-CHUNK AUDIO/SONG ---"


@dataclass(frozen=True)
class ChunkEnrichConfig:
    """Configuration for pre-timestamp audio, webcam, and song enrichment."""

    workspace: Path
    audio_source: Optional[Path | str] = None
    video_source: Optional[Path | str] = None
    webcam_corner: str = WEBCAM_CORNER
    song_cfg: SongScanConfig = field(default_factory=SongScanConfig)
    force: bool = False


def resolve_workspace_media(
    workspace: Path, args: Any = None
) -> Tuple[Optional[Path | str], Optional[Path | str]]:
    """Resolve local audio/video files or remote stream URLs for pre-chunk enrichment."""
    ws = Path(workspace)
    video_src = resolve_reaction_source(ws, args) if args is not None else resolve_reaction_source(ws, object())
    audio_src = next((ws / name for name in _LOCAL_AUDIO_NAMES if (ws / name).is_file()), None)
    if audio_src is None:
        audio_src = resolve_reaction_audio_source(ws, args) if args is not None else video_src
    return audio_src, video_src


def _load_xml_chunk(chunk_path: Path) -> dict:
    """Parse an XML chunk file into {start_sec, end_sec, items}."""
    root = ET.parse(chunk_path).getroot()
    items = [
        {"start": float(el.attrib.get("start", 0.0)), "timestamp": el.attrib.get("timestamp", ""), "text": el.text or ""}
        for el in root.findall("item")
    ]
    return {"start_sec": int(root.attrib.get("start_sec", 0)), "end_sec": int(root.attrib.get("end_sec", 0)), "items": items}


def _load_chunk_meta(chunk_path: Path) -> dict:
    """Load chunk metadata and bounds across txt, json, and xml formats."""
    chunk = _load_xml_chunk(chunk_path) if chunk_path.suffix == ".xml" else load_chunk_file(chunk_path)
    m = re.search(r"chunk_(\d+)", chunk_path.stem)
    chunk["_idx"] = int(m.group(1)) if m else 0
    if int(chunk.get("end_sec", 0)) <= int(chunk.get("start_sec", 0)):
        idx = chunk["_idx"]
        chunk["start_sec"], chunk["end_sec"] = idx * 150, (idx + 1) * 150
    return chunk


def _load_chat_and_anchors(workspace: Path, cid: str) -> Tuple[Tuple[str, ...], list]:
    """Load per-chunk livechat lines and workspace music_anchors.json."""
    lc_path = workspace / "livechat" / f"livechat_{cid}.txt"
    chat_lines = tuple(lc_path.read_text(encoding="utf-8", errors="replace").splitlines()) if lc_path.is_file() else ()
    anc_path = workspace / "music_anchors.json"
    if not anc_path.is_file():
        return chat_lines, []
    try:
        data = json.loads(anc_path.read_text(encoding="utf-8"))
        return chat_lines, data if isinstance(data, list) else []
    except Exception:
        return chat_lines, []


def _extract_cue_webcam_paths(
    chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig
) -> List[str]:
    """Crop webcam closeups at audio yell/silence timestamps and return relative paths."""
    if not cues or not cfg.video_source:
        return []
    req = ChunkWebcamRequest(
        workspace=cfg.workspace, source=cfg.video_source, chunk=chunk,
        target_secs=tuple(c.sec for c in cues), preferred=cfg.webcam_corner,
    )
    frames = sample_chunk_webcam_frames(req)
    return [str(f[1]) for f in frames if len(f) >= 2]


def _format_activity_block(
    cues: Tuple[AudioWebcamCue, ...], wc_paths: List[str], song: Optional[SongRecoveryResult]
) -> str:
    """Render pre-chunk audio, webcam, and Shazam signals for activity_chunk_NN.txt."""
    lines: List[str] = []
    for cue in cues:
        tag = "[AUDIO_PEAK]" if cue.event_type == "loud_peak" else "[SILENCE_SHOCK]"
        lines.append(f"- {tag} {fmt_ts(cue.sec)} ({cue.note}, score={cue.score})")
    if wc_paths:
        lines.append(f"- [WEBCAM_FRAMES] {', '.join(wc_paths)}")
    if song:
        lines.append(f"- [SHAZAM_SONG] {song.title} - {song.artist} (recovered_lines={len(song.recovered_items)})")
    return "\n".join(lines)


def _merge_activity_sidecar(workspace: Path, cid: str, block: str) -> None:
    """Append or refresh pre-chunk enrichment lines inside activity/activity_NN.txt."""
    if not block:
        return
    act_dir = workspace / "activity"
    act_dir.mkdir(parents=True, exist_ok=True)
    act_path = act_dir / f"activity_{cid}.txt"
    existing = act_path.read_text(encoding="utf-8") if act_path.is_file() else ""
    base = existing.split(_ENRICH_MARKER, 1)[0].strip()
    merged = f"{base}\n{_ENRICH_MARKER}\n{block}".strip()
    act_path.write_text(merged + "\n", encoding="utf-8")


def _build_enrichment_payload(
    cues: Tuple[AudioWebcamCue, ...], wc_paths: List[str], song: Optional[SongRecoveryResult]
) -> dict:
    """Serialize cues, webcam frame paths, song metadata, and recovered speech."""
    return {
        "audio_cues": [{"sec": c.sec, "event_type": c.event_type, "score": c.score, "note": c.note} for c in cues],
        "webcam_frames": wc_paths,
        "song": {"title": song.title, "artist": song.artist} if song else None,
        "recovered_items": list(song.recovered_items) if song else [],
    }


def enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict:
    """Run audio yell/silence webcam extraction and Shazam+whisper recovery for one chunk."""
    cid = chunk_path.stem
    cache_path = cfg.workspace / "enrichment" / f"{cid}.json"
    if cache_path.is_file() and not cfg.force:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    chunk = _load_chunk_meta(chunk_path)
    bounds = WindowBounds(chunk["start_sec"], chunk["end_sec"])
    cues = select_audio_webcam_cues(cfg.audio_source, bounds)
    wc_paths = _extract_cue_webcam_paths(chunk, cues, cfg)
    chat_lines, anchors = _load_chat_and_anchors(cfg.workspace, cid)
    song: Optional[SongRecoveryResult] = None
    if cfg.audio_source and should_scan_chunk_for_song(SongTriggerInput(chunk, chat_lines, anchors, cfg.audio_source)):
        scratch = cfg.workspace / "enrichment" / "scratch" / cid
        song = scan_and_recover_chunk_song(SongScanRequest(chunk, cfg.audio_source, scratch), cfg.song_cfg)
    payload = _build_enrichment_payload(cues, wc_paths, song)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _merge_activity_sidecar(cfg.workspace, cid, _format_activity_block(cues, wc_paths, song))
    return payload


def _discover_chunk_files(chunks_dir: Path) -> List[Path]:
    """Return sorted chunk files preferring txt -> xml -> json."""
    for ext in ("chunk_*.txt", "chunk_*.xml", "chunk_*.json"):
        found = sorted(chunks_dir.glob(ext))
        if found:
            return found
    return []


def enrich_workspace_chunks(cfg: ChunkEnrichConfig) -> int:
    """Pre-enrich all chunks in workspace before timestamping. Returns enriched count."""
    chunks_dir = cfg.workspace / "chunks"
    if not chunks_dir.is_dir():
        return 0
    chunk_files = _discover_chunk_files(chunks_dir)
    for cf in chunk_files:
        enrich_single_chunk(cf, cfg)
    return len(chunk_files)


__all__ = ["ChunkEnrichConfig", "enrich_single_chunk", "enrich_workspace_chunks", "resolve_workspace_media"]
