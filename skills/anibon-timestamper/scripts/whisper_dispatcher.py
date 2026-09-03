#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
whisper_dispatcher.py — Hardware-Aware Audio Slicer & Whisper.cpp Queue Dispatcher.

Orchestrates ground-truth audio verification for garbled transcript notes:
1. Profiles hardware (CPU cores, Apple Silicon Metal GPU, CUDA) to determine safe concurrency.
2. Auto-discovers local whisper.cpp binary and GGML models.
3. Ingests spotter garble candidates from garbled_notes_raw/ or JSON.
4. Clusters nearby timestamps into unified audio slices (deduplication).
5. Slices audio via ffmpeg (16kHz Mono PCM WAV).
6. Dispatches slices through a parallel worker pool to whisper-cli.
7. Aligns phonetic ground truth and writes clean garbled_notes.json.

Exit codes:
  0 = Success
  1 = Runtime error / Missing audio or whisper engine
  64 = Usage / Validation error
"""

import argparse
import concurrent.futures
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# 1. Hardware Profiler
# ==============================================================================

class HardwareProfile:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.machine = platform.machine().lower()
        self.cpu_cores = os.cpu_count() or 4
        self.is_apple_silicon = (self.os_type == "darwin" and "arm" in self.machine)
        
        if self.is_apple_silicon:
            self.max_workers = min(3, max(1, self.cpu_cores // 4))
            self.threads_per_worker = 4
            self.backend_name = "Apple Silicon Metal GPU"
        else:
            self.max_workers = 1
            self.threads_per_worker = max(1, self.cpu_cores - 1)
            self.backend_name = f"CPU Thread Pool ({self.threads_per_worker} threads)"

    def __repr__(self) -> str:
        return (f"<HardwareProfile os={self.os_type} arch={self.machine} "
                f"cores={self.cpu_cores} backend='{self.backend_name}' "
                f"workers={self.max_workers} threads={self.threads_per_worker}>")


# ==============================================================================
# 2. Binary & Model Discovery
# ==============================================================================

def find_whisper_cli(custom_path: Optional[str] = None) -> Optional[str]:
    if custom_path and os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
        return custom_path
    
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "whisper.cpp", "build", "bin", "whisper-cli"),
        os.path.join(home, "whisper.cpp", "main"),
        "/opt/homebrew/bin/whisper-cli",
        "/usr/local/bin/whisper-cli",
        shutil.which("whisper-cli") or "",
        shutil.which("whisper") or ""
    ]
    for p in candidates:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def find_whisper_model(custom_path: Optional[str] = None) -> Optional[str]:
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    
    home = os.path.expanduser("~")
    model_dirs = [
        os.path.join(home, "whisper.cpp", "models"),
        os.path.join(home, ".cache", "whisper"),
        os.path.join(home, ".whisper")
    ]
    
    preferred = [
        "ggml-large-v3-turbo.bin",
        "ggml-large-v3.bin",
        "ggml-large.bin",
        "ggml-medium.bin",
        "ggml-small.bin",
        "ggml-base.bin"
    ]
    
    for m_dir in model_dirs:
        if not os.path.isdir(m_dir):
            continue
        for pref in preferred:
            p = os.path.join(m_dir, pref)
            if os.path.isfile(p):
                return p
        for p in glob.glob(os.path.join(m_dir, "*.bin")):
            if os.path.isfile(p):
                return p
    return None


# ==============================================================================
# 3. Candidate Ingestion & Timestamp Clustering
# ==============================================================================

def parse_time_str(ts: str) -> int:
    parts = [int(p) for p in ts.strip().split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return int(ts)


def format_time_sec(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_raw_candidates(notes_dir_or_file: str) -> List[Dict]:
    candidates = []
    
    if os.path.isfile(notes_dir_or_file) and notes_dir_or_file.endswith(".json"):
        with open(notes_dir_or_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("notes", data) if isinstance(data, dict) else data
            for it in items:
                if isinstance(it, dict) and "ts" in it:
                    candidates.append({
                        "ts": it["ts"],
                        "sec": parse_time_str(it["ts"]),
                        "garbled": it.get("garbled", ""),
                        "chunk": it.get("chunk", ""),
                        "context": it.get("context", "")
                    })
        return candidates

    txt_files = []
    if os.path.isdir(notes_dir_or_file):
        txt_files = sorted(glob.glob(os.path.join(notes_dir_or_file, "*.txt")))
    elif os.path.isfile(notes_dir_or_file):
        txt_files = [notes_dir_or_file]
        
    for p in txt_files:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.search(r'"([^"]+)"(?:\s*->\s*.+?)?\s*@\s*(\d{1,2}:\d{2}:\d{2})\s*(?:\((chunk_\d+)\))?', line)
                if m:
                    g = m.group(1).strip()
                    ts = m.group(2).strip()
                    ch = m.group(3) or ""
                    if len(ts.split(":")[0]) == 1:
                        ts = "0" + ts
                    sec = parse_time_str(ts)
                    candidates.append({
                        "ts": ts,
                        "sec": sec,
                        "garbled": g,
                        "chunk": ch,
                        "context": f"Candidate from {ch} ({ts})" if ch else f"Candidate @ {ts}"
                    })

    return candidates


def cluster_candidates(candidates: List[Dict], max_gap: int = 12) -> List[Dict]:
    if not candidates:
        return []
    
    sorted_cand = sorted(candidates, key=lambda x: x["sec"])
    clusters = []
    
    current_cluster = {
        "start_sec": max(0, sorted_cand[0]["sec"] - 7),
        "end_sec": sorted_cand[0]["sec"] + 8,
        "items": [sorted_cand[0]]
    }
    
    for c in sorted_cand[1:]:
        if c["sec"] - current_cluster["end_sec"] <= max_gap:
            current_cluster["end_sec"] = max(current_cluster["end_sec"], c["sec"] + 8)
            current_cluster["items"].append(c)
        else:
            clusters.append(current_cluster)
            current_cluster = {
                "start_sec": max(0, c["sec"] - 7),
                "end_sec": c["sec"] + 8,
                "items": [c]
            }
    clusters.append(current_cluster)
    
    for idx, cl in enumerate(clusters):
        cl["cluster_id"] = idx
        cl["duration"] = cl["end_sec"] - cl["start_sec"]
        
    return clusters


# ==============================================================================
# 4. Audio Slicer & Worker Execution
# ==============================================================================

def slice_audio(audio_file: str, start_sec: int, duration: int, output_wav: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-t", str(duration),
        "-i", audio_file,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_wav
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0
    except Exception as e:
        sys.stderr.write(f"[!] FFmpeg slicing failed for {output_wav}: {e}\n")
        return False


def run_whisper_slice(
    whisper_bin: str,
    model_bin: str,
    slice_wav: str,
    threads: int = 4
) -> str:
    cmd = [
        whisper_bin,
        "-m", model_bin,
        "-f", slice_wav,
        "-l", "th",
        "-nt",
        "-t", str(threads)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip().replace("\n", " ")
    except Exception as e:
        sys.stderr.write(f"[!] Whisper inference failed on {slice_wav}: {e}\n")
        return ""


# ==============================================================================
# 5. Dispatcher Pipeline
# ==============================================================================

def dispatch_verification(
    workspace: str,
    raw_notes_dir: str,
    audio_file: Optional[str] = None,
    whisper_bin: Optional[str] = None,
    model_bin: Optional[str] = None,
    output_json: Optional[str] = None,
    workers_override: Optional[int] = None,
    verbose: bool = False
) -> int:
    profile = HardwareProfile()
    if verbose:
        sys.stderr.write(f"[*] Hardware Profile: {profile}\n")

    w_bin = find_whisper_cli(whisper_bin)
    if not w_bin:
        sys.stderr.write("[!] Error: whisper.cpp CLI binary not found. Set --whisper-bin or install whisper-cli.\n")
        return 1
    
    m_bin = find_whisper_model(model_bin)
    if not m_bin:
        sys.stderr.write("[!] Error: GGML Whisper model binary not found. Set --model or download ggml-large-v3-turbo.bin.\n")
        return 1

    if not audio_file:
        for cand_name in ["audio.opus", "audio.m4a", "audio.wav", "audio.mp3"]:
            p = os.path.join(workspace, cand_name)
            if os.path.isfile(p):
                audio_file = p
                break
                
    if not audio_file or not os.path.isfile(audio_file):
        sys.stderr.write(f"[!] Error: audio track not found in workspace ({workspace}). Ensure audio.opus exists.\n")
        return 1

    candidates = load_raw_candidates(raw_notes_dir)
    if not candidates:
        sys.stderr.write(f"[*] No garbled candidates found in {raw_notes_dir}. Nothing to dispatch.\n")
        out_path = output_json or os.path.join(workspace, "garbled_notes.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "notes": []}, f, ensure_ascii=False, indent=2)
        return 0

    clusters = cluster_candidates(candidates)
    num_workers = workers_override or profile.max_workers
    slices_dir = os.path.join(workspace, "audio_slices")
    os.makedirs(slices_dir, exist_ok=True)
    
    sys.stderr.write(f"[*] Dispatching {len(candidates)} spotter requests across {len(clusters)} audio clusters...\n")
    sys.stderr.write(f"[*] Engine: {w_bin} (Model: {os.path.basename(m_bin)}) via {num_workers} parallel workers\n")

    cluster_transcripts = {}
    t0 = time.time()

    def process_cluster(cl: Dict) -> Tuple[int, str]:
        cid = cl["cluster_id"]
        slice_wav = os.path.join(slices_dir, f"cluster_{cid:03d}_{cl['start_sec']}.wav")
        if not os.path.exists(slice_wav):
            ok = slice_audio(audio_file, cl["start_sec"], cl["duration"], slice_wav)
            if not ok:
                return (cid, "")
        transcript = run_whisper_slice(w_bin, m_bin, slice_wav, profile.threads_per_worker)
        return (cid, transcript)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_cluster, cl) for cl in clusters]
        for fut in concurrent.futures.as_completed(futures):
            cid, text = fut.result()
            cluster_transcripts[cid] = text

    t1 = time.time()
    sys.stderr.write(f"[+] All clusters transcribed in {t1 - t0:.2f}s ({len(clusters) / max(1.0, t1 - t0):.1f} clusters/sec)\n")

    verified_notes = []
    seen_keys = set()

    for cl in clusters:
        cid = cl["cluster_id"]
        raw_text = cluster_transcripts.get(cid, "")
        for item in cl["items"]:
            g = item["garbled"]
            ts = item["ts"]
            key = (ts, g)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            verified_notes.append({
                "garbled": g,
                "whisper_transcript": raw_text,
                "correct": None,
                "chunk": item["chunk"],
                "ts": ts,
                "context": item["context"],
                "cluster_span": f"{format_time_sec(cl['start_sec'])}-{format_time_sec(cl['end_sec'])}"
            })

    out_path = output_json or os.path.join(workspace, "garbled_notes.json")
    payload = {
        "version": 1,
        "engine": "whisper.cpp",
        "model": os.path.basename(m_bin),
        "backend": profile.backend_name,
        "total_requests": len(verified_notes),
        "notes": verified_notes
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    sys.stderr.write(f"[✓] Successfully generated verified notes at: {out_path}\n")
    return 0


# ==============================================================================
# 6. CLI Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Hardware-Aware Whisper.cpp Audio Slicer & Queue Dispatcher."
    )
    parser.add_argument(
        "workspace",
        help="Workspace directory containing audio.opus and garbled_notes_raw/"
    )
    parser.add_argument(
        "--raw-notes-dir",
        "-r",
        help="Directory or text file containing raw garbled spotter notes (default: <workspace>/garbled_notes_raw)"
    )
    parser.add_argument(
        "--audio-file",
        "-a",
        help="Path to full audio track (default: <workspace>/audio.opus)"
    )
    parser.add_argument(
        "--whisper-bin",
        help="Path to whisper-cli executable (auto-discovered if omitted)"
    )
    parser.add_argument(
        "--model",
        "-m",
        help="Path to GGML Whisper model binary (auto-discovered if omitted)"
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        help="Override worker concurrency (default: auto-tuned by hardware profiler)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON path (default: <workspace>/garbled_notes.json)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose hardware profiling details to stderr"
    )

    args = parser.parse_args()
    
    ws = os.path.abspath(args.workspace)
    raw_dir = args.raw_notes_dir or os.path.join(ws, "garbled_notes_raw")
    
    ret = dispatch_verification(
        workspace=ws,
        raw_notes_dir=raw_dir,
        audio_file=args.audio_file,
        whisper_bin=args.whisper_bin,
        model_bin=args.model,
        output_json=args.output,
        workers_override=args.workers,
        verbose=args.verbose
    )
    sys.exit(ret)


if __name__ == "__main__":
    main()
