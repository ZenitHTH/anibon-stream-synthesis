"""Standardized aligned column logger for Anibon livestream pipelines."""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Callable, Optional, Sequence

_BANNER_WIDTH: int = 78
_TAG_WIDTH: int = 10
_LVL_WIDTH: int = 5
_KV_WIDTH: int = 15
_STDERR_LEVELS = frozenset({"WARN", "ERROR"})
_CONT_PREFIX = f"{'':8} | {'':5} | {'':{_TAG_WIDTH}} | "

_clock_fn: Optional[Callable[[], datetime]] = None


def set_clock(fn: Optional[Callable[[], datetime]]) -> None:
    """Override wall-clock generator for deterministic tests (None resets to now)."""
    global _clock_fn
    _clock_fn = fn


def _timestamp() -> str:
    """Return local HH:MM:SS timestamp string."""
    now = _clock_fn() if _clock_fn is not None else datetime.now()
    return now.strftime("%H:%M:%S")


def _format_line(level: str, tag: str, message: str) -> str:
    """Format a single fixed-column structured log line."""
    lvl = level.upper()[:_LVL_WIDTH].ljust(_LVL_WIDTH)
    norm_tag = tag.lower().strip()[:_TAG_WIDTH].ljust(_TAG_WIDTH)
    return f"{_timestamp()} | {lvl} | {norm_tag} | {message}"


def _write_line(line: str, to_stderr: bool) -> None:
    """Write flushed log line to stdout or stderr without interleaving noise."""
    if to_stderr:
        sys.stdout.flush()
        print(line, file=sys.stderr, flush=True)
        return
    print(line, file=sys.stdout, flush=True)


def _emit(level: str, tag: str, message: str) -> None:
    """Emit structured log line routed by severity level."""
    lvl = level.upper().strip()
    _write_line(_format_line(lvl, tag, message), to_stderr=(lvl in _STDERR_LEVELS))


def log_info(tag: str, message: str) -> None:
    """Emit informational status line."""
    _emit("INFO", tag, message)


def log_ok(tag: str, message: str) -> None:
    """Emit completion or success status line."""
    _emit("OK", tag, message)


def log_warn(tag: str, message: str) -> None:
    """Emit warning status line to stderr."""
    _emit("WARN", tag, message)


def log_error(tag: str, message: str) -> None:
    """Emit error status line to stderr."""
    _emit("ERROR", tag, message)


def log_cont(message: str) -> None:
    """Emit continuation line aligned directly under the message column."""
    _write_line(f"{_CONT_PREFIX}{message}", to_stderr=False)


def log_kv(tag: str, key: str, value: Any) -> None:
    """Emit aligned key-value configuration or summary line."""
    _emit("INFO", tag, f"{key:<{_KV_WIDTH}} : {value}")


def log_banner(title: str) -> None:
    """Print double-ruled top header banner for run entry."""
    bar = "=" * _BANNER_WIDTH
    _write_line(f"{bar}\n  {title}\n{bar}", to_stderr=False)


def log_stage(stage: str) -> None:
    """Print single-ruled stage divider banner between pipeline phases."""
    bar = "-" * _BANNER_WIDTH
    _write_line(f"{bar}\n  {stage}\n{bar}", to_stderr=False)


def log_block(tag: str, level: str, text: str) -> None:
    """Emit multi-line subprocess or gate output aligned cleanly under one header."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return
    _emit(level, tag, lines[0])
    for extra in lines[1:]:
        log_cont(extra)


def log_items(tag: str, summary: str, items: Sequence[str]) -> None:
    """Emit a summary line and indent multi-item results cleanly underneath."""
    if not items:
        log_ok(tag, summary)
        return
    if len(items) == 1:
        log_ok(tag, f"{summary} -> {items[0]}")
        return
    log_ok(tag, f"{summary}:")
    for item in items:
        log_cont(f"- {item}")


def format_progress(step: int, total: int) -> str:
    """Format 1-based aligned step counter and percentage, e.g. [01/95   1%]."""
    safe_total = max(1, total)
    clamped = max(0, min(step, safe_total))
    width = max(2, len(str(safe_total)))
    pct = int(round((clamped * 100) / safe_total))
    return f"[{clamped:0{width}d}/{safe_total:0{width}d} {pct:3d}%]"


def format_duration(seconds: float) -> str:
    """Format elapsed seconds compactly as Xs, XmYYs, or XhYYm."""
    sec = max(0.0, seconds)
    if sec < 60.0:
        return f"{sec:.1f}s"
    total_sec = int(sec)
    if total_sec < 3600:
        return f"{total_sec // 60}m{total_sec % 60:02d}s"
    return f"{total_sec // 3600}h{(total_sec % 3600) // 60:02d}m"


__all__ = [
    "format_duration",
    "format_progress",
    "log_banner",
    "log_block",
    "log_cont",
    "log_error",
    "log_info",
    "log_items",
    "log_kv",
    "log_ok",
    "log_stage",
    "log_warn",
    "set_clock",
]
