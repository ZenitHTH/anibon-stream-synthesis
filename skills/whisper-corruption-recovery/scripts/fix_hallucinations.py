#!/usr/bin/env python3
"""
fix_hallucinations.py — Whisper in-segment phoneme loop detection and
divide-and-conquer slice recovery with multi-process worker support.

Usage:
    python3 fix_hallucinations.py <whisper_json> <audio_wav> [--model PATH]
        [--threshold 0.4] [--min-duration 1.0] [--workers 2] [-o output.json]
"""
from __future__ import annotations

import sys
import os
import json
import time
import shutil
import threading
import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force stdout UTF-8 encoding if available
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_LIB_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from common.time import fmt_hhmmss
from process.text import is_hallucinated
from process.audio_separator_engine import separate_via_audiocpp_api

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


def _format_log_prefix(worker_id: str, stage: str, tracker_info: str) -> str:
    ts = time.strftime("%H:%M:%S")
    if tracker_info:
        return f"[{ts}] [{worker_id}] {tracker_info} [{stage}]"
    return f"[{ts}] [{worker_id}] [{stage}]"


def log_event(worker_id: str, stage: str, msg: str, tracker: Optional[ProgressTracker] = None) -> None:
    tracker_info = tracker.get_status_prefix() if tracker else ""
    prefix = _format_log_prefix(worker_id, stage, tracker_info)
    print(f"{prefix} {msg}", flush=True)


def log_event_and_advance(worker_id: str, stage: str, msg: str, tracker: Optional[ProgressTracker] = None) -> None:
    if not tracker:
        log_event(worker_id, stage, msg)
        return
    completed, pct, elapsed_str, rem_str = tracker.advance()
    info = f"[{tracker.level_name}] [Task {completed}/{tracker.total_tasks}] [{pct:5.1f}%] [{elapsed_str}/{rem_str}]"
    prefix = _format_log_prefix(worker_id, stage, info)
    print(f"{prefix} {msg}", flush=True)


# ---------------------------------------------------------------------------
# Task 1: Detection (delegated to process.text)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 2: ffmpeg slice + whisper re-run
# ---------------------------------------------------------------------------

def ffmpeg_cut(audio_wav: Path, start_ms: int, end_ms: int) -> Path:
    """Cut [start_ms, end_ms] from audio_wav into a temp 44.1kHz stereo WAV file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = Path(tmp.name)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_ms / 1000.0),
        "-to", str(end_ms / 1000.0),
        "-i", str(audio_wav),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out
    except Exception:
        out.unlink(missing_ok=True)
        raise


def _parse_server_segments(data: dict) -> list:
    segments = []
    for seg in data.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        start_ms = int(round(float(seg.get("start", 0)) * 1000))
        end_ms = int(round(float(seg.get("end", 0)) * 1000))
        segments.append({"text": text, "offsets": {"from": start_ms, "to": end_ms}})
    return segments


@dataclass
class WhisperExecConfig:
    model: str = MODEL_PATH
    temperature: float = 0.2
    device: int = 0
    threads: int = 4
    endpoint: Optional[str] = None


def _apply_whisper_kwargs(cfg: WhisperExecConfig, kwargs: dict) -> None:
    for k, v in kwargs.items():
        if v is not None and hasattr(cfg, k):
            setattr(cfg, k, v)


def _normalize_whisper_config(
    config: Optional[WhisperExecConfig | str] = None,
    *args,
    **kwargs,
) -> WhisperExecConfig:
    if isinstance(config, WhisperExecConfig):
        return config
    cfg = WhisperExecConfig()
    if isinstance(config, str):
        cfg.model = config
    if len(args) > 0 and isinstance(args[0], (int, float)):
        cfg.temperature = float(args[0])
    _apply_whisper_kwargs(cfg, kwargs)
    return cfg


def _query_whisper_server(slice_wav: Path, cfg: WhisperExecConfig) -> list:
    cmd = [
        "curl", "-s", str(cfg.endpoint),
        "-H", "Content-Type: multipart/form-data",
        "-F", f"file=@{slice_wav}",
        "-F", "language=th",
        "-F", f"temperature={cfg.temperature}",
        "-F", "response_format=verbose_json",
    ]
    try:
        res = subprocess.check_output(cmd, timeout=120)
        data = json.loads(res.decode("utf-8", errors="replace"))
        return _parse_server_segments(data)
    except Exception:
        return []


def _load_and_cleanup_json(slice_wav: Path) -> list:
    json_path = slice_wav.with_suffix(".json")
    if not json_path.exists():
        json_path = Path(str(slice_wav) + ".json")
    if not json_path.exists():
        return []
    try:
        with open(json_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return data.get("transcription", [])
    except Exception:
        return []
    finally:
        json_path.unlink(missing_ok=True)


def _run_whisper_cli(slice_wav: Path, cfg: WhisperExecConfig) -> list:
    out_base = str(slice_wav.with_suffix(""))
    cmd = [
        WHISPER_CLI, "-m", cfg.model, "-l", "th",
        "-dev", str(cfg.device), "-t", str(cfg.threads),
        "-tp", str(cfg.temperature), "-f", str(slice_wav),
        "-ojf", "-of", out_base,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return _load_and_cleanup_json(slice_wav)


def run_whisper_on_slice(
    slice_wav: Path,
    config: Optional[WhisperExecConfig | str] = None,
    *args,
    **kwargs,
) -> list:
    """Run whisper-cli or remote whisper-server on slice_wav at given configuration."""
    cfg = _normalize_whisper_config(config, *args, **kwargs)
    if cfg.endpoint:
        return _query_whisper_server(slice_wav, cfg)
    return _run_whisper_cli(slice_wav, cfg)


# ---------------------------------------------------------------------------
# Task 3: D&C recovery
# ---------------------------------------------------------------------------

def _fmt_ts(seconds: float) -> str:
    return fmt_hhmmss(seconds)


@dataclass
class WhisperTask:
    worker_num: int
    start_ms: int
    end_ms: int
    audio_wav: Path
    model: str
    threshold: float
    min_duration_s: float
    tracker: Optional[ProgressTracker] = None
    device: int = 0
    threads: int = 4
    endpoint: Optional[str] = None
    audiocpp_url: Optional[str] = None

    @property
    def worker_id(self) -> str:
        return f"W{self.worker_num}:SERVER" if self.endpoint else f"W{self.worker_num}:GPU{self.device}"

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0

    @property
    def whisper_cfg(self) -> WhisperExecConfig:
        return WhisperExecConfig(
            model=self.model,
            temperature=0.2,
            device=self.device,
            threads=self.threads,
            endpoint=self.endpoint,
        )


def _parse_task(task: tuple | WhisperTask) -> WhisperTask:
    if isinstance(task, WhisperTask):
        return task
    w_num, start_ms, end_ms, audio_wav, model, threshold, min_dur = task[:7]
    tracker = task[7] if len(task) > 7 else None
    dev = task[8] if len(task) > 8 else 0
    threads = task[9] if len(task) > 9 else 4
    endpoint = task[10] if len(task) > 10 else None
    audiocpp_url = task[11] if len(task) > 11 else None
    return WhisperTask(
        worker_num=w_num, start_ms=start_ms, end_ms=end_ms,
        audio_wav=audio_wav, model=model, threshold=threshold,
        min_duration_s=min_dur, tracker=tracker, device=dev,
        threads=threads, endpoint=endpoint, audiocpp_url=audiocpp_url,
    )


def _format_segment_item(seg: dict, start_ms: int, end_ms: int) -> dict:
    text = seg.get("text", "").strip()
    offsets = seg.get("offsets", {})
    abs_from = offsets.get("from", 0) + start_ms
    abs_to = min(offsets.get("to", 0) + start_ms, end_ms)
    return {
        "text": text,
        "start": abs_from / 1000.0,
        "duration": max(0.0, (abs_to - abs_from) / 1000.0),
        "timestamp": _fmt_ts(abs_from / 1000.0),
    }


def _build_uncertain_item(start_ms: int, end_ms: int, text: str = "[?]") -> dict:
    dur_s = (end_ms - start_ms) / 1000.0
    return {
        "text": text,
        "start": start_ms / 1000.0,
        "duration": dur_s,
        "timestamp": _fmt_ts(start_ms / 1000.0),
        "uncertain": True,
    }


def _execute_slice_whisper(cfg: WhisperTask) -> tuple[Optional[Path], Optional[list]]:
    log_event(cfg.worker_id, "FFMPEG", f"Cutting audio {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)} ({cfg.duration_s:.1f}s)", cfg.tracker)
    t0 = time.time()
    try:
        slice_wav = ffmpeg_cut(cfg.audio_wav, cfg.start_ms, cfg.end_ms)
        segs = run_whisper_on_slice(slice_wav, cfg.whisper_cfg)
        w_dur = time.time() - t0
        target = "server" if cfg.endpoint else f"GPU {cfg.device}"
        log_event(cfg.worker_id, "WHISPER", f"Processed slice on {target} in {w_dur:.1f}s -> {len(segs)} segments returned", cfg.tracker)
        return slice_wav, segs
    except subprocess.CalledProcessError as e:
        log_event_and_advance(cfg.worker_id, "ERR", f"ffmpeg/whisper failed {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)}: {e}", cfg.tracker)
        return None, None


def _eval_single_segment(seg: dict, cfg: WhisperTask) -> tuple[Optional[dict], Optional[dict], bool]:
    text = seg.get("text", "").strip()
    item = _format_segment_item(seg, cfg.start_ms, cfg.end_ms)
    abs_from_s, abs_to_s = item["start"], item["start"] + item["duration"]
    if not is_hallucinated(text, cfg.threshold):
        log_event(cfg.worker_id, "EVAL", f"Range {_fmt_ts(abs_from_s)} -> {_fmt_ts(abs_to_s)} [✓ CLEAN] \"{text[:30]}\"", cfg.tracker)
        return item, None, False
    if cfg.duration_s < cfg.min_duration_s:
        item["text"] = f"[?] {text}"
        item["uncertain"] = True
        log_event(cfg.worker_id, "EVAL", f"Range {_fmt_ts(abs_from_s)} -> {_fmt_ts(abs_to_s)} [?] UNCERTAIN (slice {cfg.duration_s:.1f}s < {cfg.min_duration_s:.1f}s) \"{text[:30]}\"", cfg.tracker)
        return None, item, False
    log_event(cfg.worker_id, "EVAL", f"Range {_fmt_ts(abs_from_s)} -> {_fmt_ts(abs_to_s)} [✗ HALLUCINATED] Loop detected: \"{text[:30]}\"", cfg.tracker)
    return None, None, True


def _classify_segments(segs: list, cfg: WhisperTask) -> tuple[list, list, bool]:
    clean_sub, uncertain_sub = [], []
    has_hallucination = False
    for seg in segs:
        if not seg.get("text", "").strip():
            continue
        c_item, u_item, is_loop = _eval_single_segment(seg, cfg)
        if is_loop:
            has_hallucination = True
        elif c_item:
            clean_sub.append(c_item)
        elif u_item:
            uncertain_sub.append(u_item)
    return clean_sub, uncertain_sub, has_hallucination


def _extract_clean_stem_segments(vocal_segs: list, cfg: WhisperTask) -> Optional[list]:
    if not vocal_segs:
        return None
    valid = [s for s in vocal_segs if s.get("text", "").strip()]
    if not valid:
        return None
    if any(is_hallucinated(s["text"].strip(), cfg.threshold) for s in valid):
        return None
    return [_format_segment_item(s, cfg.start_ms, cfg.end_ms) for s in valid]


def _try_audiocpp_stem_recovery(slice_wav: Path, cfg: WhisperTask) -> Optional[list]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="audiocpp_stem_"))
    try:
        vocals_path, _ = separate_via_audiocpp_api(slice_wav, tmp_dir, server_url=cfg.audiocpp_url)
        vocal_segs = run_whisper_on_slice(vocals_path, cfg.whisper_cfg)
        clean_items = _extract_clean_stem_segments(vocal_segs, cfg)
        if clean_items:
            log_event(cfg.worker_id, "STEM-RECOVERED", f"Range {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)} [STEM-RECOVERED] Isolated vocals: {len(clean_items)} clean segments", cfg.tracker)
            return clean_items
    except Exception as e:
        log_event(cfg.worker_id, "WARN", f"audio.cpp stem recovery failed: {e}", cfg.tracker)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    log_event(cfg.worker_id, "STEM-FALLBACK", f"Range {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)} [STEM-FALLBACK] Falling back to D&C split", cfg.tracker)
    return None


def _resolve_hallucination(slice_wav: Path, cfg: WhisperTask) -> tuple[Optional[list], list]:
    if cfg.audiocpp_url:
        recovered = _try_audiocpp_stem_recovery(slice_wav, cfg)
        if recovered is not None:
            return recovered, []
    mid = (cfg.start_ms + cfg.end_ms) // 2
    next_sub = [(cfg.start_ms, mid), (mid, cfg.end_ms)]
    log_event(cfg.worker_id, "SPLIT", f"Queueing 2 sub-tasks: {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(mid/1000.0)} & {_fmt_ts(mid/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)}", cfg.tracker)
    return None, next_sub


def _evaluate_and_recover_task(cfg: WhisperTask, slice_wav: Path, segs: list) -> tuple:
    if not segs:
        item = _build_uncertain_item(cfg.start_ms, cfg.end_ms)
        log_event_and_advance(cfg.worker_id, "EVAL", f"Range {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)} [?] UNCERTAIN (empty text)", cfg.tracker)
        return cfg.worker_num, cfg.start_ms, cfg.end_ms, [], [item], []

    clean_sub, uncertain_sub, has_loop = _classify_segments(segs, cfg)
    next_sub = []
    if has_loop:
        stem_clean, next_sub = _resolve_hallucination(slice_wav, cfg)
        if stem_clean is not None:
            clean_sub = stem_clean
        else:
            clean_sub.clear()

    log_event_and_advance(cfg.worker_id, "DONE", f"Task complete: {_fmt_ts(cfg.start_ms/1000.0)} -> {_fmt_ts(cfg.end_ms/1000.0)}", cfg.tracker)
    return cfg.worker_num, cfg.start_ms, cfg.end_ms, clean_sub, uncertain_sub, next_sub


def _try_whisper_task(task: tuple | WhisperTask) -> tuple:
    """
    Worker function for one BFS task. Evaluates text and logs instantly.
    task = (worker_num, start_ms, end_ms, audio_wav, model, threshold, min_duration_s, tracker, device, threads, [endpoint], [audiocpp_url])
    """
    cfg = _parse_task(task)
    slice_wav = None
    try:
        slice_wav, segs = _execute_slice_whisper(cfg)
        if segs is None:
            return cfg.worker_num, cfg.start_ms, cfg.end_ms, None, [], [(cfg.start_ms, cfg.end_ms)]
        return _evaluate_and_recover_task(cfg, slice_wav, segs)
    finally:
        if slice_wav is not None:
            slice_wav.unlink(missing_ok=True)


@dataclass
class RecoveryOptions:
    model: str = MODEL_PATH
    threshold: float = 0.4
    min_duration_s: float = 1.0
    workers: int = 3
    max_consec_repeat: int = 4
    devices: int | list = 0
    threads: int = 4
    endpoint: Optional[str] = None
    audiocpp_url: Optional[str] = None


def _apply_recovery_kwargs(opts: RecoveryOptions, kwargs: dict) -> None:
    for k, v in kwargs.items():
        if v is not None and hasattr(opts, k):
            setattr(opts, k, v)


def _normalize_recovery_options(
    options: Optional[RecoveryOptions | str] = None,
    *args,
    **kwargs,
) -> RecoveryOptions:
    if isinstance(options, RecoveryOptions):
        return options
    opts = RecoveryOptions()
    if isinstance(options, str):
        opts.model = options
    if len(args) > 0 and isinstance(args[0], (int, float)):
        opts.threshold = float(args[0])
    if len(args) > 1 and isinstance(args[1], (int, float)):
        opts.min_duration_s = float(args[1])
    _apply_recovery_kwargs(opts, kwargs)
    return opts


@dataclass
class LevelContext:
    audio_wav: Path
    opts: RecoveryOptions
    level: int = 0


def _cap_stuck_tasks(pending: list, level: int) -> list:
    log_event("MAIN", "WARN", f"[Level {level}] MAX_LEVEL reached — marking {len(pending)} tasks as uncertain")
    return [
        {
            "text": "[?] (stuck loop)",
            "start": s / 1000.0,
            "duration": (e - s) / 1000.0,
            "timestamp": _fmt_ts(s / 1000.0),
            "uncertain": True,
        }
        for s, e in pending
    ]


def _build_whisper_task(task_spec: tuple, audio_wav: Path, opts: RecoveryOptions) -> WhisperTask:
    idx, (s, e), tracker, dev_list = task_spec
    return WhisperTask(
        worker_num=idx % opts.workers + 1, start_ms=s, end_ms=e, audio_wav=audio_wav,
        model=opts.model, threshold=opts.threshold, min_duration_s=opts.min_duration_s,
        tracker=tracker, device=dev_list[idx % len(dev_list)], threads=opts.threads,
        endpoint=opts.endpoint, audiocpp_url=opts.audiocpp_url,
    )


def _run_bfs_level(
    executor: ThreadPoolExecutor,
    pending: list,
    ctx: LevelContext,
) -> tuple:
    dev_list = ctx.opts.devices if isinstance(ctx.opts.devices, (list, tuple)) else [ctx.opts.devices]
    tracker = ProgressTracker(f"Level {ctx.level}", len(pending))
    futures = [
        executor.submit(_try_whisper_task, _build_whisper_task((i, (s, e), tracker, dev_list), ctx.audio_wav, ctx.opts))
        for i, (s, e) in enumerate(pending)
    ]
    clean_sub, uncertain_sub, next_pending = [], [], []
    for f in as_completed(futures):
        _, _, _, c_items, u_items, n_items = f.result()
        clean_sub.extend(c_items or [])
        uncertain_sub.extend(u_items)
        next_pending.extend(n_items)
    return clean_sub, uncertain_sub, next_pending


def _process_bfs_queue(executor: ThreadPoolExecutor, pending: list, ctx: LevelContext) -> tuple[list, list]:
    clean_items, uncertain_items = [], []
    max_level = 20
    while pending:
        if ctx.level >= max_level:
            uncertain_items.extend(_cap_stuck_tasks(pending, ctx.level))
            break
        c_items, u_items, pending = _run_bfs_level(executor, pending, ctx)
        clean_items.extend(c_items)
        uncertain_items.extend(u_items)
        ctx = LevelContext(ctx.audio_wav, ctx.opts, ctx.level + 1)
    return clean_items, uncertain_items


def _bfs_recover(
    ranges: list,
    audio_wav: Path,
    options: Optional[RecoveryOptions] = None,
    *args,
    **kwargs,
) -> tuple:
    """BFS parallel divide-and-conquer recovery across single or multiple GPUs, or remote whisper-server."""
    opts = _normalize_recovery_options(options, *args, **kwargs)
    ctx = LevelContext(audio_wav=audio_wav, opts=opts, level=0)
    with ThreadPoolExecutor(max_workers=opts.workers) as executor:
        return _process_bfs_queue(executor, list(ranges), ctx)


def _partition_uncertain_runs(items: list, min_dur: float) -> tuple:
    runs, run = [], [items[0]]
    for item in items[1:]:
        prev_end = run[-1]["start"] + run[-1]["duration"]
        if item["start"] - prev_end < 0.1:
            run.append(item)
        else:
            runs.append(run)
            run = [item]
    runs.append(run)
    retry_runs = [r for r in runs if sum(i["duration"] for i in r) > min_dur]
    keep_runs = [r for r in runs if sum(i["duration"] for i in r) <= min_dur]
    return retry_runs, [item for r in keep_runs for item in r]


def _execute_second_chance_tasks(retry_runs: list, audio_wav: Path, opts: RecoveryOptions) -> tuple:
    dev_list = opts.devices if isinstance(opts.devices, (list, tuple)) else [opts.devices]
    tracker = ProgressTracker("Second-Chance", len(retry_runs))
    ranges = [(int(r[0]["start"] * 1000), int((r[-1]["start"] + r[-1]["duration"]) * 1000)) for r in retry_runs]
    tasks = [
        _build_whisper_task((i, (s, e), tracker, dev_list), audio_wav, opts)
        for i, (s, e) in enumerate(ranges)
    ]
    with ThreadPoolExecutor(max_workers=opts.workers) as executor:
        results = list(executor.map(_try_whisper_task, tasks))
    recovered, still_uncertain = [], []
    for run, (_, _, _, c_sub, u_sub, _) in zip(retry_runs, results):
        if c_sub:
            recovered.extend(c_sub)
            still_uncertain.extend(u_sub)
        else:
            still_uncertain.extend(run)
    return recovered, still_uncertain


def _second_chance_pass(
    uncertain_items: list,
    audio_wav: Path,
    options: Optional[RecoveryOptions] = None,
    *args,
    **kwargs,
) -> tuple:
    """Merge consecutive [?] runs spanning > 1s and retry recovery in parallel across GPUs or remote whisper-server."""
    if not uncertain_items:
        return [], []
    opts = _normalize_recovery_options(options, *args, **kwargs)
    sorted_items = sorted(uncertain_items, key=lambda x: x["start"])
    retry_runs, still_uncertain = _partition_uncertain_runs(sorted_items, opts.min_duration_s)
    if not retry_runs:
        return [], still_uncertain
    recovered, retry_uncertain = _execute_second_chance_tasks(retry_runs, audio_wav, opts)
    return recovered, still_uncertain + retry_uncertain


def _mark_phoneme_loops(items: list, threshold: float) -> None:
    for item in items:
        text = item.get("text", "")
        if is_hallucinated(text, threshold) and not text.startswith("[?]"):
            item["text"] = f"[?] {text}"
            item["uncertain"] = True


def _match_pattern_at_index(texts: list, i: int, pat_len: int, min_rep: int) -> int:
    pattern = texts[i : i + pat_len]
    if not any(len(t) > 1 for t in pattern):
        return 0
    matches, curr, n = 0, i, len(texts)
    while curr + pat_len <= n and texts[curr : curr + pat_len] == pattern:
        matches += 1
        curr += pat_len
    return curr if matches >= min_rep else 0


def _find_pattern_loops(items: list) -> list:
    n = len(items)
    texts = [items[k].get("text", "").replace("[?] ", "").strip() for k in range(n)]
    is_corrupt = [False] * n
    for pat_len in range(1, 4):
        min_rep = 4 if pat_len == 1 else 3
        i = 0
        while i <= n - (pat_len * min_rep):
            match_end = _match_pattern_at_index(texts, i, pat_len, min_rep)
            if match_end > 0:
                for k in range(i, match_end):
                    is_corrupt[k] = True
                i = match_end
            else:
                i += 1
    return is_corrupt


def _extract_corrupt_ranges(items: list, is_corrupt: list) -> list:
    ranges, curr_start, curr_end = [], None, None
    for i, item in enumerate(items):
        if is_corrupt[i]:
            start_ms = int(item["start"] * 1000)
            end_ms = int((item["start"] + item.get("duration", 0)) * 1000)
            curr_start = start_ms if curr_start is None else curr_start
            curr_end = end_ms if curr_end is None else max(curr_end, end_ms)
        elif curr_start is not None:
            ranges.append((curr_start, curr_end))
            curr_start, curr_end = None, None
    if curr_start is not None:
        ranges.append((curr_start, curr_end))
    return ranges


def _chunk_ranges(ranges: list, max_chunk_ms: int = 30000) -> list:
    chunked = []
    for st, en in ranges:
        curr = st
        while curr < en:
            nxt = min(curr + max_chunk_ms, en)
            chunked.append((curr, nxt))
            curr = nxt
    return chunked


def _dedup_consecutive_repeats(items: list) -> list:
    dedup, i, n = [], 0, len(items)
    fillers = {"โอเค", "เออ", "อืม", "อื้อ", "เอ่อ", "อ้าว"}
    while i < n:
        j = i + 1
        t = items[i].get("text", "").strip()
        while j < n and items[j].get("text", "").strip() == t:
            j += 1
        if (j - i) >= 3 and len(t) > 2 and t not in fillers:
            dedup.append(items[i])
        else:
            dedup.extend(items[i:j])
        i = j
    return dedup


def _scan_corruptions(items: list, threshold: float) -> tuple[list, list]:
    _mark_phoneme_loops(items, threshold)
    is_corrupt = _find_pattern_loops(items)
    ranges = _extract_corrupt_ranges(items, is_corrupt)
    return is_corrupt, ranges


def _recover_corrupt_ranges(ranges: list, audio_wav: Path, opts: RecoveryOptions) -> list:
    chunked = _chunk_ranges(ranges)
    clean_rec, uncertain = _bfs_recover(chunked, audio_wav, opts)
    sc_rec, sc_unc = _second_chance_pass(uncertain, audio_wav, opts)
    return clean_rec + sc_rec + sc_unc


def detect_and_recover(
    items: list,
    audio_wav: Path,
    options: Optional[RecoveryOptions] = None,
    *args,
    **kwargs,
) -> list:
    """Scan items for loops, run D&C recovery, and return timestamp-sorted list."""
    opts = _normalize_recovery_options(options, *args, **kwargs)
    is_corrupt, ranges = _scan_corruptions(items, opts.threshold)
    if not ranges:
        return items
    clean_orig = [item for i, item in enumerate(items) if not is_corrupt[i]]
    if not audio_wav.exists():
        return clean_orig

    recovered = _recover_corrupt_ranges(ranges, audio_wav, opts)
    result = sorted(clean_orig + recovered, key=lambda x: x["start"])
    return _dedup_consecutive_repeats(result)



# ---------------------------------------------------------------------------
# Task 4: Standalone CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Detect and fix Whisper in-segment phoneme loop hallucinations with multi-worker / multi-GPU support."
    )
    ap.add_argument("whisper_json", help="Path to whisper-cli JSON output (audio.wav.json)")
    ap.add_argument("audio_wav",    help="Path to original WAV audio file")
    ap.add_argument("--model",        default=MODEL_PATH,
                    help=f"Path to GGML model (default: {MODEL_PATH})")
    ap.add_argument("--threshold",    type=float, default=0.4,
                    help="N-gram repetition ratio threshold (default: 0.4)")
    ap.add_argument("--min-duration", type=float, default=1.0,
                    help="Min slice duration in seconds before discarding (default: 1.0)")
    ap.add_argument("-w", "--workers", type=int, default=4,
                    help="Number of parallel whisper-cli workers (default: 4)")
    ap.add_argument("-dev", "--devices", nargs="+", default=["0"],
                    help="GPU device ID(s) for whisper-cli pool, e.g. --devices 0 1 (default: 0)")
    ap.add_argument("-t", "--threads", type=int, default=4,
                    help="CPU threads per worker (default: 4)")
    ap.add_argument("--endpoint", default=None,
                    help="Remote or local whisper-server endpoint URL (e.g. http://100.115.25.30:8080/v1/audio/transcriptions)")
    ap.add_argument("--audiocpp-url", default=os.environ.get("AUDIOCPP_URL", None),
                    help="audio.cpp HTDemucs stem separation server URL (default: $AUDIOCPP_URL or None)")
    ap.add_argument("-o", "--output", default=None,
                    help="Output JSON path (default: overwrite input)")
    args = ap.parse_args()

    # Parse devices (accepts list of strings or comma-separated values)
    parsed_devices = []
    for d in args.devices:
        for sub in str(d).split(","):
            sub = sub.strip()
            if sub.isdigit():
                parsed_devices.append(int(sub))
    if not parsed_devices:
        parsed_devices = [0]

    json_path  = Path(args.whisper_json)
    audio_path = Path(args.audio_wav)
    out_path   = Path(args.output) if args.output else json_path

    target_desc = f"server {args.endpoint}" if args.endpoint else f"Target GPUs: {parsed_devices}"
    log_event("MAIN", "INIT", f"Loading {json_path} ... ({target_desc})")
    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    raw = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            text = item.get("text", "").strip()
            if not text or len(text) == 1:
                continue
            start_s = float(item.get("start", 0))
            dur_s = float(item.get("duration", 0))
            raw.append({
                "text": text,
                "start": start_s,
                "duration": dur_s,
                "timestamp": item.get("timestamp") or _fmt_ts(start_s),
            })
    else:
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

    opts = RecoveryOptions(
        model=args.model,
        threshold=args.threshold,
        min_duration_s=args.min_duration,
        workers=args.workers,
        devices=parsed_devices,
        threads=args.threads,
        endpoint=args.endpoint,
        audiocpp_url=args.audiocpp_url,
    )
    fixed = detect_and_recover(raw, audio_path, opts)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)

    log_event("MAIN", "DONE", f"Wrote {len(fixed):,} items to {out_path}")


if __name__ == "__main__":
    main()
