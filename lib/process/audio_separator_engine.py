"""Clean Code Audio Separation and Speech Recovery Engine.

Uses audio-separator (BS-RoFormer / MDX-Net) to isolate vocal stems from
music-polluted livestream recordings, then transcribes clean speech via whisper-cli.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from process.whisper_dispatcher import find_whisper_cli, find_whisper_model

DEFAULT_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"


@dataclass(frozen=True)
class SeparationResult:
    vocals_path: Path
    instrumental_path: Path
    transcript_text: str
    duration_sec: float


def run_stem_separation(
    audio_path: Path,
    output_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> tuple[Path, Path]:
    from audio_separator.separator import Separator

    output_dir.mkdir(parents=True, exist_ok=True)
    sep = Separator(
        output_dir=str(output_dir),
        output_format="WAV",
        model_file_dir="/tmp/audio-separator-models/",
    )
    sep.load_model(model_name)
    outputs = sep.separate(str(audio_path))
    voc = next(output_dir / f for f in outputs if "(Vocals)" in f)
    inst = next(output_dir / f for f in outputs if "(Instrumental)" in f)
    return voc, inst


def convert_audio_to_16k_mono(input_path: Path, output_path: Path) -> Path:
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def run_whisper_transcription(
    audio_path: Path,
    language: str = "th",
    cli_path: Optional[str] = None,
    model_path: Optional[str] = None,
) -> str:
    bin_path = cli_path or find_whisper_cli()
    m_path = model_path or find_whisper_model()
    if not (bin_path and m_path):
        raise RuntimeError("whisper-cli or model not discovered on host")

    cmd = [bin_path, "-m", m_path, "-f", str(audio_path), "-l", language, "-t", "4", "--no-timestamps"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [
        l.strip() for l in proc.stdout.splitlines()
        if l.strip() and not l.startswith("main:") and not l.startswith("system_info:")
    ]
    return " ".join(lines).strip()


def calculate_audio_duration(audio_path: Path) -> float:
    import soundfile as sf
    info = sf.info(str(audio_path))
    return float(info.duration)


def recover_speech_from_mixed_audio(
    mixed_audio: Path,
    output_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> SeparationResult:
    voc, inst = run_stem_separation(mixed_audio, output_dir, model_name)
    target_16k = output_dir / f"{voc.stem}_16k.wav"
    convert_audio_to_16k_mono(voc, target_16k)
    transcript = run_whisper_transcription(target_16k)
    duration = calculate_audio_duration(mixed_audio)
    return SeparationResult(
        vocals_path=voc,
        instrumental_path=inst,
        transcript_text=transcript,
        duration_sec=duration,
    )
