"""Pre-chunk Shazam identification, audio.cpp separation, and whisper.cpp recovery."""
from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

from common.log import log_warn
from common.time import fmt_ts
from process.audio_separator_engine import (
    DEFAULT_AUDIOCPP_URL,
    convert_audio_to_16k_mono,
    separate_via_audiocpp_api,
)
from process.music.sensor import TrackMetadata, has_music_chat_surge, recognize_shazam_slice
from process.whisper_dispatcher import find_whisper_cli, find_whisper_model, run_whisper_slice


@dataclass(frozen=True)
class SongScanConfig:
    """Configuration for pre-chunk Shazam, audio.cpp, and whisper.cpp recovery."""

    audiocpp_url: str = DEFAULT_AUDIOCPP_URL
    shazam_timeout_sec: float = 15.0
    whisper_bin: Optional[str] = None
    whisper_model: Optional[str] = None
    shazam_slice_sec: int = 20


@dataclass(frozen=True)
class SongTriggerInput:
    """Inputs deciding whether a chunk should undergo Shazam scanning."""

    chunk: dict
    chat_lines: Sequence[str] = ()
    anchors: Sequence[dict] = ()
    audio_source: Optional[Path | str] = None


@dataclass(frozen=True)
class SongScanRequest:
    """Chunk target and workspace scratch dir for song + speech recovery."""

    chunk: dict
    audio_source: Path | str
    work_dir: Path


@dataclass(frozen=True)
class SongRecoveryResult:
    """Identified track and recovered speaker dialogue items."""

    title: str
    artist: str
    recovered_items: Tuple[dict, ...]
    vocals_path: Optional[Path] = None


def _chunk_bounds(chunk: dict) -> Tuple[int, int]:
    """Return inclusive (start_sec, end_sec) for a chunk dict."""
    s = int(chunk.get("start_sec", 0) or 0)
    e = int(chunk.get("end_sec", 0) or 0)
    if e > s:
        return s, e
    items = chunk.get("items", ())
    if not items:
        return s, s + 150
    lo = int(float(items[0].get("start", 0) or 0))
    hi = int(float(items[-1].get("start", lo) or lo)) + int(float(items[-1].get("duration", 5) or 5))
    return lo, max(lo + 5, hi)


def _anchor_overlaps(anchors: Sequence[dict], start_sec: int, end_sec: int) -> bool:
    """Return True if any music anchor falls inside [start_sec, end_sec)."""
    for anchor in anchors:
        sec = int(anchor.get("offset_ms", anchor.get("start_ms", 0)) or 0) // 1000
        if start_sec <= sec < end_sec:
            return True
    return False


def _probe_spectral_music(audio_source: Optional[Path | str], start_sec: int, end_sec: int) -> bool:
    """Check 5s midpoint audio slice for tonal/music spectral flatness."""
    if not audio_source:
        return False
    mid = max(0, (start_sec + end_sec) // 2 - 2)
    cmd = ["ffmpeg", "-v", "error", "-ss", str(mid), "-t", "5", "-i", str(audio_source),
           "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    try:
        import numpy as np
        from process.music.acoustic import analyze_acoustic_features, is_music_spectral
        res = subprocess.run(cmd, capture_output=True, timeout=20)
        if res.returncode != 0 or len(res.stdout) < 3200:
            return False
        samples = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        return is_music_spectral(analyze_acoustic_features(samples, 16000).flatness)
    except Exception:
        return False


def should_scan_chunk_for_song(inp: SongTriggerInput) -> bool:
    """Determine if a chunk has music anchors, chat surge, or spectral music cues."""
    start_sec, end_sec = _chunk_bounds(inp.chunk)
    if _anchor_overlaps(inp.anchors, start_sec, end_sec):
        return True
    if has_music_chat_surge(inp.chat_lines):
        return True
    return _probe_spectral_music(inp.audio_source, start_sec, end_sec)


def _slice_wav_range(source: Path | str, span: Tuple[int, int], out_wav: Path) -> bool:
    """Slice bounded (start_sec, duration_sec) 44.1kHz stereo WAV via ffmpeg."""
    start_sec, duration_sec = span
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(max(0, start_sec)),
           "-t", str(max(1, duration_sec)), "-i", str(source),
           "-vn", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_wav)]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=45)
        return res.returncode == 0 and out_wav.is_file() and out_wav.stat().st_size > 0
    except (OSError, subprocess.SubprocessError):
        return False


def _run_shazam_with_timeout(slice_wav: Path, timeout_sec: float) -> Optional[TrackMetadata]:
    """Run shazamio recognition bounded by asyncio.wait_for."""
    async def _call() -> Optional[TrackMetadata]:
        return await asyncio.wait_for(recognize_shazam_slice(str(slice_wav)), timeout=timeout_sec)
    try:
        return asyncio.run(_call())
    except Exception:
        return None


def _segments_to_items(segments: Sequence[dict], full_text: str, base_sec: int) -> Tuple[dict, ...]:
    """Convert relative whisper-cli JSON segments into absolute-timestamped items."""
    items = []
    for seg in segments:
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        rel_sec = float((seg.get("offsets") or {}).get("from", 0)) / 1000.0
        abs_sec = round(base_sec + rel_sec, 2)
        items.append({"start": abs_sec, "timestamp": fmt_ts(abs_sec), "text": txt})
    if not items and full_text.strip():
        items.append({"start": float(base_sec), "timestamp": fmt_ts(base_sec), "text": full_text.strip()})
    return tuple(items)


def _transcribe_vocals(
    vocals_wav: Path, req: SongScanRequest, cfg: SongScanConfig
) -> Tuple[dict, ...]:
    """Resample vocals to 16kHz mono and transcribe via whisper.cpp."""
    w_bin = cfg.whisper_bin or find_whisper_cli()
    w_mod = cfg.whisper_model or find_whisper_model()
    if not os.environ.get("WHISPER_ENDPOINT") and not (w_bin and w_mod):
        log_warn("song", "whisper-cli or model missing; skipping speech recovery")
        return ()
    wav_16k = req.work_dir / f"{vocals_wav.stem}_16k.wav"
    base_sec = _chunk_bounds(req.chunk)[0]
    try:
        convert_audio_to_16k_mono(vocals_wav, wav_16k)
        full_text, segments = run_whisper_slice(w_bin or "", w_mod or "", str(wav_16k))
        return _segments_to_items(segments, full_text, base_sec)
    except Exception as exc:
        log_warn("song", f"whisper recovery failed ({exc})")
        return ()


def scan_and_recover_chunk_song(
    req: SongScanRequest, cfg: SongScanConfig
) -> Optional[SongRecoveryResult]:
    """Identify song via Shazam, split vocals via audio.cpp, and transcribe speech."""
    start_sec, end_sec = _chunk_bounds(req.chunk)
    mid_start = max(start_sec, (start_sec + end_sec) // 2 - cfg.shazam_slice_sec // 2)
    probe_wav = req.work_dir / "shazam_probe.wav"
    if not _slice_wav_range(req.audio_source, (mid_start, cfg.shazam_slice_sec), probe_wav):
        return None
    track = _run_shazam_with_timeout(probe_wav, cfg.shazam_timeout_sec)
    if not track:
        return None
    chunk_wav = req.work_dir / "chunk_mix.wav"
    if not _slice_wav_range(req.audio_source, (start_sec, max(1, end_sec - start_sec)), chunk_wav):
        return SongRecoveryResult(track.title, track.artist, (), None)
    try:
        vocals_wav, _ = separate_via_audiocpp_api(chunk_wav, req.work_dir / "stems", server_url=cfg.audiocpp_url)
    except Exception as exc:
        log_warn("song", f"audio.cpp separation failed ({exc})")
        return SongRecoveryResult(track.title, track.artist, (), None)
    return SongRecoveryResult(track.title, track.artist, _transcribe_vocals(vocals_wav, req, cfg), vocals_wav)


__all__ = ["SongRecoveryResult", "SongScanConfig", "SongScanRequest", "SongTriggerInput", "scan_and_recover_chunk_song", "should_scan_chunk_for_song"]
