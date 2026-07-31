"""Whisper repetition loop & hallucination detection utilities with multithreaded analysis.

# ponytail: stdlib Counter, re, and ThreadPoolExecutor for parallel segment analysis.
"""

import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def detect_segment_hallucination(text: str, threshold: float = 0.4, min_repeats: int = 3):
    """Analyzes text for repeating n-gram loops.
    Returns: (is_hallucinated: bool, score: float, top_pattern: str)
    """
    if not text or not text.strip():
        return False, 0.0, ""

    words = text.strip().split()
    if len(words) < 4:
        tokens = list(re.sub(r"\s+", "", text))
        n_size = 3
    else:
        tokens = words
        n_size = 2

    if len(tokens) < n_size * 2:
        return False, 0.0, ""

    ngram_list = [tuple(tokens[i:i + n_size]) for i in range(len(tokens) - n_size + 1)]
    counts = Counter(ngram_list)
    if not counts:
        return False, 0.0, ""

    most_common, top_count = counts.most_common(1)[0]
    total_ngrams = len(ngram_list)
    score = top_count / total_ngrams

    is_hallucinated = top_count >= min_repeats and score >= threshold
    phrase = " ".join(most_common) if isinstance(most_common, tuple) else str(most_common)
    return is_hallucinated, score, phrase


def is_hallucinated(text: str, threshold: float = 0.4) -> bool:
    """Fast boolean check for repetition hallucination loops."""
    flag, _, _ = detect_segment_hallucination(text, threshold=threshold)
    return flag


def _eval_item(item, threshold: float):
    """Worker task for single line or segment dict."""
    if isinstance(item, tuple):  # (line_no, line_text)
        idx, line = item
        is_h, score, phrase = detect_segment_hallucination(line, threshold)
        return {
            "line": idx,
            "text": line,
            "hallucination": is_h,
            "score": round(score, 3),
            "repeat_pattern": phrase
        }
    else:  # segment dict
        text = item.get("text", "")
        is_h, score, phrase = detect_segment_hallucination(text, threshold)
        return {
            "id": item.get("id"),
            "start": item.get("start"),
            "end": item.get("end"),
            "text": text,
            "hallucination": is_h,
            "score": round(score, 3),
            "repeat_pattern": phrase
        }


def analyze_transcript(data, threshold: float = 0.4, workers: int = None):
    """Processes loaded JSON or string. Uses ThreadPoolExecutor for >50 items."""
    if isinstance(data, str):
        items = [(idx + 1, line) for idx, line in enumerate(data.splitlines()) if line.strip()]
    elif isinstance(data, dict) and "segments" in data:
        items = data["segments"]
    else:
        return []

    if not items:
        return []

    if workers is None:
        workers = max(1, os.cpu_count() or 4)


    if len(items) > 50:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(lambda it: _eval_item(it, threshold), items))
    else:
        results = [_eval_item(it, threshold) for it in items]

    return results
