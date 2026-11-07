#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "numpy",
#     "scipy",
# ]
# ///
"""
Reconcile Timestamps for Post-Stream Edited / Trimmed YouTube Videos.
Detects cut points between raw livestream audio and YouTube VOD via 1000Hz FFT
cross-correlation, then maps timestamps without re-transcribing.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import scipy.signal

SAMPLE_RATE_HZ = 1000
PCM_TYPE = np.int16
BYTES_PER_SAMPLE = 2


@dataclass(frozen=True)
class CutInterval:
    """Represents a segment deleted from the original livestream."""
    start_orig: float
    end_orig: float
    cut_at_edit: float
    duration: float


def parse_timestr_to_seconds(timestr: str) -> int:
    """Convert HH:MM:SS string to integer seconds."""
    parts = [int(p) for p in timestr.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    raise ValueError(f"Invalid timestamp format: {timestr}")


def format_seconds_to_timestr(seconds: float) -> str:
    """Convert seconds to HH:MM:SS string."""
    s = int(round(max(0.0, seconds)))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_online_duration_seconds(video_url: str) -> float | None:
    """Query current online video duration via yt-dlp."""
    cmd = ["yt-dlp", "--get-duration", video_url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        dur_str = res.stdout.strip()
        return float(parse_timestr_to_seconds(dur_str))
    except (subprocess.CalledProcessError, ValueError):
        return None


def get_audio_file_duration_seconds(audio_path: str) -> float:
    """Get local audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def download_edited_audio(video_url: str, out_audio_path: str) -> None:
    """Download low-bitrate opus audio stream from YouTube."""
    cmd = ["yt-dlp", "-f", "249/250/139/ba", video_url, "-o", out_audio_path]
    subprocess.run(cmd, check=True)


def extract_1000hz_raw(audio_path: str, raw_out_path: str) -> None:
    """Downsample audio to 1000Hz mono 16-bit PCM for fast in-memory alignment."""
    cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", str(SAMPLE_RATE_HZ), "-ac", "1",
        "-f", "s16le", raw_out_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def match_offset_at(
    edit_sig: np.ndarray,
    orig_sig: np.ndarray,
    t_edit: float,
    expected_offset: float,
    window_sec: float = 3.0,
    search_margin_sec: float = 15.0
) -> tuple[float | None, float]:
    """Find local time offset between edit and orig signal via FFT correlation."""
    idx_edit = int(t_edit * SAMPLE_RATE_HZ)
    w_samples = int(window_sec * SAMPLE_RATE_HZ)
    if idx_edit + w_samples > len(edit_sig):
        return None, 0.0

    snippet = edit_sig[idx_edit : idx_edit + w_samples]
    std = float(np.std(snippet))
    if std < 1.0:
        return None, 0.0
    snippet_norm = (snippet - np.mean(snippet)) / std

    center_orig = t_edit + expected_offset
    start_orig = max(0.0, center_orig - search_margin_sec)
    end_orig = min(len(orig_sig) / SAMPLE_RATE_HZ, center_orig + search_margin_sec + window_sec)

    idx_start = int(start_orig * SAMPLE_RATE_HZ)
    idx_end = int(end_orig * SAMPLE_RATE_HZ)
    target = orig_sig[idx_start:idx_end]
    if len(target) < w_samples:
        return None, 0.0

    target_norm = (target - np.mean(target)) / (np.std(target) + 1e-6)
    corr = scipy.signal.fftconvolve(target_norm, snippet_norm[::-1], mode="valid")
    best_idx = int(np.argmax(corr))
    peak_quality = float(corr[best_idx] / w_samples)

    matched_orig = start_orig + (best_idx / float(SAMPLE_RATE_HZ))
    return (matched_orig - t_edit), peak_quality


def refine_boundary(
    edit_sig: np.ndarray,
    orig_sig: np.ndarray,
    t_low: float,
    t_high: float,
    off_before: float
) -> float:
    """Binary search cut boundary where offset jumps."""
    for _ in range(20):
        t_mid = (t_low + t_high) / 2.0
        off, q = match_offset_at(edit_sig, orig_sig, t_mid, off_before, window_sec=1.5, search_margin_sec=5.0)
        if off is not None and q > 0.6 and abs(off - off_before) < 0.5:
            t_low = t_mid
        else:
            t_high = t_mid
    return (t_low + t_high) / 2.0


def scan_offset_curve(
    edit_sig: np.ndarray,
    orig_sig: np.ndarray,
    step_sec: int = 180
) -> list[tuple[float, float]]:
    """Sample time offsets across edited audio."""
    samples: list[tuple[float, float]] = []
    edit_len = len(edit_sig) / SAMPLE_RATE_HZ
    cur_offset = 0.0

    for t in range(60, int(edit_len) - 60, step_sec):
        off, q = match_offset_at(edit_sig, orig_sig, float(t), cur_offset, search_margin_sec=10000.0)
        if off is not None and q > 0.4:
            cur_offset = off
            samples.append((float(t), off))
    return samples


def detect_cut_intervals(
    orig_sig: np.ndarray,
    edit_sig: np.ndarray,
    coarse_step_sec: int = 180
) -> list[CutInterval]:
    """Identify all cut intervals by finding step transitions in the offset curve."""
    samples = scan_offset_curve(edit_sig, orig_sig, step_sec=coarse_step_sec)
    cuts: list[CutInterval] = []

    # Check initial offset (intro cut)
    init_off, _ = match_offset_at(edit_sig, orig_sig, 5.0, 0.0, search_margin_sec=300.0)
    current_off = init_off if init_off is not None else 0.0

    for i in range(len(samples) - 1):
        t_cur, off_cur = samples[i]
        t_next, off_next = samples[i + 1]
        delta = off_next - off_cur
        if delta >= 3.0:  # Distinct cut of at least 3 seconds
            cut_t_edit = refine_boundary(edit_sig, orig_sig, t_cur, t_next, off_cur)
            orig_cut_start = cut_t_edit + off_cur
            orig_cut_end = cut_t_edit + off_next
            cuts.append(CutInterval(
                start_orig=orig_cut_start,
                end_orig=orig_cut_end,
                cut_at_edit=cut_t_edit,
                duration=delta
            ))

    return cuts


class TimelineReconciler:
    """Maps original timestamps through detected cut intervals."""

    def __init__(self, cuts: Sequence[CutInterval], intro_trim: float = 0.0):
        self.cuts = sorted(cuts, key=lambda c: c.start_orig)
        self.intro_trim = intro_trim

    def map_original_time(self, t_orig: float) -> tuple[float | None, str]:
        """Convert original seconds to edited seconds or identify cut."""
        if t_orig < self.intro_trim:
            return None, "CUT_INTRO"

        accumulated_cut = self.intro_trim
        for cut in self.cuts:
            if cut.start_orig <= t_orig < cut.end_orig:
                return None, f"DELETED ({format_seconds_to_timestr(cut.start_orig)} - {format_seconds_to_timestr(cut.end_orig)})"
            if t_orig >= cut.end_orig:
                accumulated_cut += cut.duration

        return (t_orig - accumulated_cut), "RETAINED"


def reconcile_markdown_file(
    input_path: str,
    output_path: str,
    reconciler: TimelineReconciler
) -> int:
    """Read markdown timestamps, shift valid timestamps, and prune deleted ones."""
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out_lines: list[str] = []
    retained_count = 0
    pattern = re.compile(r"^(\d{2}:\d{2}:\d{2}) - (.*)$")

    for line in lines:
        m = pattern.match(line.strip())
        if not m:
            out_lines.append(line)
            continue

        orig_str, rest = m.groups()
        orig_sec = float(parse_timestr_to_seconds(orig_str))
        new_sec, status = reconciler.map_original_time(orig_sec)

        if new_sec is not None:
            new_str = format_seconds_to_timestr(new_sec)
            out_lines.append(f"{new_str} - {rest}\n")
            retained_count += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)

    return retained_count


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct command-line arguments."""
    p = argparse.ArgumentParser(description="Reconcile timestamps for post-stream edited YouTube VODs.")
    p.add_argument("--orig-audio", required=True, help="Path to original unedited livestream audio.")
    p.add_argument("--video-url", required=True, help="YouTube video URL of the edited livestream.")
    p.add_argument("--timestamps", required=True, help="Path to input markdown timestamps file.")
    p.add_argument("-o", "--output", help="Path to output markdown file (defaults to overwrite input).")
    p.add_argument("--tmp-dir", default="/tmp", help="Directory for temporary raw PCM files.")
    return p


def main() -> None:
    """CLI execution entrypoint."""
    args = build_arg_parser().parse_args()
    out_path = args.output or args.timestamps

    orig_dur = get_audio_file_duration_seconds(args.orig_audio)
    online_dur = get_online_duration_seconds(args.video_url)

    if online_dur is None:
        sys.exit("Error: Could not retrieve online video duration from YouTube.")

    dur_diff = orig_dur - online_dur
    print(f"Original duration: {format_seconds_to_timestr(orig_dur)} ({orig_dur:.1f}s)")
    print(f"Online duration:   {format_seconds_to_timestr(online_dur)} ({online_dur:.1f}s)")
    print(f"Duration delta:    {dur_diff:.1f}s")

    if abs(dur_diff) < 3.0:
        print("Duration matches within tolerance. No reconciliation needed.")
        sys.exit(0)

    edit_audio_path = os.path.join(args.tmp_dir, "online_edited_audio.opus")
    orig_raw = os.path.join(args.tmp_dir, "reconcile_orig_1k.raw")
    edit_raw = os.path.join(args.tmp_dir, "reconcile_edit_1k.raw")

    try:
        print("Downloading edited audio from YouTube...")
        download_edited_audio(args.video_url, edit_audio_path)

        print("Downsampling both streams to 1000Hz PCM...")
        extract_1000hz_raw(args.orig_audio, orig_raw)
        extract_1000hz_raw(edit_audio_path, edit_raw)

        orig_sig = np.fromfile(orig_raw, dtype=PCM_TYPE).astype(np.float32)
        edit_sig = np.fromfile(edit_raw, dtype=PCM_TYPE).astype(np.float32)

        print("Detecting cut points via cross-correlation...")
        cuts = detect_cut_intervals(orig_sig, edit_sig)

        # Check intro offset
        init_off, _ = match_offset_at(edit_sig, orig_sig, 5.0, 0.0)
        intro_trim = init_off if init_off is not None and init_off > 1.0 else 0.0

        print(f"\nFound {len(cuts)} cut interval(s):")
        for i, c in enumerate(cuts, 1):
            print(f"  Cut {i}: {format_seconds_to_timestr(c.start_orig)} -> {format_seconds_to_timestr(c.end_orig)} (Duration: {c.duration:.1f}s, at edit {format_seconds_to_timestr(c.cut_at_edit)})")

        reconciler = TimelineReconciler(cuts, intro_trim=intro_trim)
        retained = reconcile_markdown_file(args.timestamps, out_path, reconciler)
        print(f"\nSuccessfully reconciled timestamps! Saved {retained} valid timestamps to {out_path}")

    finally:
        for f in (edit_audio_path, orig_raw, edit_raw):
            if os.path.exists(f):
                os.remove(f)


if __name__ == "__main__":
    main()
