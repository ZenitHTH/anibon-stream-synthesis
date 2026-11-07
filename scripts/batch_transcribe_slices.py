#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_transcribe_slices.py - Sliced 10-minute audio transcription via whisper-server.
Follows Clean Code principles (Robert C. Martin).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path


def fmt_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_audio_duration(audio_path: Path) -> float:
    """Extract audio duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def extract_slice_wav(audio_path: Path, offset: float, duration: float, out_wav: Path) -> bool:
    """Extract a 44.1kHz stereo 16-bit PCM WAV slice from audio using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(offset), "-t", str(duration),
        "-i", str(audio_path), "-ar", "44100", "-ac", "2",
        "-c:a", "pcm_s16le", str(out_wav)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0 and out_wav.is_file() and out_wav.stat().st_size > 0


def query_whisper_server(endpoint: str, wav_path: Path, timeout: int = 300) -> dict | None:
    """Post WAV slice to whisper.cpp server and parse verbose_json response."""
    cmd = [
        "curl", "-s", "--fail", "--max-time", str(timeout), endpoint,
        "-H", "Content-Type: multipart/form-data",
        "-F", f"file=@{wav_path}",
        "-F", "language=th",
        "-F", "temperature=0.0",
        "-F", "temperature_inc=0.0",
        "-F", "response_format=verbose_json"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def process_slice(audio_path: Path, idx: int, offset: float, dur: float, cache_dir: Path, endpoint: str) -> bool:
    """Process a single slice: check cache, extract WAV, query server, save JSON."""
    slice_json = cache_dir / f"slice_{idx:04d}.json"
    if slice_json.is_file() and slice_json.stat().st_size > 50:
        return True

    tmp_wav = cache_dir / f"_temp_slice_{idx:04d}.wav"
    for attempt in range(3):
        try:
            if not extract_slice_wav(audio_path, offset, dur, tmp_wav):
                continue
            result = query_whisper_server(endpoint, tmp_wav)
            if result and "segments" in result:
                slice_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                return True
        except Exception as e:
            sys.stderr.write(f"[!] Slice {idx:04d} attempt {attempt+1} error: {e}\n")
        finally:
            if tmp_wav.exists():
                tmp_wav.unlink()
    return False


def parse_and_shift_segment(seg: dict, offset: float) -> dict | None:
    """Shift slice-relative segment timestamps to absolute video timestamps."""
    text = seg.get("text", "").strip()
    if not text:
        return None
    start_sec = offset + float(seg.get("start", 0))
    end_sec = offset + float(seg.get("end", 0))
    return {
        "text": text,
        "start": round(start_sec, 2),
        "duration": round(max(0.0, end_sec - start_sec), 2),
        "timestamp": fmt_timestamp(start_sec)
    }


def stitch_all_slices(cache_dir: Path, num_slices: int, slice_dur: float, out_file: Path) -> int:
    """Stitch all cached slice segments into unified raw_transcript.json."""
    all_items: list[dict] = []
    for idx in range(num_slices):
        slice_json = cache_dir / f"slice_{idx:04d}.json"
        if not slice_json.is_file():
            continue
        try:
            data = json.loads(slice_json.read_text(encoding="utf-8"))
            offset = idx * slice_dur
            for s in data.get("segments", []):
                item = parse_and_shift_segment(s, offset)
                if item:
                    all_items.append(item)
        except Exception as e:
            sys.stderr.write(f"[!] Warning reading {slice_json.name}: {e}\n")

    all_items.sort(key=lambda x: x["start"])
    out_file.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(all_items)


def run_batch_transcription(audio: Path, cache_dir: Path, out_json: Path, endpoint: str, workers: int = 1) -> bool:
    """Run batch sliced transcription across all slices with worker pool."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    total_dur = get_audio_duration(audio)
    slice_dur = 600.0
    num_slices = int((total_dur + slice_dur - 1) // slice_dur)
    print(f"[*] Audio: {total_dur:.1f}s ({num_slices} slices of {slice_dur}s)", file=sys.stderr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for idx in range(num_slices):
            offset = idx * slice_dur
            dur = min(slice_dur, total_dur - offset)
            f = executor.submit(process_slice, audio, idx, offset, dur, cache_dir, endpoint)
            futures[f] = idx

        for fut in concurrent.futures.as_completed(futures):
            idx = futures[fut]
            try:
                ok = fut.result()
                status = "OK" if ok else "FAILED"
                print(f"[{status}] Slice {idx:04d}/{num_slices:04d}", file=sys.stderr)
            except Exception as e:
                print(f"[ERROR] Slice {idx:04d}: {e}", file=sys.stderr)

    count = stitch_all_slices(cache_dir, num_slices, slice_dur, out_json)
    print(f"[*] Stitched {count} segments into {out_json}", file=sys.stderr)
    return count > 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sliced 10-min audio transcription via whisper-server.")
    ap.add_argument("audio", type=Path, help="Path to audio file (audio.opus / audio.wav)")
    ap.add_argument("--workspace", "-w", type=Path, required=True, help="Workspace directory")
    ap.add_argument("--endpoint", "-e", default="http://100.115.25.30:8082/inference", help="whisper-server endpoint")
    ap.add_argument("--workers", "-j", type=int, default=1, help="Number of parallel workers")
    ap.add_argument("--stitch-only", action="store_true", help="Only stitch existing cached slices")
    args = ap.parse_args()

    cache_dir = args.workspace / "whisper_slices_cache"
    out_json = args.workspace / "raw_transcript.json"

    if args.stitch_only:
        total_dur = get_audio_duration(args.audio)
        num_slices = int((total_dur + 599) // 600)
        c = stitch_all_slices(cache_dir, num_slices, 600.0, out_json)
        print(f"[*] Stitched {c} segments into {out_json}")
        return 0 if c > 0 else 1

    ok = run_batch_transcription(args.audio, cache_dir, out_json, args.endpoint, workers=args.workers)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
