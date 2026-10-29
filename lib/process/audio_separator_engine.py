"""Clean Code Audio Separation and Speech Recovery Engine.

Uses audio.cpp (GGUF HTDemucs) or audio-separator (BS-RoFormer) to isolate vocal stems from
music-polluted livestream recordings, then transcribes clean speech via whisper-cli.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from process.whisper_dispatcher import find_whisper_cli, find_whisper_model

DEFAULT_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
DEFAULT_AUDIOCPP_URL = "http://100.115.25.30:8080/v1/tasks/run"


@dataclass(frozen=True)
class SeparationResult:
    vocals_path: Path
    instrumental_path: Path
    transcript_text: str
    duration_sec: float


def ensure_44k_stereo_wav(input_path: Path, output_path: Path) -> Path:
    """Resample to 44.1kHz stereo WAV required by HTDemucs in audio.cpp."""
    if input_path.resolve() == output_path.resolve():
        tmp_target = output_path.with_name(f"{output_path.stem}_tmp.wav")
        ensure_44k_stereo_wav(input_path, tmp_target)
        tmp_target.replace(output_path)
        return output_path

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def mix_instrumental_stems(drums: Path, bass: Path, other: Path, out_path: Path) -> Path:
    """Mix drums, bass, and other stems into a single full instrumental track."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(drums), "-i", str(bass), "-i", str(other),
        "-filter_complex", "amix=inputs=3:normalize=0",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path


def _decode_and_save_stems(outputs: list[dict], output_dir: Path) -> tuple[Path, Path]:
    """Decode base64 audio stems and return (vocals, complete_instrumental) paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for item in outputs:
        name = item["id"]
        path = output_dir / f"{name}.wav"
        path.write_bytes(base64.b64decode(item["audio"]))
        stems[name] = path

    vocals = stems.get("vocals", output_dir / "vocals.wav")
    if all(k in stems for k in ("drums", "bass", "other")):
        inst = mix_instrumental_stems(stems["drums"], stems["bass"], stems["other"], output_dir / "instrumental.wav")
    else:
        inst = stems.get("other", output_dir / "other.wav")
    return vocals, inst


def _post_json_request(server_url: str, payload: dict, timeout: int = 180) -> dict:
    """Post JSON payload to audio.cpp server with descriptive error handling."""
    req = urllib.request.Request(
        server_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as err:
        raise RuntimeError(f"Failed to connect to audio.cpp server at {server_url}: {err}") from err


def separate_via_audiocpp_api(
    audio_path: Path,
    output_dir: Path,
    server_url: str = DEFAULT_AUDIOCPP_URL,
) -> tuple[Path, Path]:
    """Isolate vocal and instrumental stems using remote or local audio.cpp server."""
    resampled = output_dir / "input_44k.wav"
    ensure_44k_stereo_wav(audio_path, resampled)
    b64_audio = base64.b64encode(resampled.read_bytes()).decode("utf-8")
    payload = {"model": "htdemucs", "request": {"audio_base64": b64_audio}}
    res = _post_json_request(server_url, payload)
    return _decode_and_save_stems(res.get("named_audio_outputs", []), output_dir)


def run_stem_separation(
    audio_path: Path,
    output_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> tuple[Path, Path]:
    """Run stem separation via audio.cpp API if specified, or audio_separator library."""
    if model_name == "audio.cpp" or os.environ.get("USE_AUDIOCPP"):
        url = os.environ.get("AUDIOCPP_URL", DEFAULT_AUDIOCPP_URL)
        return separate_via_audiocpp_api(audio_path, output_dir, server_url=url)

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
