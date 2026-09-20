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
import threading
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
        self.device_id = None
        
        if self.is_apple_silicon:
            self.max_workers = min(3, max(1, self.cpu_cores // 4))
            self.threads_per_worker = 4
            self.backend_name = "Apple Silicon Metal GPU"
        elif self.os_type == "windows":
            # Check for Tesla P100 (Vulkan device 1)
            self.max_workers = 2
            self.threads_per_worker = 4
            self.device_id = 1
            self.backend_name = "Tesla P100 Vulkan GPU (device 1)"
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
        if p and os.name == "nt" and os.path.isfile(p + ".exe"):
            return p + ".exe"
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


def load_master_dictionary_matcher() -> List[Tuple[re.Pattern, str]]:
    """Load compiled patterns from garbled_replacements.json to pre-resolve known tokens."""
    home = os.path.expanduser("~")
    search_paths = [
        os.path.join(home, ".gemini/config/plugins/anibon-stream-synthesis/resources/garbled_replacements.json"),
        os.path.join(home, "abss-dev/resources/garbled_replacements.json"),
    ]
    compiled = []
    for sp in search_paths:
        if os.path.isfile(sp):
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mappings = data.get("mappings", {})
                pairs = []
                for target, patterns in mappings.items():
                    pats = patterns if isinstance(patterns, list) else [patterns]
                    for p in pats:
                        p_str = str(p).strip()
                        if p_str:
                            pairs.append((p_str, str(target).strip()))
                pairs.sort(key=lambda x: len(x[0]), reverse=True)
                for pat, rep in pairs:
                    try:
                        compiled.append((re.compile(pat, re.IGNORECASE), rep))
                    except re.error:
                        pass
                if compiled:
                    break
            except Exception:
                pass
    return compiled


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
                        "correct": it.get("correct", None)
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
                m = re.search(r'"([^"]+)"(?:\s*->\s*([^@]+?))?\s*@\s*(\d{1,2}:\d{2}:\d{2})\s*(?:\((chunk_\d+)\))?', line)
                if m:
                    g = m.group(1).strip()
                    correct_raw = (m.group(2) or "").strip()
                    is_unknown = not correct_raw or correct_raw.upper() in ["UNKNOWN", "NULL", "NONE"]
                    correct = None if is_unknown else correct_raw
                    ts = m.group(3).strip()
                    ch = m.group(4) or ""
                    if len(ts.split(":")[0]) == 1:
                        ts = "0" + ts
                    sec = parse_time_str(ts)
                    candidates.append({
                        "ts": ts,
                        "sec": sec,
                        "garbled": g,
                        "chunk": ch,
                        "correct": correct
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


def extract_google_context(
    events: List[Dict],
    target_sec: int,
    window_before_sec: int = 5,
    window_after_sec: int = 5
) -> str:
    """Extract surrounding Google ASR sentence words from raw_transcript.th-orig.json3."""
    target_ms = target_sec * 1000
    before_ms = window_before_sec * 1000
    after_ms = window_after_sec * 1000
    tokens = []
    for ev in events:
        t = ev.get("tStartMs", 0)
        d = ev.get("dDurationMs", 0) or 0
        if t + d >= target_ms - before_ms and t <= target_ms + after_ms:
            for s in ev.get("segs", []):
                txt = s.get("utf8", "")
                if txt.strip():
                    tokens.append(txt.strip())
    return " ".join(tokens)


def align_whisper_segments(
    whisper_segments: List[Dict],
    rel_sec: float,
    tolerance_sec: float = 2.5
) -> str:
    """Find the specific Whisper segment(s) closest to the candidate relative timestamp."""
    matched = []
    for seg in whisper_segments:
        offsets = seg.get("offsets", {})
        start_sec = offsets.get("from", 0) / 1000.0
        end_sec = offsets.get("to", 0) / 1000.0
        if start_sec - tolerance_sec <= rel_sec <= end_sec + tolerance_sec:
            matched.append(seg)
    if not matched and whisper_segments:
        closest = min(
            whisper_segments,
            key=lambda s: abs((s.get("offsets", {}).get("from", 0) + s.get("offsets", {}).get("to", 0)) / 2000.0 - rel_sec)
        )
        matched = [closest]
    texts = [s.get("text", "").strip() for s in matched if s.get("text", "").strip()]
    return " ".join(texts)


def run_whisper_slice(
    whisper_bin: str,
    model_bin: str,
    slice_wav: str,
    threads: int = 4,
    device_id: Optional[int] = None
) -> Tuple[str, List[Dict]]:
    """Run whisper-cli on audio slice and extract both full text and timed segments."""
    base_no_ext = os.path.splitext(slice_wav)[0]
    json_out = base_no_ext + ".json"
    cmd = [
        whisper_bin,
        "-m", model_bin,
        "-f", slice_wav,
        "-l", "th",
        "-oj",
        "-of", base_no_ext,
        "-t", str(threads),
        "-nf",
        "-bo", "1",
        "-bs", "1"
    ]
    if device_id is not None:
        cmd.extend(["-dev", str(device_id)])
    if os.path.exists(json_out) and os.path.getsize(json_out) > 0:
        try:
            with open(json_out, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            segments = data.get("transcription", [])
            full_text = " ".join(s.get("text", "").strip() for s in segments if s.get("text", "").strip())
            return (full_text, segments)
        except Exception:
            pass

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(json_out):
            with open(json_out, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            segments = data.get("transcription", [])
            full_text = " ".join(s.get("text", "").strip() for s in segments if s.get("text", "").strip())
            return (full_text, segments)
    except Exception as e:
        sys.stderr.write(f"[!] Whisper inference with JSON output failed on {slice_wav}: {e}\n")

    # Fallback to plain text CLI if -oj failed
    fallback_cmd = [
        whisper_bin,
        "-m", model_bin,
        "-f", slice_wav,
        "-l", "th",
        "-nt",
        "-t", str(threads),
        "-nf",
        "-bo", "1",
        "-bs", "1"
    ]
    if device_id is not None:
        fallback_cmd.extend(["-dev", str(device_id)])
    try:
        res = subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
        return (res.stdout.strip().replace("\n", " "), [])
    except Exception as e:
        sys.stderr.write(f"[!] Whisper fallback inference failed on {slice_wav}: {e}\n")
        return ("", [])


def get_youtube_stream_url(video_url: str) -> Optional[str]:
    """Retrieve direct HTTPS stream URL via Android client or browser cookies."""
    # 1. Try Android client first
    cmd = [
        "yt-dlp",
        "--extractor-args", "youtube:player_client=android",
        "-g",
        "-f", "18/ba/b",
        video_url
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = res.stdout.strip().splitlines()[0].strip()
        if url.startswith("http"):
            # Verify stream URL is playable
            check = subprocess.run(["ffmpeg", "-y", "-ss", "0", "-t", "1", "-i", url, "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                return url
    except Exception:
        pass

    # 2. Fallback to browser cookies (Chrome, Brave, Firefox, Edge, Safari)
    for b in ["chrome", "brave", "firefox", "edge", "safari"]:
        try:
            cmd = ["yt-dlp", "--cookies-from-browser", b, "-g", "-f", "140/ba/b", video_url]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip().startswith("http"):
                url = res.stdout.strip().splitlines()[0].strip()
                return url
        except Exception:
            continue

    sys.stderr.write(f"[!] Warning: failed to fetch playable YouTube stream URL for {video_url}\n")
    return None


def detect_audio_transcript_offset(
    audio_source: str,
    raw_th_orig_path: str,
    whisper_bin: str,
    model_bin: str,
    threads: int = 4,
    device_id: Optional[int] = None
) -> float:
    """Detect standby/intro time offset between raw Google transcript and actual audio stream.
    
    Uses multi-anchor longest-substring matching to robustly distinguish actual speech
    from false matches during background standby or pre-stream countdowns.
    Returns offset in seconds (audio_time = transcript_time + offset).
    """
    import difflib
    import tempfile
    if not os.path.isfile(raw_th_orig_path):
        return 0.0

    try:
        with open(raw_th_orig_path, "r", encoding="utf-8") as f:
            events = json.load(f).get("events", [])
    except Exception:
        return 0.0

    # Build reference text from opening 30 seconds of transcript
    speech_ref = ""
    first_speech_sec = 0.0
    for ev in events:
        t = ev.get("tStartMs", 0) / 1000.0
        if t <= 30.0:
            for s in ev.get("segs", []):
                txt = s.get("utf8", "")
                if txt.strip() and not first_speech_sec and not txt.strip().startswith("["):
                    first_speech_sec = t
                speech_ref += txt
    ref_clean = "".join(c for c in speech_ref if c.isalnum())
    if not ref_clean:
        return 0.0

    tmp_dir = tempfile.gettempdir()
    # 1. Quick probe 0s (verify if video audio and transcript start in sync)
    test_wav0 = os.path.join(tmp_dir, "_sync_probe_0.wav")
    for ext in [".wav", ".json"]:
        p = os.path.join(tmp_dir, f"_sync_probe_0{ext}")
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    if slice_audio(audio_source, 0, 20, test_wav0):
        txt0, _ = run_whisper_slice(whisper_bin, model_bin, test_wav0, threads=threads, device_id=device_id)
        t0_c = "".join(c for c in txt0 if c.isalnum())
        m0 = difflib.SequenceMatcher(None, t0_c, ref_clean).find_longest_match(0, len(t0_c), 0, len(ref_clean)).size
        for ext in [".wav", ".json"]:
            p = os.path.join(tmp_dir, f"_sync_probe_0{ext}")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        if m0 >= 15:
            return 0.0

    # 2. Fast silence detection to identify candidate standby exits
    silence_ends = []
    try:
        res = subprocess.run(
            ["ffmpeg", "-t", "900", "-i", audio_source, "-af", "silencedetect=noise=-30dB:d=3", "-f", "null", "-"],
            capture_output=True, text=True
        )
        for line in res.stderr.splitlines():
            if "silence_end:" in line:
                s_end = float(line.split("silence_end:")[1].split("|")[0].strip())
                silence_ends.append(s_end)
    except Exception:
        pass

    # Jump candidates: detected silence boundaries + fallback 120s grid
    candidates = sorted(list(set([int(s) for s in silence_ends] + list(range(120, 900, 120)))))

    best_sec = 0
    best_len = 0
    for cand in candidates:
        wav = os.path.join(tmp_dir, f"_cand_probe_{cand}.wav")
        for ext in [".wav", ".json"]:
            p = os.path.join(tmp_dir, f"_cand_probe_{cand}{ext}")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        if not slice_audio(audio_source, cand, 25, wav):
            continue
        txt, _ = run_whisper_slice(whisper_bin, model_bin, wav, threads=threads, device_id=device_id)
        for ext in [".wav", ".json"]:
            p = os.path.join(tmp_dir, f"_cand_probe_{cand}{ext}")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        tc = "".join(c for c in txt if c.isalnum())
        m = difflib.SequenceMatcher(None, tc, ref_clean, autojunk=False).find_longest_match(0, len(tc), 0, len(ref_clean)).size
        if m > best_len:
            best_len = m
            best_sec = cand
        if m >= 12:
            break

    if best_len < 4:
        return 0.0

    # 3. Fine alignment via single JSON slice around best_sec
    fine_start = max(0, best_sec - 10)
    fine_wav = os.path.join(tmp_dir, "_fine_align_slice.wav")
    for ext in [".wav", ".json"]:
        p = os.path.join(tmp_dir, f"_fine_align_slice{ext}")
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    if not slice_audio(audio_source, fine_start, 45, fine_wav):
        return float(best_sec)

    _, segments = run_whisper_slice(whisper_bin, model_bin, fine_wav, threads=threads, device_id=device_id)
    for ext in [".wav", ".json"]:
        p = os.path.join(tmp_dir, f"_fine_align_slice{ext}")
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    if not segments:
        return float(best_sec)

    best_seg = None
    best_seg_len = 0
    best_match_b = 0
    for seg in segments:
        tc = "".join(c for c in seg.get("text", "") if c.isalnum())
        m = difflib.SequenceMatcher(None, tc, ref_clean, autojunk=False).find_longest_match(0, len(tc), 0, len(ref_clean))
        if m.size > best_seg_len:
            best_seg_len = m.size
            best_seg = seg
            best_match_b = m.b

    if best_seg and best_seg_len >= 5:
        # Find the transcript timestamp corresponding to match index m.b
        matched_t = first_speech_sec
        curr_chars = 0
        for ev in events:
            t = ev.get("tStartMs", 0) / 1000.0
            found = False
            for s in ev.get("segs", []):
                w_c = "".join(c for c in s.get("utf8", "") if c.isalnum())
                if curr_chars + len(w_c) >= best_match_b:
                    matched_t = t
                    found = True
                    break
                curr_chars += len(w_c)
            if found:
                break

        rel_from = best_seg.get("offsets", {}).get("from", 0) / 1000.0
        audio_event_time = fine_start + rel_from
        offset = max(0.0, audio_event_time - matched_t)
        return round(offset, 1)

    return float(best_sec)


# ==============================================================================
# 5. Dispatcher Pipeline
# ==============================================================================

def dispatch_verification(
    workspace: str,
    raw_notes_dir: str,
    audio_file: Optional[str] = None,
    video_url: Optional[str] = None,
    stream_url: Optional[str] = None,
    whisper_bin: Optional[str] = None,
    model_bin: Optional[str] = None,
    output_json: Optional[str] = None,
    workers_override: Optional[int] = None,
    offset_sec: Optional[float] = None,
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

    candidates = load_raw_candidates(raw_notes_dir)
    if not candidates:
        sys.stderr.write(f"[*] No garbled candidates found in {raw_notes_dir}. Nothing to dispatch.\n")
        out_path = output_json or os.path.join(workspace, "garbled_notes.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "notes": []}, f, ensure_ascii=False, indent=2)
        return 0

    clusters = cluster_candidates(candidates)
    slices_dir = os.path.join(workspace, "audio_slices")
    os.makedirs(slices_dir, exist_ok=True)

    # Resolve audio source if needed
    audio_source = audio_file
    if not audio_source:
        for cand_name in ["audio.opus", "audio.m4a", "audio.wav", "audio.mp3"]:
            p = os.path.join(workspace, cand_name)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                audio_source = p
                break

    if not audio_source:
        if stream_url:
            audio_source = stream_url
        elif video_url:
            audio_source = get_youtube_stream_url(video_url)

    # Auto-calibrate or apply audio-to-transcript timeline offset
    raw_th_orig = os.path.join(workspace, "raw_transcript.th-orig.json3")
    if not os.path.exists(raw_th_orig):
        for cand in ["raw_transcript.json", "raw_transcript.th.json3"]:
            p = os.path.join(workspace, cand)
            if os.path.exists(p):
                raw_th_orig = p
                break

    if offset_sec is None:
        sys.stderr.write("[*] Calibrating audio-to-transcript timeline offset...\n")
        offset_sec = detect_audio_transcript_offset(audio_source, raw_th_orig, w_bin, m_bin, profile.threads_per_worker, device_id=profile.device_id)
        if offset_sec > 0:
            sys.stderr.write(f"[*] Detected audio-to-transcript standby offset: +{offset_sec:.1f}s (auto-aligned)\n")
        else:
            sys.stderr.write("[*] Timeline offset: 0.0s (direct sync)\n")
            offset_sec = 0.0
    else:
        sys.stderr.write(f"[*] Using timeline offset: +{offset_sec:.1f}s\n")

    # Check which clusters need slicing
    missing_clusters = []
    for cl in clusters:
        cid = cl["cluster_id"]
        slice_name = f"cluster_{cid:03d}_{cl['start_sec']}_off{int(offset_sec)}.wav" if offset_sec else f"cluster_{cid:03d}_{cl['start_sec']}.wav"
        slice_wav = os.path.join(slices_dir, slice_name)
        if not (os.path.exists(slice_wav) and os.path.getsize(slice_wav) > 0):
            missing_clusters.append(cl)

    if missing_clusters and not audio_source:
        if video_url:
            sys.stderr.write(f"[*] Slices needed ({len(missing_clusters)} clusters). Fetching stream URL for {video_url}...\n")
            audio_source = get_youtube_stream_url(video_url)

    if missing_clusters and not audio_source:
        sys.stderr.write(
            f"[!] Error: {len(missing_clusters)} audio clusters need slicing, but no audio source found.\n"
            f"    Provide a local audio track (audio.opus in {workspace}), pass --audio-file, or provide --video-url.\n"
        )
        return 1
    
    num_workers = workers_override or profile.max_workers
    sys.stderr.write(f"[*] Dispatching {len(candidates)} spotter requests across {len(clusters)} audio clusters...\n")
    sys.stderr.write(f"[*] Engine: {w_bin} (Model: {os.path.basename(m_bin)}) via {num_workers} parallel workers\n")

    # Load raw Google transcript if available in workspace
    google_events = []
    if os.path.exists(raw_th_orig):
        try:
            with open(raw_th_orig, "r", encoding="utf-8") as f:
                google_events = json.load(f).get("events", [])
        except Exception as e:
            sys.stderr.write(f"[*] Note: could not load Google transcript {raw_th_orig}: {e}\n")

    cluster_transcripts = {}
    cluster_segments = {}
    t0 = time.time()
    failed_slices = []
    consecutive_fails = 0
    fail_lock = threading.Lock()

    def process_cluster(cl: Dict) -> Tuple[int, str, List[Dict]]:
        nonlocal consecutive_fails
        cid = cl["cluster_id"]
        slice_name = f"cluster_{cid:03d}_{cl['start_sec']}_off{int(offset_sec)}.wav" if offset_sec else f"cluster_{cid:03d}_{cl['start_sec']}.wav"
        slice_wav = os.path.join(slices_dir, slice_name)
        slice_start = max(0, int(cl["start_sec"] + offset_sec))
        if not (os.path.exists(slice_wav) and os.path.getsize(slice_wav) > 0):
            ok = slice_audio(audio_source, slice_start, cl["duration"], slice_wav)
            if not ok:
                with fail_lock:
                    failed_slices.append(cid)
                    consecutive_fails += 1
                    if consecutive_fails == 5:
                        sys.stderr.write(
                            "\n[!] CRITICAL ALERT: 5 consecutive FFmpeg slicing failures detected!\n"
                            "    The network connection was severed or the system entered sleep mode.\n"
                        )
                return (cid, "", [])
        with fail_lock:
            consecutive_fails = 0
        full_text, segments = run_whisper_slice(w_bin, m_bin, slice_wav, profile.threads_per_worker, device_id=profile.device_id)
        return (cid, full_text, segments)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_cluster, cl) for cl in clusters]
        for fut in concurrent.futures.as_completed(futures):
            cid, text, segs = fut.result()
            cluster_transcripts[cid] = text
            cluster_segments[cid] = segs

    t1 = time.time()
    sys.stderr.write(f"[+] All clusters processed in {t1 - t0:.2f}s ({len(clusters) / max(1.0, t1 - t0):.1f} clusters/sec)\n")
    if failed_slices:
        sys.stderr.write(
            f"[!] Warning: {len(failed_slices)}/{len(clusters)} audio clusters failed to slice.\n"
        )
        if len(failed_slices) / len(clusters) > 0.2:
            sys.stderr.write(
                f"[!] CRITICAL: High failure rate ({(len(failed_slices)/len(clusters))*100:.1f}%). "
                f"Slices likely dropped due to laptop sleep or network interruption.\n"
            )

    dict_matchers = load_master_dictionary_matcher()
    verified_notes = []
    seen_keys = set()

    for cl in clusters:
        cid = cl["cluster_id"]
        raw_text = cluster_transcripts.get(cid, "")
        segs = cluster_segments.get(cid, [])
        slice_start = max(0, int(cl["start_sec"] + offset_sec))
        for item in cl["items"]:
            g = item["garbled"]
            ts = item["ts"]
            key = (ts, g)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            cand_sec = item["sec"]
            rel_sec = max(0.0, (cand_sec + offset_sec) - slice_start)

            # Extract surrounding Google ASR sentence words
            google_sentence = ""
            if google_events:
                google_sentence = extract_google_context(google_events, cand_sec)

            # Find matching Whisper segment(s) around the candidate timestamp
            whisper_seg_text = align_whisper_segments(segs, rel_sec) if segs else raw_text
            if not whisper_seg_text:
                whisper_seg_text = raw_text

            # Check if candidate has existing correct value or matches master dictionary
            resolved = item.get("correct")
            if not resolved and dict_matchers:
                for pat, rep in dict_matchers:
                    if pat.search(g):
                        resolved = rep
                        break

            verified_notes.append({
                "garbled": g,
                "google_sentence": google_sentence,
                "whisper_segment": whisper_seg_text,
                "correct": resolved,
                "chunk": item["chunk"],
                "ts": ts,
                "cluster_span": f"{format_time_sec(cl['start_sec'])}-{format_time_sec(cl['end_sec'])}"
            })

    out_path = output_json or os.path.join(workspace, "garbled_notes.json")
    status_str = "PARTIAL_FAILURE_NETWORK_SUSPENDED" if (failed_slices and len(failed_slices) / len(clusters) > 0.2) else "SUCCESS"
    payload = {
        "version": 1,
        "engine": "whisper.cpp",
        "model": os.path.basename(m_bin),
        "backend": profile.backend_name,
        "audio_offset_sec": offset_sec,
        "status": status_str,
        "total_clusters": len(clusters),
        "failed_slices": len(failed_slices),
        "total_requests": len(verified_notes),
        "notes": verified_notes
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    sys.stderr.write(f"[✓] Successfully generated verified notes at: {out_path} (Status: {status_str})\n")
    return 0


# ==============================================================================
# 6. CLI Entrypoint
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
        "--raw-notes-dir", "-r",
        help="Directory or text file containing raw garbled spotter notes (default: <workspace>/garbled_notes_raw)"
    )
    parser.add_argument(
        "--audio-file", "-a",
        help="Path to full audio track (default: <workspace>/audio.opus)"
    )
    parser.add_argument(
        "--video-url", "-u",
        help="YouTube video URL. If audio track is missing, fetches direct Android stream URL to slice clusters on-the-fly."
    )
    parser.add_argument(
        "--stream-url",
        help="Direct HTTPS stream URL for on-the-fly slicing without local audio track."
    )
    parser.add_argument(
        "--whisper-bin",
        help="Path to whisper-cli executable (auto-discovered if omitted)"
    )
    parser.add_argument(
        "--model", "-m",
        help="Path to GGML Whisper model binary (auto-discovered if omitted)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        help="Override worker concurrency (default: auto-tuned by hardware profiler)"
    )
    parser.add_argument(
        "--offset-sec",
        type=float,
        default=None,
        help="Audio-to-transcript time offset in seconds (auto-detected if omitted)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON path (default: <workspace>/garbled_notes.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
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
        video_url=args.video_url,
        stream_url=args.stream_url,
        whisper_bin=args.whisper_bin,
        model_bin=args.model,
        output_json=args.output,
        workers_override=args.workers,
        offset_sec=args.offset_sec,
        verbose=args.verbose
    )
    sys.exit(ret)


if __name__ == "__main__":
    main()
