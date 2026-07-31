#!/usr/bin/env python3
"""Detect Whisper/whisper.cpp repetition loops and hallucinations using multithreaded n-gram frequency analysis.

# ponytail: stdlib ThreadPoolExecutor & Counter for parallel segment analysis.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from anibon.corruption import detect_segment_hallucination, is_hallucinated, analyze_transcript
except ImportError:
    from concurrent.futures import ThreadPoolExecutor

    def detect_segment_hallucination(text: str, threshold: float = 0.4, min_repeats: int = 3):
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
        score = top_count / len(ngram_list)
        is_h = top_count >= min_repeats and score >= threshold
        phrase = " ".join(most_common) if isinstance(most_common, tuple) else str(most_common)
        return is_h, score, phrase

    def is_hallucinated(text: str, threshold: float = 0.4) -> bool:
        flag, _, _ = detect_segment_hallucination(text, threshold)
        return flag

    def analyze_transcript(data, threshold: float = 0.4, workers: int = None):
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


        def eval_item(it):
            if isinstance(it, tuple):
                idx, line = it
                is_h, score, phrase = detect_segment_hallucination(line, threshold)
                return {"line": idx, "text": line, "hallucination": is_h, "score": round(score, 3), "repeat_pattern": phrase}
            else:
                text = it.get("text", "")
                is_h, score, phrase = detect_segment_hallucination(text, threshold)
                return {"id": it.get("id"), "start": it.get("start"), "end": it.get("end"), "text": text, "hallucination": is_h, "score": round(score, 3), "repeat_pattern": phrase}

        if len(items) > 50:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                return list(executor.map(eval_item, items))
        return [eval_item(it) for it in items]


def self_check():
    """Assert-based test suite for ponytail verification."""
    normal_text = "สวัสดีครับ วันนี้เราจะมาเล่นเกม Minecraft กันนะครับ"
    is_h, score, _ = detect_segment_hallucination(normal_text)
    assert not is_h, f"False positive on normal speech: score={score}"

    repeated_text = "ขอบคุณครับ ขอบคุณครับ ขอบคุณครับ ขอบคุณครับ ขอบคุณครับ"
    is_h, score, pattern = detect_segment_hallucination(repeated_text)
    assert is_h, f"Failed to flag repeated words: score={score}"
    assert "ขอบคุณครับ" in pattern

    loop_text = "มา มา มา มา มา มา มา มา มา มา"
    is_h, score, _ = detect_segment_hallucination(loop_text)
    assert is_h, f"Failed to flag single word loop: score={score}"

    # Multithreading batch check
    large_batch = {"segments": [{"id": i, "text": repeated_text if i % 10 == 0 else normal_text} for i in range(100)]}
    report = analyze_transcript(large_batch, threshold=0.4, workers=4)
    assert len(report) == 100, f"Expected 100 items, got {len(report)}"
    flagged = [r for r in report if r["hallucination"]]
    assert len(flagged) == 10, f"Expected 10 flagged items in batch, got {len(flagged)}"

    print("Self-check passed (multithreaded batch verified).")


if __name__ == "__main__":
    if "--test" in sys.argv:
        self_check()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Detect Whisper hallucinations via multithreaded n-gram frequency analysis.")
    parser.add_argument("input", nargs="?", help="Path to input file (.json or .txt/.vtt/.srt)")
    parser.add_argument("-t", "--threshold", type=float, default=0.4, help="Frequency ratio threshold (default: 0.4)")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Number of thread workers (default: CPU auto)")
    parser.add_argument("-o", "--output", help="Path to save output JSON report")
    parser.add_argument("-a", "--audio", help="Audio file path (.wav) to trigger whisper-corruption-recovery skill")
    parser.add_argument("--auto-recover", action="store_true", help="Auto-trigger fix_hallucinations.py if corrupt segments found")
    args = parser.parse_args()

    if not args.input:
        self_check()
        sys.exit(0)

    with open(args.input, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        content = raw

    report = analyze_transcript(content, args.threshold, workers=args.workers)
    flagged = [r for r in report if r["hallucination"]]
    print(f"Processed {len(report)} segments across threads. Flagged {len(flagged)} hallucinations.")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Report saved to {args.output}")

    if flagged and (args.auto-recover or args.audio):
        import subprocess
        from pathlib import Path

        recovery_script = Path.home() / ".agents/skills/whisper-corruption-recovery/scripts/fix_hallucinations.py"
        if not recovery_script.exists():
            print(f"Recovery script not found at {recovery_script}")
            sys.exit(1)

        if not args.audio:
            print("Hallucinations detected! Pass --audio <audio.wav> to run automated recovery.")
        else:
            out_file = args.output or "recovered_transcript.json"
            cmd = [sys.executable, str(recovery_script), args.input, args.audio, "-o", out_file, "--threshold", str(args.threshold)]
            print(f"\n[!] Triggering whisper-corruption-recovery skill...\nRunning: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
