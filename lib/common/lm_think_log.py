"""LM Studio thinking/reasoning trace logger, performance telemetry, and error detector."""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common.log import log_info, log_warn

_LOCK = threading.Lock()
_TRACE_PATH: Optional[Path] = None
_VERBOSE_THINK: bool = False

_INLINE_THINK_RE = re.compile(
    r"(?:<think>(.*?)</think>|<thought>(.*?)</thought>|<\|channel>thought\r?\n?(.*?)<channel\|>)",
    re.DOTALL | re.IGNORECASE,
)
_OPEN_TAG_RE = re.compile(r"(<think>|<thought>|<\|channel>thought)", re.IGNORECASE)
_CLOSE_TAG_RE = re.compile(r"(</think>|</thought>|<channel\|>)", re.IGNORECASE)
_THINK_OVERFLOW_TOKENS, _THINK_OVERFLOW_CHARS = 150, 600

@dataclass(frozen=True)
class LmThinkAnalysis:
    """Extracted thinking, clean output, usage telemetry, and error flags."""
    raw_content: str
    clean_content: str
    think_text: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    errors: Tuple[str, ...]

def configure_lm_think_logging(trace_path: Optional[Path] = None, verbose: bool = False) -> None:
    """Configure workspace JSONL trace destination and verbose console logging."""
    global _TRACE_PATH, _VERBOSE_THINK
    with _LOCK:
        _TRACE_PATH = Path(trace_path) if trace_path else None
        _VERBOSE_THINK = bool(verbose or os.environ.get("ANIBON_LOG_THINK") == "1")

def _active_trace_path() -> Optional[Path]:
    if _TRACE_PATH is not None:
        return _TRACE_PATH
    env_p = os.environ.get("ANIBON_LM_TRACE_PATH", "").strip()
    return Path(env_p) if env_p else None


def _split_inline_think(raw: str) -> Tuple[str, str, bool]:
    """Separate closed inline think blocks from answer and detect unclosed tags."""
    if not raw:
        return ("", "", False)
    blocks = [next(g for g in m.groups() if g is not None).strip() for m in _INLINE_THINK_RE.finditer(raw)]
    cleaned = _INLINE_THINK_RE.sub("", raw).strip()
    opens = len(_OPEN_TAG_RE.findall(raw))
    closes = len(_CLOSE_TAG_RE.findall(raw))
    return (cleaned, "\n".join(b for b in blocks if b), opens > closes)


def _extract_raw_fields(data: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return (raw_content, api_reasoning, finish_reason) from OpenAI or native payload."""
    if "choices" in data and data["choices"]:
        ch = data["choices"][0]
        msg = ch.get("message") or {}
        content = (msg.get("content") or "").strip()
        rsn = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
        return (content, rsn, str(ch.get("finish_reason") or ""))
    if "output" in data and isinstance(data["output"], list):
        msgs = [str(i.get("content", "")) for i in data["output"] if i.get("type") == "message"]
        rsns = [str(i.get("content", "")) for i in data["output"] if i.get("type") == "reasoning"]
        return ("\n".join(msgs).strip(), "\n".join(rsns).strip(), str(data.get("status") or ""))
    return ("", "", "")


def _has_repetition_loop(text: str) -> bool:
    """Detect degenerate >=4x repeated 24-char substrings in think or output."""
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) < 120:
        return False
    return bool(re.search(r"(.{24,80}?)\1{3,}", compact))


def _detect_errors(
    clean_content: str, think_text: str, finish_reason: str, reasoning_tokens: int, unclosed: bool
) -> Tuple[str, ...]:
    """Identify structural, truncation, overflow, or loop anomalies in LM response."""
    errs: List[str] = []
    if not clean_content.strip():
        errs.append("EMPTY_CONTENT")
    if unclosed:
        errs.append("UNCLOSED_THINK_TAG")
    if finish_reason == "length":
        errs.append("TRUNCATED_LENGTH")
    if reasoning_tokens > _THINK_OVERFLOW_TOKENS or len(think_text) > _THINK_OVERFLOW_CHARS:
        errs.append("THINK_OVERFLOW")
    if _has_repetition_loop(think_text) or _has_repetition_loop(clean_content):
        errs.append("REPETITION_LOOP")
    return tuple(errs)


def analyze_lm_response(data: Dict[str, Any]) -> LmThinkAnalysis:
    """Parse reasoning blocks, token usage, clean answer, and error diagnostics."""
    raw_content, api_rsn, finish_reason = _extract_raw_fields(data)
    clean_content, inline_rsn, unclosed = _split_inline_think(raw_content)
    think_text = "\n".join(part for part in (api_rsn, inline_rsn) if part).strip()
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    p_tok = int(usage.get("prompt_tokens") or 0)
    c_tok = int(usage.get("completion_tokens") or 0)
    r_tok = int(details.get("reasoning_tokens") or (len(think_text) // 4 if think_text else 0))
    errs = _detect_errors(clean_content, think_text, finish_reason, r_tok, unclosed)
    return LmThinkAnalysis(raw_content, clean_content, think_text, finish_reason, p_tok, c_tok, r_tok, errs)


def _format_snippet(think_text: str, limit: int = 140) -> str:
    compact = re.sub(r"\s+", " ", think_text or "").strip()
    if not compact:
        return ""
    return f" | \"{compact[:limit]}{'...' if len(compact) > limit else ''}\""


def _write_trace_line(path: Path, entry: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _build_trace_entry(
    res: LmThinkAnalysis, call_type: str, model: str, elapsed_s: float
) -> Dict[str, Any]:
    """Build JSON-serializable trace record for JSONL telemetry output."""
    return {
        "ts": datetime.now().isoformat(timespec="seconds"), "call_type": call_type, "model": model,
        "elapsed_s": round(elapsed_s, 3), "finish_reason": res.finish_reason,
        "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
        "reasoning_tokens": res.reasoning_tokens, "think_chars": len(res.think_text),
        "content_chars": len(res.clean_content), "errors": list(res.errors),
        "think": res.think_text, "content_preview": res.clean_content[:400],
    }


def record_lm_response(
    data: Dict[str, Any], call_type: str, model: str, elapsed_s: float
) -> LmThinkAnalysis:
    """Analyze LM response, append JSONL telemetry, and surface think errors/logs."""
    res = analyze_lm_response(data)
    trace_path = _active_trace_path()
    if trace_path is not None:
        _write_trace_line(trace_path, _build_trace_entry(res, call_type, model, elapsed_s))
    tok = f"tok={res.prompt_tokens}+{res.completion_tokens}(think={res.reasoning_tokens})"
    snip = _format_snippet(res.think_text)
    if res.errors:
        log_warn("lm-think", f"{call_type} | err={','.join(res.errors)} | {elapsed_s:.1f}s | {tok}{snip}")
    elif _VERBOSE_THINK or os.environ.get("ANIBON_LOG_THINK") == "1":
        log_info("lm-think", f"{call_type} | {elapsed_s:.1f}s | {tok}{snip}")
    return res


def _read_trace_rows(trace_path: Path) -> List[Dict[str, Any]]:
    """Read valid JSONL records from trace_path."""
    rows: List[Dict[str, Any]] = []
    for line in Path(trace_path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows

def summarize_lm_trace(trace_path: Path) -> Dict[str, Any]:
    """Aggregate latency, token throughput, and think error counts from JSONL trace."""
    if not Path(trace_path).is_file() or not (rows := _read_trace_rows(Path(trace_path))):
        return {"calls": 0}
    err_counts: Dict[str, int] = {}
    for row in rows:
        for err in row.get("errors", ()):
            err_counts[err] = err_counts.get(err, 0) + 1
    tot_s = sum(float(r.get("elapsed_s", 0.0)) for r in rows)
    tot_p = sum(int(r.get("prompt_tokens", 0)) for r in rows)
    tot_c = sum(int(r.get("completion_tokens", 0)) for r in rows)
    return {
        "calls": len(rows), "total_elapsed_s": round(tot_s, 2),
        "prompt_tokens": tot_p, "completion_tokens": tot_c,
        "reasoning_tokens": sum(int(r.get("reasoning_tokens", 0)) for r in rows),
        "tok_per_sec": round(tot_c / max(tot_s, 0.001), 2),
        "total_tok_per_sec": round((tot_p + tot_c) / max(tot_s, 0.001), 2),
        "errors": err_counts,
    }

__all__ = ["LmThinkAnalysis", "analyze_lm_response", "configure_lm_think_logging", "record_lm_response", "summarize_lm_trace"]
