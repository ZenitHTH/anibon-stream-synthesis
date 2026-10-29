#!/usr/bin/env python3
"""CLI runner to separate audio tracks using audio-separator and recover transcript."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from process.audio_separator_engine import recover_speech_from_mixed_audio


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path, help="Input mixed audio file")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory for stems")
    parser.add_argument("--model", default="model_bs_roformer_ep_317_sdr_12.9755.ckpt", help="Model name")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    print(f"[*] Separating stems from {args.audio.name} using {args.model}...")
    res = recover_speech_from_mixed_audio(args.audio, args.output_dir, args.model)
    print(f"[+] Vocals Stem: {res.vocals_path}")
    print(f"[+] Instrumental Stem: {res.instrumental_path}")
    print(f"[+] Duration: {res.duration_sec:.2f}s")
    print("\n=== Recovered Speech Transcript ===")
    print(res.transcript_text)


if __name__ == "__main__":
    main()
