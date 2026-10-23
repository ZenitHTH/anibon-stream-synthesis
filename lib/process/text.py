"""
Text processing, repetition cleanup, and hallucination detection.
"""

from __future__ import annotations


def _check_ngram_coverage(text: str, n: int, threshold: float) -> bool:
    """Check if any n-gram covers more than the threshold fraction of text."""
    ngrams = [text[i : i + n] for i in range(len(text) - n + 1)]
    for gram in set(ngrams):
        count = text.count(gram)
        if count >= 2 and (count * n / len(text)) > threshold:
            return True
    return False


def is_hallucinated(text: str, threshold: float = 0.4) -> bool:
    """True if a repeated n-gram (n=2..4, count>=2) covers > threshold of text."""
    if len(text) < 8:
        return False
    for n in range(2, 5):
        if _check_ngram_coverage(text, n, threshold):
            return True
    return False
