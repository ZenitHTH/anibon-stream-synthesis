from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class AcousticFeatures:
    flatness: float
    rms_energy_db: float
    bass_ratio: float


def _compute_spectral_flatness(spectrum: np.ndarray, eps: float = 1e-10) -> float:
    pos_spectrum = np.maximum(spectrum, eps)
    geometric_mean = float(np.exp(np.mean(np.log(pos_spectrum))))
    arithmetic_mean = float(np.mean(pos_spectrum))
    if arithmetic_mean <= eps:
        return 0.0
    return float(geometric_mean / arithmetic_mean)


def _compute_bass_ratio(fft_mag: np.ndarray, freqs: np.ndarray) -> float:
    total_energy = float(np.sum(fft_mag**2))
    if total_energy <= 1e-10:
        return 0.0
    bass_mask = (freqs >= 20.0) & (freqs <= 250.0)
    bass_energy = float(np.sum(fft_mag[bass_mask] ** 2))
    return float(bass_energy / total_energy)


def _compute_rms_db(signal: np.ndarray, eps: float = 1e-10) -> float:
    rms = float(np.sqrt(np.mean(signal**2)))
    return float(20.0 * np.log10(max(rms, eps)))


def analyze_acoustic_features(signal: np.ndarray, sr: int = 16000) -> AcousticFeatures:
    if signal.ndim > 1:
        signal = np.mean(signal, axis=1)
    n = len(signal)
    if n == 0:
        return AcousticFeatures(flatness=1.0, rms_energy_db=-100.0, bass_ratio=0.0)
    fft_vals = np.fft.rfft(signal)
    fft_mag = np.abs(fft_vals)
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    flatness = _compute_spectral_flatness(fft_mag**2)
    rms_db = _compute_rms_db(signal)
    bass_ratio = _compute_bass_ratio(fft_mag, freqs)
    return AcousticFeatures(flatness=flatness, rms_energy_db=rms_db, bass_ratio=bass_ratio)


def is_music_spectral(flatness: float, threshold: float = 0.010) -> bool:
    return flatness < threshold
