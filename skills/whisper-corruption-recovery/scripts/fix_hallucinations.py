#!/usr/bin/env python3
"""
fix_hallucinations.py — Whisper in-segment phoneme loop detection and
divide-and-conquer slice recovery with multi-process worker support.

Usage:
    python3 fix_hallucinations.py <whisper_json> <audio_wav> [--model PATH]
        [--threshold 0.4] [--min-duration 1.0] [--workers 2] [-o output.json]
"""
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

WHISPER_CLI = str(Path.home() / "whisper.cpp/build/bin/whisper-cli")
if not Path(WHISPER_CLI).exists() and Path(WHISPER_CLI + ".exe").exists():
    WHISPER_CLI += ".exe"

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
            "-tp", str(temperature),
            "-f", str(slice_wav),
            "-ojf",
            "-of", out_base,
        ],
        check=True,
        capture_output=True,
    )
    json_path = slice_wav.with_suffix(".json")
    if not json_path.exists():
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


def _try_whisper_task(task):
    """
    Worker function for one BFS task.
    task = (start_ms, end_ms, audio_wav, model, threshold, min_duration_s)
    Returns (start_ms, end_ms, segs_or_none)
    segs_or_none: list of raw whisper seg dicts, or None on ffmpeg/whisper failure.
    Offsets in segs are relative to slice start (whisper convention).
    """
    start_ms, end_ms, audio_wav, model, threshold, min_duration_s = task
    slice_wav = None
    try:
        slice_wav = ffmpeg_cut(audio_wav, start_ms, end_ms)
        segs = run_whisper_on_slice(slice_wav, model, temperature=0.2)
        return start_ms, end_ms, segs
    except subprocess.CalledProcessError as e:
        print(f"  [err] ffmpeg/whisper failed {start_ms}-{end_ms}ms: {e}", file=sys.stderr)
        return start_ms, end_ms, None
    finally:
        if slice_wav is not None:
            slice_wav.unlink(missing_ok=True)


def _bfs_recover(
    ranges: list,
    audio_wav: Path,
    model: str = MODEL_PATH,
    threshold: float = 0.4,
    min_duration_s: float = 1.0,
    workers: int = 2,
) -> tuple:
    """
    BFS parallel divide-and-conquer recovery.

    Args:
        ranges: list of (start_ms, end_ms) corrupt time ranges
        audio_wav: path to original audio file
        model: whisper GGML model path
        threshold: hallucination n-gram ratio threshold
        min_duration_s: base case — slices shorter than this get [?] if still bad
        workers: number of concurrent whisper-cli processes

    Returns:
        (clean_items, uncertain_items)
        clean_items   — list of {"text", "start", "duration", "timestamp"}
        uncertain_items — list of {"text": "[?]", "start", "duration", "timestamp", "uncertain": True}
    """
    clean_items = []
    uncertain_items = []
    pending = list(ranges)  # list of (start_ms, end_ms)
    level = 0

    bar = "━" * 40
    print(bar)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while pending:
            n = len(pending)
            avg_s = sum(e - s for s, e in pending) / n / 1000.0 if n else 0
            print(f"\n[Level {level}]  {n} task(s)  (avg {avg_s:.1f}s each)")

            tasks = [(s, e, audio_wav, model, threshold, min_duration_s) for s, e in pending]
            results = list(executor.map(_try_whisper_task, tasks))

            next_pending = []
            level_clean = level_uncertain = level_recurse = 0

            for (start_ms, end_ms), (_, _, segs) in zip(pending, results):
                duration_s = (end_ms - start_ms) / 1000.0

                if segs is None:
                    # ffmpeg/whisper hard failure — mark uncertain
                    item = {
                        "text": "[?]",
                        "start": start_ms / 1000.0,
                        "duration": duration_s,
                        "timestamp": _fmt_ts(start_ms / 1000.0),
                        "uncertain": True,
                    }
                    uncertain_items.append(item)
                    level_uncertain += 1
                    print(f"  [?]  {_fmt_ts(start_ms/1000.0)}→{_fmt_ts(end_ms/1000.0)}"
                          f"  {duration_s:.1f}s  whisper failed")
                    continue

                for seg in segs:
                    text = seg.get("text", "").strip()
                    if not text:
                        continue
                    offsets = seg.get("offsets", {})
                    abs_from = offsets.get("from", 0) + start_ms
                    abs_to   = offsets.get("to",   0) + start_ms
                    seg_dur_s = (abs_to - abs_from) / 1000.0

                    if not is_hallucinated(text, threshold):
                        # ✓ clean
                        item = {
                            "text": text,
                            "start": abs_from / 1000.0,
                            "duration": max(0.0, seg_dur_s),
                            "timestamp": _fmt_ts(abs_from / 1000.0),
                        }
                        clean_items.append(item)
                        level_clean += 1
                        print(f"  ✓  {_fmt_ts(abs_from/1000.0)}→{_fmt_ts(abs_to/1000.0)}"
                              f"  {seg_dur_s:.1f}s  \"{text[:30]}\"")
                    elif seg_dur_s < min_duration_s:
                        # [?] base case — too small to split further
                        item = {
                            "text": "[?]",
                            "start": abs_from / 1000.0,
                            "duration": max(0.0, seg_dur_s),
                            "timestamp": _fmt_ts(abs_from / 1000.0),
                            "uncertain": True,
                        }
                        uncertain_items.append(item)
                        level_uncertain += 1
                        print(f"  [?]  {_fmt_ts(abs_from/1000.0)}→{_fmt_ts(abs_to/1000.0)}"
                              f"  {seg_dur_s:.1f}s  uncertain (base case)")
                    else:
                        # ✗ still bad and splittable → add both halves to next level
                        mid = (abs_from + abs_to) // 2
                        next_pending.append((abs_from, mid))
                        next_pending.append((mid, abs_to))
                        level_recurse += 1
                        print(f"  ✗  {_fmt_ts(abs_from/1000.0)}→{_fmt_ts(abs_to/1000.0)}"
                              f"  {seg_dur_s:.1f}s  → split")

            print(f"  → Level {level}: {level_clean} clean, "
                  f"{level_recurse} recurse ({len(next_pending)} new tasks), "
                  f"{level_uncertain} uncertain")
            pending = next_pending
            level += 1

    print()
    return clean_items, uncertain_items


def _second_chance_pass(
    uncertain_items: list,
    audio_wav: Path,
    model: str = MODEL_PATH,
    threshold: float = 0.4,
    min_duration_s: float = 1.0,
    workers: int = 2,
) -> tuple:
    """
    Merge consecutive [?] runs spanning > 1s and retry recovery in parallel.

    Returns (recovered_items, still_uncertain_items).
    """
    if not uncertain_items:
        return [], []

    uncertain_items = sorted(uncertain_items, key=lambda x: x["start"])

    # Group consecutive uncertain items into runs
    runs = []
    run = [uncertain_items[0]]
    for item in uncertain_items[1:]:
        # consecutive = next item starts where this one ends (within 0.1s gap tolerance)
        prev_end = run[-1]["start"] + run[-1]["duration"]
        if item["start"] - prev_end < 0.1:
            run.append(item)
        else:
            runs.append(run)
            run = [item]
    runs.append(run)

    # Split into retry-eligible (span > 1s) and keep-as-is (span <= 1s)
    retry_runs = []
    keep_runs = []
    for run in runs:
        span = sum(i["duration"] for i in run)
        if span > min_duration_s:
            retry_runs.append(run)
        else:
            keep_runs.append(run)

    still_uncertain = [item for run in keep_runs for item in run]
    recovered = []

    if not retry_runs:
        return recovered, still_uncertain

    print(f"\n[Second-chance]  {len(retry_runs)} uncertain region(s) > {min_duration_s}s"
          f"  |  {workers} workers")

    # Build retry tasks
    retry_ranges = []
    for run in retry_runs:
        start_ms = int(run[0]["start"] * 1000)
        end_ms   = int((run[-1]["start"] + run[-1]["duration"]) * 1000)
        retry_ranges.append((start_ms, end_ms))

    tasks = [(s, e, audio_wav, model, threshold, min_duration_s) for s, e in retry_ranges]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_try_whisper_task, tasks))

    for run, (start_ms, end_ms), (_, _, segs) in zip(retry_runs, retry_ranges, results):
        span_s = (end_ms - start_ms) / 1000.0
        if segs is None:
            print(f"  [?]  {_fmt_ts(start_ms/1000.0)}→{_fmt_ts(end_ms/1000.0)}"
                  f"  {span_s:.1f}s  → whisper failed, keep uncertain")
            still_uncertain.extend(run)
            continue

        run_recovered = []
        run_uncertain = []
        for seg in segs:
            text = seg.get("text", "").strip()
            if not text:
                continue
            offsets = seg.get("offsets", {})
            abs_from = offsets.get("from", 0) + start_ms
            abs_to   = offsets.get("to",   0) + start_ms
            seg_dur  = (abs_to - abs_from) / 1000.0
            if is_hallucinated(text, threshold):
                run_uncertain.append({
                    "text": "[?]",
                    "start": abs_from / 1000.0,
                    "duration": max(0.0, seg_dur),
                    "timestamp": _fmt_ts(abs_from / 1000.0),
                    "uncertain": True,
                })
            else:
                run_recovered.append({
                    "text": text,
                    "start": abs_from / 1000.0,
                    "duration": max(0.0, seg_dur),
                    "timestamp": _fmt_ts(abs_from / 1000.0),
                })

        if run_recovered:
            print(f"  ✓  {_fmt_ts(start_ms/1000.0)}→{_fmt_ts(end_ms/1000.0)}"
                  f"  {span_s:.1f}s  → recovered: {len(run_recovered)} item(s)")
            recovered.extend(run_recovered)
            still_uncertain.extend(run_uncertain)
        else:
            print(f"  [?]  {_fmt_ts(start_ms/1000.0)}→{_fmt_ts(end_ms/1000.0)}"
                  f"  {span_s:.1f}s  → still uncertain")
            still_uncertain.extend(run)

    return recovered, still_uncertain



def detect_and_recover(
    items: list,
    audio_wav: Path,
    model: str = MODEL_PATH,
    threshold: float = 0.4,
    min_duration_s: float = 1.0,
    workers: int = 2,
    max_consec_repeat: int = 4,
) -> list:
    """
    Scan items for in-segment phoneme loops and cross-segment repetition loops.
    Merges contiguous corrupt items into 5-minute audio slice tasks, running D&C
    recovery across N workers concurrently.
    Returns merged, timestamp-sorted list.
    """
    is_corrupt = [False] * len(items)

    # 1. In-segment phoneme loop detection
    for i, item in enumerate(items):
        if is_hallucinated(item.get("text", ""), threshold):
            is_corrupt[i] = True

    # 2. Cross-segment consecutive identical text loop detection
    i = 0
    while i < len(items):
        j = i + 1
        t = items[i].get("text", "").strip()
        while j < len(items) and items[j].get("text", "").strip() == t:
            j += 1
        count = j - i
        if count >= max_consec_repeat and len(t) > 1:
            for k in range(i, j):
                is_corrupt[k] = True
        i = j

    # Group contiguous corrupt items into merged time ranges [start_ms, end_ms]
    ranges = []
    curr_start = None
    curr_end = None

    for i, item in enumerate(items):
        if is_corrupt[i]:
            start_ms = int(item["start"] * 1000)
            end_ms = int((item["start"] + item.get("duration", 0)) * 1000)
            if curr_start is None:
                curr_start = start_ms
                curr_end = end_ms
            else:
                curr_end = max(curr_end, end_ms)
        else:
            if curr_start is not None:
                ranges.append((curr_start, curr_end))
                curr_start = None
                curr_end = None

    if curr_start is not None:
        ranges.append((curr_start, curr_end))

    clean_items = [item for i, item in enumerate(items) if not is_corrupt[i]]
    num_corrupt = sum(is_corrupt)
    print(f"[fix] Found {num_corrupt} corrupt segments ({len(ranges)} merged ranges) out of {len(items)} total segments.")
    
    if not ranges:
        return items

    if not audio_wav.exists():
        print(f"[fix] WARNING: audio_wav {audio_wav} not found — dropping corrupt segments", file=sys.stderr)
        return clean_items

    # Split large ranges (> 300s) into 300s sub-chunks
    chunked_ranges = []
    MAX_CHUNK_MS = 300 * 1000  # 5 minutes
    for st, en in ranges:
        curr = st
        while curr < en:
            nxt = min(curr + MAX_CHUNK_MS, en)
            chunked_ranges.append((curr, nxt))
            curr = nxt

    print(f"[fix] Split into {len(chunked_ranges)} recovery tasks (up to 5m each).")
    print(f"[fix] Running BFS parallel recovery using {workers} worker(s)...")
    clean_recovered, uncertain_items = _bfs_recover(
        chunked_ranges, audio_wav, model, threshold, min_duration_s, workers
    )
    sc_recovered, sc_uncertain = _second_chance_pass(
        uncertain_items, audio_wav, model, threshold, min_duration_s, workers
    )
    recovered_items = clean_recovered + sc_recovered + sc_uncertain

    result = clean_items + recovered_items
    result.sort(key=lambda x: x["start"])

    # Final post-recovery pass: strip residual consecutive repetitions (>= 3)
    final_dedup = []
    i = 0
    fillers = {"โอเค", "เออ", "อืม", "อื้อ", "เอ่อ", "อ้าว"}
    while i < len(result):
        j = i + 1
        t = result[i].get("text", "").strip()
        while j < len(result) and result[j].get("text", "").strip() == t:
            j += 1
        count = j - i
        if count >= 3 and len(t) > 2 and t not in fillers:
            final_dedup.append(result[i])
        else:
            final_dedup.extend(result[i:j])
        i = j

    result = final_dedup

    n_uncertain = sum(1 for i in result if i.get("uncertain"))
    n_clean_orig = len(items) - num_corrupt
    n_recovered  = len(result) - n_clean_orig - n_uncertain
    bar = "━" * 40
    print(f"\n{bar}")
    print(f" Done")
    print(f" Total output  : {len(result):,} items")
    print(f" Recovered     : {n_recovered:,}  (D&C + second-chance)")
    print(f" Uncertain [?] : {n_uncertain:,}  (preserved, sub-second)")
    print(f" Original clean: {n_clean_orig:,}")
    print(bar)

    return result



# ---------------------------------------------------------------------------
# Task 4: Standalone CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Detect and fix Whisper in-segment phoneme loop hallucinations with multi-worker support."
    )
    ap.add_argument("whisper_json", help="Path to whisper-cli JSON output (audio.wav.json)")
    ap.add_argument("audio_wav",    help="Path to original WAV audio file")
    ap.add_argument("--model",        default=MODEL_PATH,
                    help=f"Path to GGML model (default: {MODEL_PATH})")
    ap.add_argument("--threshold",    type=float, default=0.4,
                    help="N-gram repetition ratio threshold (default: 0.4)")
    ap.add_argument("--min-duration", type=float, default=1.0,
                    help="Min slice duration in seconds before discarding (default: 1.0)")
    ap.add_argument("-w", "--workers", type=int, default=2,
                    help="Number of parallel whisper-cli workers (default: 2)")
    ap.add_argument("-o", "--output", default=None,
                    help="Output JSON path (default: overwrite input)")
    args = ap.parse_args()

    json_path  = Path(args.whisper_json)
    audio_path = Path(args.audio_wav)
    out_path   = Path(args.output) if args.output else json_path

    print(f"[fix] Loading {json_path} ...", file=sys.stderr)
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

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

    fixed = detect_and_recover(raw, audio_path, args.model, args.threshold, args.min_duration, workers=args.workers)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)

    print(f"[fix] Done. Wrote {len(fixed)} items to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
