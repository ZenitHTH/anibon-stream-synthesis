#!/usr/bin/env python3
"""
fix_hallucinations.py — Whisper in-segment phoneme loop detection and
divide-and-conquer slice recovery.

Usage:
    python3 fix_hallucinations.py <whisper_json> <audio_wav> [--model PATH]
        [--threshold 0.4] [--min-duration 1.0] [-o output.json]
"""
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path

WHISPER_CLI = str(Path.home() / "whisper.cpp/build/bin/whisper-cli")
MODEL_PATH  = str(Path.home() / "whisper.cpp/models/ggml-large-v3-turbo.bin")


# ---------------------------------------------------------------------------
# Task 1: Detection
# ---------------------------------------------------------------------------

def is_hallucinated(text: str, threshold: float = 0.4) -> bool:
    """True if a repeated n-gram (n=2..4, count>=2) covers > threshold of text length."""
    if len(text) < 8:
        return False
    for n in range(2, 5):
        ngrams = [text[i:i+n] for i in range(len(text) - n + 1)]
        for gram in set(ngrams):
            count = text.count(gram)
            if count >= 2 and count * n / len(text) > threshold:
                return True
    return False


# ---------------------------------------------------------------------------
# Task 2: ffmpeg slice + whisper re-run
# ---------------------------------------------------------------------------

def ffmpeg_cut(audio_wav: Path, start_ms: int, end_ms: int) -> Path:
    """Cut [start_ms, end_ms] from audio_wav into a temp mono 16kHz WAV file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = Path(tmp.name)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start_ms / 1000.0),
            "-to", str(end_ms / 1000.0),
            "-i", str(audio_wav),
            "-ar", "16000", "-ac", "1",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def run_whisper_on_slice(slice_wav: Path, model: str, temperature: float) -> list:
    """
    Run whisper-cli on slice_wav at given temperature.
    Returns list of raw transcription dicts from whisper-cli JSON.
    Offsets in the returned dicts are relative to the slice start.
    """
    out_base = str(slice_wav.with_suffix(""))
    subprocess.run(
        [
            WHISPER_CLI,
            "-m", model,
            "-l", "th",
            "--temperature", str(temperature),
            "-f", str(slice_wav),
            "-ojf", out_base,
        ],
        check=True,
        capture_output=True,
    )
    json_path = Path(str(slice_wav) + ".json")
    if not json_path.exists():
        return []
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    json_path.unlink(missing_ok=True)
    return data.get("transcription", [])


# ---------------------------------------------------------------------------
# Task 3: D&C recovery
# ---------------------------------------------------------------------------

def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def recover_segment(
    audio_wav: Path,
    start_ms: int,
    end_ms: int,
    model: str,
    threshold: float,
    min_duration_s: float,
    depth: int = 0,
    max_depth: int = 4,
) -> list:
    """
    Divide-and-conquer: recursively halve [start_ms, end_ms] until clean or
    < min_duration_s or depth > max_depth.
    Returns list of pipeline items {"text", "start", "duration", "timestamp"}.
    Offsets returned are absolute (relative to original audio_wav start = 0).
    """
    indent = "  " * depth
    duration_s = (end_ms - start_ms) / 1000.0

    if duration_s < min_duration_s:
        print(f"[fix]{indent} base-case: slice {start_ms}-{end_ms}ms ({duration_s:.1f}s) < {min_duration_s}s — discard", file=sys.stderr, flush=True)
        return []

    if depth >= max_depth:
        print(f"[fix]{indent} max-depth {max_depth} reached at {start_ms}-{end_ms}ms ({duration_s:.1f}s) — discard (non-speech)", file=sys.stderr, flush=True)
        return []

    print(f"[fix]{indent} depth={depth} cutting slice {start_ms}-{end_ms}ms ({duration_s:.1f}s)...", file=sys.stderr, flush=True)
    slice_wav = ffmpeg_cut(audio_wav, start_ms, end_ms)
    try:
        print(f"[fix]{indent} running whisper-cli on {duration_s:.1f}s slice...", file=sys.stderr, flush=True)
        raw_segs = run_whisper_on_slice(slice_wav, model, temperature=0.2)
    except subprocess.CalledProcessError as e:
        print(f"[fix]{indent} whisper-cli FAILED on {start_ms}-{end_ms}ms: {e}", file=sys.stderr, flush=True)
        return []
    finally:
        slice_wav.unlink(missing_ok=True)

    print(f"[fix]{indent} whisper returned {len(raw_segs)} token-segs from {duration_s:.1f}s slice", file=sys.stderr, flush=True)

    clean_items = []
    for seg in raw_segs:
        text = seg.get("text", "").strip()
        if not text:
            continue
        offsets = seg.get("offsets", {})
        # Offsets from whisper are relative to the slice; add start_ms to make absolute
        abs_from = offsets.get("from", 0) + start_ms
        abs_to   = offsets.get("to",   0) + start_ms

        if is_hallucinated(text, threshold):
            print(f"[fix]{indent} still hallucinated: '{text[:40]}' → recurse (depth {depth+1})", file=sys.stderr, flush=True)
            mid = (abs_from + abs_to) // 2
            clean_items.extend(
                recover_segment(audio_wav, abs_from, mid, model, threshold, min_duration_s, depth + 1, max_depth)
            )
            clean_items.extend(
                recover_segment(audio_wav, mid, abs_to, model, threshold, min_duration_s, depth + 1, max_depth)
            )
        else:
            start_s = abs_from / 1000.0
            print(f"[fix]{indent} clean: '{text[:50]}'", file=sys.stderr, flush=True)
            clean_items.append({
                "text": text,
                "start": start_s,
                "duration": max(0.0, (abs_to - abs_from) / 1000.0),
                "timestamp": _fmt_ts(start_s),
            })

    return clean_items


def detect_and_recover(
    items: list,
    audio_wav: Path,
    model: str = MODEL_PATH,
    threshold: float = 0.4,
    min_duration_s: float = 1.0,
    max_depth: int = 4,
) -> list:
    """
    Scan items for in-segment phoneme loops. For each corrupt item, run D&C
    recovery on the audio slice and substitute recovered items.
    Returns merged, timestamp-sorted list.
    """
    result = []
    corrupt_count = 0
    total = len(items)

    for idx, item in enumerate(items):
        text = item.get("text", "")
        if not is_hallucinated(text, threshold):
            if idx % 500 == 0:
                print(f"[fix] progress: {idx+1}/{total} segments scanned, {corrupt_count} corrupt so far", file=sys.stderr, flush=True)
            result.append(item)
            continue

        corrupt_count += 1
        start_ms = int(item["start"] * 1000)
        end_ms   = int((item["start"] + item.get("duration", 0)) * 1000)
        duration_s = (end_ms - start_ms) / 1000.0
        print(
            f"\n[fix] [{idx+1}/{total}] Corrupt segment at {item['timestamp']} ({duration_s:.1f}s): "
            f"recovering [{start_ms}ms–{end_ms}ms]",
            file=sys.stderr, flush=True,
        )
        print(f"[fix]   text preview: '{text[:60]}'", file=sys.stderr, flush=True)

        if not audio_wav.exists():
            print(
                f"[fix] WARNING: audio_wav {audio_wav} not found — dropping segment",
                file=sys.stderr, flush=True,
            )
            continue

        recovered = recover_segment(audio_wav, start_ms, end_ms, model, threshold, min_duration_s, depth=0, max_depth=max_depth)
        print(f"[fix]   → recovered {len(recovered)} clean items from {item['timestamp']}", file=sys.stderr, flush=True)
        result.extend(recovered)

    result.sort(key=lambda x: x["start"])
    if corrupt_count:
        print(f"[fix] Replaced {corrupt_count} hallucinated segments.", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Task 4: Standalone CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Detect and fix Whisper in-segment phoneme loop hallucinations."
    )
    ap.add_argument("whisper_json", help="Path to whisper-cli JSON output (audio.wav.json)")
    ap.add_argument("audio_wav",    help="Path to original WAV audio file")
    ap.add_argument("--model",        default=MODEL_PATH,
                    help=f"Path to GGML model (default: {MODEL_PATH})")
    ap.add_argument("--threshold",    type=float, default=0.4,
                    help="N-gram repetition ratio threshold (default: 0.4)")
    ap.add_argument("--min-duration", type=float, default=1.0,
                    help="Min slice duration in seconds before discarding (default: 1.0)")
    ap.add_argument("-o", "--output", default=None,
                    help="Output JSON path (default: overwrite input)")
    args = ap.parse_args()

    json_path  = Path(args.whisper_json)
    audio_path = Path(args.audio_wav)
    out_path   = Path(args.output) if args.output else json_path

    print(f"[fix] Loading {json_path} ...", file=sys.stderr)
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    # Parse whisper-cli transcription format → pipeline items
    raw = []
    for seg in data.get("transcription", []):
        offsets  = seg.get("offsets", {})
        start_s  = offsets.get("from", 0) / 1000.0
        end_s    = offsets.get("to",   0) / 1000.0
        text     = seg.get("text", "").strip()
        if not text or len(text) == 1:
            continue
        raw.append({
            "text":      text,
            "start":     start_s,
            "duration":  max(0.0, end_s - start_s),
            "timestamp": _fmt_ts(start_s),
        })

    fixed = detect_and_recover(raw, audio_path, args.model, args.threshold, args.min_duration)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)

    print(f"[fix] Done. Wrote {len(fixed)} items to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
