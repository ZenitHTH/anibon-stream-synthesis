from __future__ import annotations

from pathlib import Path
import numpy as np


def _align_and_compute_gain(mixed: np.ndarray, ref_slice: np.ndarray) -> float:
    ref_energy = float(np.sum(ref_slice**2))
    if ref_energy <= 1e-10:
        return 0.0
    return float(np.sum(mixed * ref_slice) / ref_energy)


def _find_best_lag(mixed: np.ndarray, ref: np.ndarray) -> int:
    try:
        from scipy.signal import correlate
        corr = correlate(mixed, ref, mode="full", method="fft")
    except ImportError:
        corr = np.correlate(mixed, ref, mode="full")
    return int(np.argmax(corr) - (len(ref) - 1))


def _extract_aligned_slice(ref: np.ndarray, lag: int, length: int) -> np.ndarray:
    aligned = np.zeros(length, dtype=np.float32)
    start_dst = max(0, lag)
    end_dst = min(length, lag + len(ref))
    start_src = max(0, -lag)
    end_src = start_src + (end_dst - start_dst)
    if end_dst > start_dst and end_src <= len(ref):
        aligned[start_dst:end_dst] = ref[start_src:end_src]
    return aligned


def subtract_reference_signal(mixed: np.ndarray, ref: np.ndarray) -> np.ndarray:
    if len(mixed) == 0 or len(ref) == 0:
        return mixed.copy()
    lag = _find_best_lag(mixed, ref)
    ref_slice = _extract_aligned_slice(ref, lag, len(mixed))
    gain = _align_and_compute_gain(mixed, ref_slice)
    subtracted = mixed - (gain * ref_slice)
    return np.clip(subtracted, -1.0, 1.0)


def process_subtraction_files(mixed_path: str | Path, ref_path: str | Path, out_path: str | Path) -> None:
    import soundfile as sf

    mixed, sr_mixed = sf.read(str(mixed_path), dtype="float32")
    ref, sr_ref = sf.read(str(ref_path), dtype="float32")
    if mixed.ndim > 1:
        mixed = np.mean(mixed, axis=1)
    if ref.ndim > 1:
        ref = np.mean(ref, axis=1)
    cleaned = subtract_reference_signal(mixed, ref)
    sf.write(str(out_path), cleaned, sr_mixed)
