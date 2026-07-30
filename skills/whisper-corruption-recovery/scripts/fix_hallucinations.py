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
import time
import threading
import argparse
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force stdout UTF-8 encoding if available
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WHISPER_CLI = str(Path.home() / "whisper.cpp/build/bin/whisper-cli")
if not Path(WHISPER_CLI).exists() and Path(WHISPER_CLI + ".exe").exists():
    WHISPER_CLI += ".exe"

MODEL_PATH  = str(Path.home() / "whisper.cpp/models/ggml-large-v3-turbo.bin")


class ProgressTracker:
    def __init__(self, level_name: str, total_tasks: int):
        self.level_name = level_name
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.start_time = time.time()
        self.lock = threading.Lock()

    def _fmt_time(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    def advance(self) -> tuple:
        with self.lock:
            self.completed_tasks += 1
            elapsed = time.time() - self.start_time
            pct = (self.completed_tasks / self.total_tasks) * 100.0 if self.total_tasks > 0 else 100.0
            
            if self.completed_tasks > 0 and self.completed_tasks < self.total_tasks:
                avg_per_task = elapsed / self.completed_tasks
                remaining_tasks = self.total_tasks - self.completed_tasks
                est_rem = avg_per_task * remaining_tasks
            else:
                est_rem = 0.0
                
            return self.completed_tasks, pct, self._fmt_time(elapsed), self._fmt_time(est_rem)

    def get_status_prefix(self) -> str:
        with self.lock:
            elapsed = time.time() - self.start_time
            pct = (self.completed_tasks / self.total_tasks) * 100.0 if self.total_tasks > 0 else 100.0
            if self.completed_tasks > 0 and self.completed_tasks < self.total_tasks:
                avg_per_task = elapsed / self.completed_tasks
                remaining_tasks = self.total_tasks - self.completed_tasks
                est_rem = avg_per_task * remaining_tasks
            else:
                est_rem = 0.0
            return f"[{self.level_name}] [Task {self.completed_tasks}/{self.total_tasks}] [{pct:5.1f}%] [{self._fmt_time(elapsed)}/{self._fmt_time(est_rem)}]"


def log_event(worker_id: str, stage: str, msg: str, tracker: ProgressTracker = None, advance: bool = False):
    ts = time.strftime("%H:%M:%S")
    if tracker:
        if advance:
            completed, pct, elapsed_str, rem_str = tracker.advance()
            prefix = f"[{ts}] [{worker_id}] [{tracker.level_name}] [Task {completed}/{tracker.total_tasks}] [{pct:5.1f}%] [{elapsed_str}/{rem_str}] [{stage}]"
        else:
            prefix = f"[{ts}] [{worker_id}] {tracker.get_status_prefix()} [{stage}]"
    else:
        prefix = f"[{ts}] [{worker_id}] [{stage}]"
    
    print(f"{prefix} {msg}", flush=True)


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
    Worker function for one BFS task. Evaluates text and logs instantly.
    task = (worker_num, start_ms, end_ms, audio_wav, model, threshold, min_duration_s, tracker)
    """
    worker_num, start_ms, end_ms, audio_wav, model, threshold, min_duration_s, tracker = task
    worker_id = f"W{worker_num}"
    duration_s = (end_ms - start_ms) / 1000.0
    slice_wav = None
    
    log_event(worker_id, "FFMPEG", f"Cutting audio {_fmt_ts(start_ms/1000.0)} -> {_fmt_ts(end_ms/1000.0)} ({duration_s:.1f}s)", tracker, advance=False)
    
    t0 = time.time()
    try:
        slice_wav = ffmpeg_cut(audio_wav, start_ms, end_ms)
        segs = run_whisper_on_slice(slice_wav, model, temperature=0.2)
        w_dur = time.time() - t0
        log_event(worker_id, "WHISPER", f"Processed slice in {w_dur:.1f}s -> {len(segs)} segments returned", tracker, advance=False)
    except subprocess.CalledProcessError as e:
        log_event(worker_id, "ERR", f"ffmpeg/whisper failed {_fmt_ts(start_ms/1000.0)} -> {_fmt_ts(end_ms/1000.0)}: {e}", tracker, advance=True)
        return worker_num, start_ms, end_ms, None, [], [(start_ms, end_ms)]
    finally:
        if slice_wav is not None:
            slice_wav.unlink(missing_ok=True)

    clean_sub = []
    uncertain_sub = []
    next_sub = []

    if not segs:
        item = {
            "text": "[?]",
            "start": start_ms / 1000.0,
            "duration": duration_s,
            "timestamp": _fmt_ts(start_ms / 1000.0),
            "uncertain": True,
        }
        uncertain_sub.append(item)
        log_event(worker_id, "EVAL", f"Range {_fmt_ts(start_ms/1000.0)} -> {_fmt_ts(end_ms/1000.0)} [?] UNCERTAIN (empty text)", tracker, advance=True)
        return worker_num, start_ms, end_ms, clean_sub, uncertain_sub, next_sub

    for seg in segs:
        text = seg.get("text", "").strip()
        if not text:
            continue
        offsets = seg.get("offsets", {})
        abs_from = offsets.get("from", 0) + start_ms
        # ponytail: clamp abs_to to end_ms — Whisper phantom offsets can report
        # timestamps far beyond the actual slice, which makes seg_dur_s huge and
        # prevents the base case from ever firing → infinite split loop.
        abs_to   = min(offsets.get("to", 0) + start_ms, end_ms)
        # Use the task's actual slice duration for the base-case check, NOT
        # Whisper's reported duration (which can be a phantom large number).
        seg_dur_s = duration_s

        if not is_hallucinated(text, threshold):
            item = {
                "text": text,
                "start": abs_from / 1000.0,
                "duration": max(0.0, (abs_to - abs_from) / 1000.0),
                "timestamp": _fmt_ts(abs_from / 1000.0),
            }
            clean_sub.append(item)
            log_event(worker_id, "EVAL", f"Range {_fmt_ts(abs_from/1000.0)} -> {_fmt_ts(abs_to/1000.0)} [✓ CLEAN] \"{text[:30]}\"", tracker, advance=False)
        elif seg_dur_s < min_duration_s:
            # Base case: slice is too small to split further → mark uncertain,
            # but keep Whisper's best-guess text with [?] prefix so humans can
            # verify by listening rather than losing the transcript entirely.
            item = {
                "text": f"[?] {text}",
                "start": abs_from / 1000.0,
                "duration": max(0.0, (abs_to - abs_from) / 1000.0),
                "timestamp": _fmt_ts(abs_from / 1000.0),
                "uncertain": True,
            }
            uncertain_sub.append(item)
            log_event(worker_id, "EVAL", f"Range {_fmt_ts(abs_from/1000.0)} -> {_fmt_ts(abs_to/1000.0)} [?] UNCERTAIN (slice {seg_dur_s:.1f}s < {min_duration_s:.1f}s) \"{text[:30]}\"", tracker, advance=False)
        else:
            mid = (abs_from + abs_to) // 2
            next_sub.append((abs_from, mid))
            next_sub.append((mid, abs_to))
            log_event(worker_id, "EVAL", f"Range {_fmt_ts(abs_from/1000.0)} -> {_fmt_ts(abs_to/1000.0)} [✗ HALLUCINATED] Loop detected: \"{text[:30]}\"", tracker, advance=False)
            log_event(worker_id, "SPLIT", f"Queueing 2 sub-tasks: {_fmt_ts(abs_from/1000.0)} -> {_fmt_ts(mid/1000.0)} & {_fmt_ts(mid/1000.0)} -> {_fmt_ts(abs_to/1000.0)}", tracker, advance=False)

    log_event(worker_id, "DONE", f"Task complete: {_fmt_ts(start_ms/1000.0)} -> {_fmt_ts(end_ms/1000.0)}", tracker, advance=True)
    return worker_num, start_ms, end_ms, clean_sub, uncertain_sub, next_sub


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
    """
    clean_items = []
    uncertain_items = []
    pending = list(ranges)  # list of (start_ms, end_ms)
    level = 0
    MAX_LEVEL = 20  # ponytail: hard cap — anything still bad at depth 20 is marked [?]; prevents infinite splitting on regions Whisper can never clean

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while pending:
            n = len(pending)
            avg_s = sum(e - s for s, e in pending) / n / 1000.0 if n else 0
            level_name = f"Level {level}"
            tracker = ProgressTracker(level_name, n)

            # Hard cap: force-mark all remaining ranges as uncertain
            if level >= MAX_LEVEL:
                log_event("MAIN", "WARN", f"[{level_name}] MAX_LEVEL={MAX_LEVEL} reached — marking {n} remaining task(s) as [?] UNCERTAIN (stuck loop)")
                for s, e in pending:
                    uncertain_items.append({
                        "text": "[?] (stuck loop)",
                        "start": s / 1000.0,
                        "duration": (e - s) / 1000.0,
                        "timestamp": _fmt_ts(s / 1000.0),
                        "uncertain": True,
                    })
                break

            log_event("MAIN", "START", f"[{level_name}] Launching {n} task(s) on {workers} worker(s)... (avg {avg_s:.1f}s each)")

            future_to_task = {
                executor.submit(
                    _try_whisper_task,
                    (i % workers + 1, s, e, audio_wav, model, threshold, min_duration_s, tracker)
                ): (s, e)
                for i, (s, e) in enumerate(pending)
            }

            next_pending = []
            level_clean = level_uncertain = level_recurse = 0

            for future in as_completed(future_to_task):
                try:
                    w_num, start_ms, end_ms, clean_sub, uncertain_sub, next_sub = future.result()
                    clean_items.extend(clean_sub)
                    uncertain_items.extend(uncertain_sub)
                    next_pending.extend(next_sub)

                    level_clean += len(clean_sub)
                    level_uncertain += len(uncertain_sub)
                    level_recurse += len(next_sub) // 2
                except Exception as e:
                    log_event("MAIN", "ERR", f"Error in worker task: {e}")

            log_event("MAIN", "SUMMARY", f"[{level_name} Complete] Tasks: {n}/{n} [100.0%] | Clean: {level_clean} | Split: {level_recurse} ({len(next_pending)} new tasks) | Uncertain: {level_uncertain}")
            pending = next_pending
            level += 1

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

    level_name = "Second-Chance"
    n_retry = len(retry_runs)
    tracker = ProgressTracker(level_name, n_retry)
    log_event("MAIN", "START", f"[{level_name}] Launching retry for {n_retry} uncertain region(s) > {min_duration_s:.1f}s on {workers} worker(s)...")

    # Build retry tasks
    retry_ranges = []
    for run in retry_runs:
        start_ms = int(run[0]["start"] * 1000)
        end_ms   = int((run[-1]["start"] + run[-1]["duration"]) * 1000)
        retry_ranges.append((start_ms, end_ms))

    tasks = [
        (i % workers + 1, s, e, audio_wav, model, threshold, min_duration_s, tracker)
        for i, (s, e) in enumerate(retry_ranges)
    ]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_try_whisper_task, tasks))

    for run, (w_num, start_ms, end_ms, clean_sub, uncertain_sub, next_sub) in zip(retry_runs, results):
        if clean_sub:
            recovered.extend(clean_sub)
            still_uncertain.extend(uncertain_sub)
        else:
            still_uncertain.extend(run)

    log_event("MAIN", "SUMMARY", f"[{level_name} Complete] Regions: {n_retry}/{n_retry} [100.0%] | Recovered: {len(recovered)} | Still Uncertain: {len(still_uncertain)}")
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
    log_event("MAIN", "SCAN", f"Found {num_corrupt} corrupt segments ({len(ranges)} merged ranges) out of {len(items)} total segments.")
    
    if not ranges:
        return items

    if not audio_wav.exists():
        log_event("MAIN", "WARN", f"audio_wav {audio_wav} not found — dropping corrupt segments")
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

    log_event("MAIN", "CHUNK", f"Split into {len(chunked_ranges)} recovery tasks (max 300s each).")
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
    log_event("MAIN", "SUMMARY", f"Completed recovery. Total: {len(result):,} | Recovered: {n_recovered:,} | Preserved Uncertain [?]: {n_uncertain:,} | Original Clean: {n_clean_orig:,}")

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

    log_event("MAIN", "INIT", f"Loading {json_path} ...")
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

    log_event("MAIN", "DONE", f"Wrote {len(fixed):,} items to {out_path}")


if __name__ == "__main__":
    main()
