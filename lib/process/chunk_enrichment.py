"""Pre-timestamp per-chunk enrichment: audio yell/silence webcam cues and Shazam recovery."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from chunk.state import load_chunk_file
from common import config as _cfg
from common.config import WEBCAM_CORNER
from common.log import format_progress, log_info, log_stage, log_warn
from common.time import fmt_ts
from process.chunk_storyboard_prep import prep_chunk_storyboard
from process.multimodal_situations import collect_situational_candidates
from process.reaction_source import resolve_reaction_audio_source, resolve_reaction_source
from video.audio_webcam_cues import AudioWebcamCue, select_audio_webcam_cues
from video.chunk_webcam import ChunkWebcamRequest, sample_chunk_webcam_frames
from video.motion_types import WindowBounds

if TYPE_CHECKING:
    from process.music.chunk_scanner import SongRecoveryResult, SongScanConfig

_LOCAL_AUDIO_NAMES = ("audio.m4a", "audio.opus", "audio.wav", "audio.mp3")
_ENRICH_MARKER = "--- PRE-CHUNK AUDIO/SONG ---"


@dataclass(frozen=True)
class ChunkEnrichConfig:
    """Configuration for pre-timestamp audio, webcam, and song enrichment."""

    workspace: Path
    audio_source: Optional[Path | str] = None
    video_source: Optional[Path | str] = None
    webcam_corner: str = WEBCAM_CORNER
    song_cfg: Optional["SongScanConfig"] = None
    force: bool = False
    slides_dir: Optional[Path] = None


def should_scan_chunk_for_song(inp: Any) -> bool:
    """Lazy-forward to process.music.chunk_scanner without eager numpy import."""
    from process.music.chunk_scanner import should_scan_chunk_for_song as _fn
    return _fn(inp)


def scan_and_recover_chunk_song(req: Any, cfg: Optional["SongScanConfig"]) -> Optional["SongRecoveryResult"]:
    """Lazy-forward to process.music.chunk_scanner without eager numpy import."""
    from process.music.chunk_scanner import SongScanConfig, scan_and_recover_chunk_song as _fn
    return _fn(req, cfg or SongScanConfig())


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
    items = [{"start": float(el.attrib.get("start", 0.0)), "timestamp": el.attrib.get("timestamp", ""), "text": el.text or ""} for el in root.findall("item")]
    return {"start_sec": int(root.attrib.get("start_sec", 0)), "end_sec": int(root.attrib.get("end_sec", 0)), "items": items}


def _load_chunk_meta(chunk_path: Path) -> dict:
    """Load chunk metadata and bounds across txt, json, and xml formats."""
    chunk = _load_xml_chunk(chunk_path) if chunk_path.suffix == ".xml" else load_chunk_file(chunk_path)
    m = re.search(r"chunk_(\d+)", chunk_path.stem)
    chunk["_idx"] = int(m.group(1)) if m else 0
    if int(chunk.get("end_sec", 0)) <= int(chunk.get("start_sec", 0)):
        chunk["start_sec"], chunk["end_sec"] = chunk["_idx"] * 150, (chunk["_idx"] + 1) * 150
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


def _expand_cue_target_secs(chunk: dict, cues: Tuple[AudioWebcamCue, ...]) -> Tuple[int, ...]:
    """Expand audio peak/silence cues with onset/follow-through offsets and deictic speech cues."""
    if not cues:
        return ()
    lo, hi = int(chunk.get("start_sec", 0) or 0), int(chunk.get("end_sec", 0) or 0)
    cap = max(3, int(_cfg.PASS1_WEBCAM_FRAMES or 9))
    chosen: List[int] = []
    for c in cues:
        for off in (0, -2, 2):
            sec = max(lo, min(hi, int(c.sec) + off)) if hi > lo else max(0, int(c.sec) + off)
            if all(abs(sec - prev) >= 2 for prev in chosen) and len(chosen) < cap:
                chosen.append(sec)
    items = chunk.get("items") or []
    for _, sec in collect_situational_candidates(items, lo, hi if hi > lo else lo + 150, pinned_only=False):
        if len(chosen) >= cap:
            break
        if all(abs(int(sec) - prev) >= 6 for prev in chosen):
            chosen.append(int(sec))
    return tuple(sorted(chosen[:cap]))


def _extract_cue_webcam_entries(chunk: dict, cues: Tuple[AudioWebcamCue, ...], cfg: ChunkEnrichConfig) -> Tuple[List[str], List[dict]]:
    """Crop webcam closeups at expanded audio/silence/deictic timestamps and return paths + sheet metadata."""
    if not cues or not cfg.video_source:
        return [], []
    secs = _expand_cue_target_secs(chunk, cues)
    req = ChunkWebcamRequest(cfg.workspace, cfg.video_source, chunk, secs, cfg.webcam_corner, max_frames=max(len(secs), _cfg.PASS1_WEBCAM_FRAMES))
    rendered = sample_chunk_webcam_frames(req)
    paths = [str(f[1]) for f in rendered if len(f) >= 2]
    sheets = [{"ts": str(f[0]), "path": str(f[1]), "label": str(f[3]) if len(f) > 3 else "WEBCAM CLOSEUP"} for f in rendered if len(f) >= 2]
    return paths, sheets


def _format_activity_block(cues: Tuple[AudioWebcamCue, ...], wc_paths: List[str], song: Optional["SongRecoveryResult"]) -> str:
    """Render pre-chunk audio, webcam, and Shazam signals for activity_chunk_NN.txt."""
    lines = [f"- {'[AUDIO_PEAK]' if c.event_type == 'loud_peak' else '[SILENCE_SHOCK]'} {fmt_ts(c.sec)} ({c.note}, score={c.score})" for c in cues]
    if wc_paths:
        lines.append(f"- [WEBCAM_FRAMES] {', '.join(wc_paths)}")
    if song:
        lines.append(f"- [SHAZAM_SONG] {song.title} - {song.artist} (recovered_lines={len(song.recovered_items)})")
    return "\n".join(lines)


def _merge_activity_sidecar(workspace: Path, cid: str, block: str) -> None:
    """Append, refresh, or strip pre-chunk enrichment lines in activity_NN.txt."""
    act_path = workspace / "activity" / f"activity_{cid}.txt"
    existing = act_path.read_text(encoding="utf-8") if act_path.is_file() else ""
    base = existing.split(_ENRICH_MARKER, 1)[0].strip()
    if not block:
        if _ENRICH_MARKER in existing:
            act_path.write_text((base + "\n") if base else "", encoding="utf-8")
        return
    act_path.parent.mkdir(parents=True, exist_ok=True)
    merged = f"{base}\n{_ENRICH_MARKER}\n{block}".strip()
    act_path.write_text(merged + "\n", encoding="utf-8")


def _read_cached_enrichment(cache_path: Path) -> Optional[dict]:
    """Read enrichment JSON cache safely, returning None on missing or corrupt JSON."""
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _build_enrichment_payload(
    cues: Tuple[AudioWebcamCue, ...], wc_paths: List[str], song: Optional["SongRecoveryResult"]
) -> dict:
    """Serialize cues, webcam frame paths, song metadata, and recovered speech."""
    return {
        "audio_cues": [{"sec": c.sec, "event_type": c.event_type, "score": c.score, "note": c.note} for c in cues],
        "webcam_frames": wc_paths,
        "song": {"title": song.title, "artist": song.artist} if song else None,
        "recovered_items": list(song.recovered_items) if song else [],
    }


def _maybe_recover_chunk_song(chunk: dict, cid: str, cfg: ChunkEnrichConfig) -> Optional["SongRecoveryResult"]:
    """Scan and recover background song + speaker speech when audio source and triggers match."""
    if not cfg.audio_source:
        return None
    from process.music.chunk_scanner import SongScanRequest, SongTriggerInput
    chat_lines, anchors = _load_chat_and_anchors(cfg.workspace, cid)
    scratch = cfg.workspace / "enrichment" / "scratch" / cid
    if cfg.force:
        (scratch / "vocals_16k.json").unlink(missing_ok=True)
    if should_scan_chunk_for_song(SongTriggerInput(chunk, chat_lines, anchors, cfg.audio_source)):
        return scan_and_recover_chunk_song(SongScanRequest(chunk, cfg.audio_source, scratch), cfg.song_cfg)
    return None


def enrich_single_chunk(chunk_path: Path, cfg: ChunkEnrichConfig) -> dict:
    """Run storyboard prep, audio yell/silence webcam extraction, and Shazam+whisper recovery."""
    cid = chunk_path.stem
    cache_path = cfg.workspace / "enrichment" / f"{cid}.json"
    if not cfg.force and (cached := _read_cached_enrichment(cache_path)) is not None:
        return cached
    if not cfg.audio_source and not cfg.video_source and not cfg.slides_dir:
        log_warn("enrich", f"{cid}: no audio/video/storyboard source resolved; skipping enrichment cache")
        return {}
    chunk = _load_chunk_meta(chunk_path)
    sb_frames = prep_chunk_storyboard(chunk, cfg.slides_dir, cfg.workspace)
    cues = select_audio_webcam_cues(cfg.audio_source, WindowBounds(chunk["start_sec"], chunk["end_sec"]))
    wc_paths, wc_sheets = _extract_cue_webcam_entries(chunk, cues, cfg)
    song = _maybe_recover_chunk_song(chunk, cid, cfg)
    payload = _build_enrichment_payload(cues, wc_paths, song)
    payload["webcam_sheets"] = wc_sheets
    payload["storyboard_frames"] = sb_frames
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
    if cfg.slides_dir is None:
        from process.multimodal import prepare_storyboard_slides
        cfg = replace(cfg, slides_dir=prepare_storyboard_slides(cfg.workspace))
    total = len(chunk_files)
    log_stage(f"STAGE 2 :: PREP-FIRST ENRICHMENT ({total} chunks: storyboard + webcam@peak/silence + song)")
    for i, cf in enumerate(chunk_files, start=1):
        p = enrich_single_chunk(cf, cfg)
        song_lbl = f" song={p['song']['title']}" if p.get("song") else ""
        log_info("prep", f"{format_progress(i, total)} {cf.stem} | sb={len(p.get('storyboard_frames') or ())} cues={len(p.get('audio_cues') or ())} wc={len(p.get('webcam_frames') or ())}{song_lbl}")
    return total


__all__ = ["ChunkEnrichConfig", "enrich_single_chunk", "enrich_workspace_chunks", "resolve_workspace_media"]
