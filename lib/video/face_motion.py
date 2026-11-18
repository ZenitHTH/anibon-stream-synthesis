"""Dual-Box F+W ffmpeg rawvideo extractor and 256x256 VLM keyframe strip exporter."""
from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from common.time import fmt_ts
from video.face_motion_metrics import score_motion_series
from video.motion_types import FaceBox, FaceMotionSample, KeyframePick, LayoutSegment, WindowBounds
from video.obs_layout import detect_layout_cuts, split_around_cuts


@dataclass(frozen=True)
class FrameExportSpec:
    """Configuration for exporting 256x256 VLM keyframe JPEGs and strip."""

    keyframes: Tuple[KeyframePick, ...]
    box: Optional[FaceBox]
    out_dir: Path
    prefix: str = "webcam"
    out_size: int = 256


def _is_remote(src: str) -> bool:
    return src.startswith(("http://", "https://"))


def _build_raw_cmd(src: str, box: Optional[FaceBox], bounds: WindowBounds) -> List[str]:
    """Construct ffmpeg rawvideo RGB24 extraction command."""
    filters = [f"fps={bounds.fps:.4f}"]
    crop = box.to_ffmpeg_crop() if box is not None else None
    if crop:
        filters.append(crop)
    filters.extend([f"scale={bounds.sample_size}:{bounds.sample_size}:flags=area", "format=rgb24"])
    return ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, bounds.start_sec):.3f}", "-i", src,
            "-t", f"{max(0.5, bounds.end_sec - bounds.start_sec):.3f}", "-vf", ",".join(filters),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]


def extract_raw_rgb_frames(
    source: Path | str, box: Optional[FaceBox], bounds: WindowBounds
) -> Tuple[List[bytes], List[float]]:
    """Extract cropped raw RGB24 frames via ffmpeg stdout pipe."""
    src = str(source)
    if not _is_remote(src) and not Path(src).is_file():
        raise FileNotFoundError(f"Video not found: {src}")
    if bounds.fps <= 0:
        raise ValueError(f"fps must be positive, got {bounds.fps}")
    res = subprocess.run(_build_raw_cmd(src, box, bounds), capture_output=True, timeout=90)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg rawvideo failed: {res.stderr.decode('utf-8', errors='replace').strip()}")
    fb = bounds.sample_size * bounds.sample_size * 3
    n = len(res.stdout) // fb
    return ([res.stdout[i * fb : (i + 1) * fb] for i in range(n)], [bounds.start_sec + i / bounds.fps for i in range(n)])


def _clamp_bounds(bounds: WindowBounds, layout: LayoutSegment) -> WindowBounds:
    """Narrow extraction bounds to layout.clean_start_sec/clean_end_sec when valid."""
    lo = max(bounds.start_sec, layout.clean_start_sec) if layout.clean_start_sec is not None else bounds.start_sec
    hi = min(bounds.end_sec, layout.clean_end_sec) if layout.clean_end_sec is not None else bounds.end_sec
    if (hi - lo) >= 1.0:
        return WindowBounds(lo, hi, bounds.fps, bounds.sample_size)
    return bounds


def extract_dual_motion_series(
    source: Path | str, bounds: WindowBounds, layout: LayoutSegment
) -> Tuple[List[FaceMotionSample], List[FaceMotionSample], Tuple[float, ...]]:
    """Extract cut-split Dual-Box (F tight-face, W full-webcam) motion series."""
    if layout.webcam_box is None:
        return ([], [], ())
    eff = _clamp_bounds(bounds, layout)
    w_frames, _ = extract_raw_rgb_frames(source, layout.webcam_box, eff)
    is_full = layout.webcam_box.to_ffmpeg_crop() is None
    full_frames = w_frames if is_full else extract_raw_rgb_frames(source, None, eff)[0]
    cuts = detect_layout_cuts(full_frames, fps=eff.fps)
    cut_secs = tuple(sorted({round(eff.start_sec + c / eff.fps, 3) for c in cuts} | set(layout.cut_secs)))
    lo, hi = split_around_cuts(len(w_frames), cuts, fps=eff.fps)
    f_box = layout.face_box or layout.webcam_box.derive_tight_face()
    f_frames, _ = extract_raw_rgb_frames(source, f_box, eff)
    clean_offset = eff.start_sec + lo / eff.fps
    f_samples, _ = score_motion_series(f_frames[lo:hi], fps=eff.fps, abs_offset_sec=clean_offset)
    w_samples, _ = score_motion_series(w_frames[lo:hi], fps=eff.fps, abs_offset_sec=clean_offset)
    return (f_samples, w_samples, cut_secs)


def _export_vf(box: Optional[FaceBox], out_size: int) -> str:
    """Build ffmpeg scale+pad filter string (no drawtext)."""
    parts = [box.to_ffmpeg_crop()] if (box is not None and box.to_ffmpeg_crop()) else []
    parts.append(f"scale={out_size}:{out_size}:force_original_aspect_ratio=decrease,"
                 f"pad={out_size}:{out_size}:(ow-iw)/2:(oh-ih)/2:color=black")
    return ",".join(parts)


def _render_single_jpeg(src_vf: Tuple[str, str], out_jpg: Path, abs_sec: float) -> bool:
    """Render one keyframe JPEG at abs_sec via ffmpeg."""
    src, vf = src_vf
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, abs_sec):.3f}", "-i", src,
           "-vf", vf, "-frames:v", "1", "-q:v", "2", str(out_jpg)]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return res.returncode == 0 and out_jpg.is_file()


def _hstack_strip(frame_paths: List[Path], out_dir: Path, prefix: str) -> Optional[Path]:
    """Assemble horizontal VLM strip JPEG from exported keyframe paths."""
    if not frame_paths:
        return None
    strip = out_dir / f"strip_{prefix}.jpg"
    if len(frame_paths) == 1:
        strip.write_bytes(frame_paths[0].read_bytes())
        return strip
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for p in frame_paths:
        cmd.extend(["-i", str(p)])
    cmd.extend(["-filter_complex", f"hstack=inputs={len(frame_paths)}", "-q:v", "2", str(strip)])
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return strip if (res.returncode == 0 and strip.is_file()) else None


def export_vlm_keyframes(source: Path | str, spec: FrameExportSpec) -> Dict[str, object]:
    """Export uncropped W keyframe JPEGs and hstack strip for VLM inspection."""
    spec.out_dir.mkdir(parents=True, exist_ok=True)
    vf = _export_vf(spec.box, spec.out_size)
    exported, paths = [], []
    for idx, kf in enumerate(spec.keyframes, start=1):
        out_jpg = spec.out_dir / f"{spec.prefix}_{idx:02d}_{kf.role}_{kf.rel_sec:.1f}s.jpg"
        if not _render_single_jpeg((str(source), vf), out_jpg, kf.abs_sec):
            continue
        paths.append(out_jpg)
        exported.append({
            "index": idx, "role": kf.role, "rel_sec": kf.rel_sec, "abs_sec": kf.abs_sec,
            "ts": fmt_ts(kf.abs_sec), "path": str(out_jpg),
            "b64": base64.b64encode(out_jpg.read_bytes()).decode("ascii"),
        })
    strip = _hstack_strip(paths, spec.out_dir, spec.prefix)
    return {"frames": exported, "strip_path": str(strip) if strip else None}
