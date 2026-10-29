from __future__ import annotations

import difflib
import re

CONSONANT_MAP: dict[str, str] = {
    "ผ": "พ",
    "ภ": "พ",
    "ข": "ค",
    "ฆ": "ค",
    "ศ": "ส",
    "ษ": "ส",
    "ซ": "ส",
    "บ": "ป",
    "ธ": "ท",
    "ฐ": "ท",
    "ถ": "ท",
    "ฌ": "ช",
    "ฉ": "ช",
    "ญ": "ย",
    "ณ": "น",
    "ฏ": "ต",
    "ฮ": "ห",
}

VOWEL_MAP: dict[str, str] = {
    "ี": "ิ",
    "ื": "ึ",
    "ู": "ุ",
    "แ": "เ",
}


def _clean_melisma_fillers(text: str) -> str:
    cleaned = re.sub(r"\(\d\d:\d\d:\d\d\)", "", text)
    cleaned = cleaned.replace(">>", "")
    cleaned = re.sub(r"[\u0e48-\u0e4e]", "", cleaned)
    return re.sub(r"[\s\W_]+", "", cleaned)


def thai_phonetic_skeleton(text: str) -> str:
    base = _clean_melisma_fillers(text)
    consonants = [CONSONANT_MAP.get(c, c) for c in base]
    vowels = [VOWEL_MAP.get(c, c) for c in consonants]
    return "".join(vowels)


def _scan_best_window_ratio(haystack: str, needle: str) -> float:
    best = difflib.SequenceMatcher(None, haystack, needle).ratio()
    n_len = len(needle)
    min_w = max(1, int(n_len * 0.8))
    max_w = min(len(haystack), int(n_len * 1.3) + 1)
    step = 1 if len(haystack) < 120 else 2
    for w in range(min_w, max_w + 1):
        for i in range(0, len(haystack) - w + 1, step):
            sub = haystack[i : i + w]
            r = difflib.SequenceMatcher(None, sub, needle).ratio()
            if r > best:
                best = r
    return best


def phonetic_phrase_similarity(text_a: str, text_b: str) -> float:
    sk_a = thai_phonetic_skeleton(text_a)
    sk_b = thai_phonetic_skeleton(text_b)
    if len(sk_a) < 6 or len(sk_b) < 6:
        return 0.0
    if min(len(sk_a), len(sk_b)) < int(max(len(sk_a), len(sk_b)) * 0.45):
        return 0.0
    if len(sk_b) > len(sk_a):
        sk_a, sk_b = sk_b, sk_a
    return _scan_best_window_ratio(sk_a, sk_b)
