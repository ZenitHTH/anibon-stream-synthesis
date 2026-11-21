"""Pack sequential cropped webcam frames into a tiled storyboard grid sheet."""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path
from typing import Optional, Sequence, Tuple

_PANEL_COUNT_RE = re.compile(r";\s*(\d+)\s+panels:")


def grid_dims(count: int) -> Tuple[int, int]:
    """Choose compact (cols, rows) storyboard layout for 1..9 frames."""
    if count <= 1:
        return (1, 1)
    if count == 2:
        return (2, 1)
    if count <= 4:
        return (2, 2)
    if count <= 6:
        return (3, 2)
    return (3, 3)


def _render_grid_jpeg(paths: Sequence[Path], out_path: Path, dims: Tuple[int, int]) -> bool:
    """Assemble image inputs (normalizing mixed aspect ratios to 320x320) into a JPEG grid."""
    cols, rows = dims
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for p in paths:
        cmd.extend(["-i", str(p)])
    norm = "".join(
        f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}];"
        for i in range(len(paths))
    )
    streams = "".join(f"[v{i}]" for i in range(len(paths)))
    vf = f"{norm}{streams}concat=n={len(paths)}:v=1:a=0,tile={cols}x{rows}:padding=6:margin=6:color=black"
    cmd.extend(["-filter_complex", vf, "-frames:v", "1", "-q:v", "2", str(out_path)])
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 100


def _build_legend(frames: Sequence[Tuple[str, Path, str, str]], dims: Tuple[int, int]) -> str:
    """Build left-to-right top-to-bottom panel timestamp and role legend."""
    cols, rows = dims
    parts = [f"[{i}]={ts} {lbl}" for i, (ts, _, _, lbl) in enumerate(frames, start=1)]
    return f"WEBCAM STORYBOARD ({cols}x{rows} grid, left-to-right top-to-bottom; {len(frames)} panels: {', '.join(parts)})"


def assemble_webcam_storyboard(
    frames: Sequence[Tuple[str, Path, str, str]],
    out_path: Path,
) -> Optional[Tuple[str, Path, str, str]]:
    """Pack multiple webcam frames into one tiled storyboard JPEG tuple, or None on error."""
    valid = [f for f in frames if Path(f[1]).is_file()][:9]
    if not valid:
        return None
    dims = grid_dims(len(valid))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not _render_grid_jpeg([Path(f[1]) for f in valid], out_path, dims):
        return None
    b64 = base64.b64encode(out_path.read_bytes()).decode("ascii")
    ts_span = valid[0][0] if len(valid) == 1 else f"{valid[0][0]}-{valid[-1][0]}"
    return (ts_span, out_path, b64, _build_legend(valid, dims))


def count_packed_panels(frames: Sequence[tuple]) -> int:
    """Return total individual webcam panels represented across frame or sheet tuples."""
    total = 0
    for item in frames:
        lbl = str(item[3]) if len(item) > 3 else ""
        m = _PANEL_COUNT_RE.search(lbl)
        total += int(m.group(1)) if m else 1
    return total


def format_webcam_count(frames: Sequence[tuple]) -> str:
    """Format concise count-only webcam string (e.g. '0', '1', or '1(6f)')."""
    if not frames:
        return "0"
    panels = count_packed_panels(frames)
    if panels > len(frames):
        return f"{len(frames)}({panels}f)"
    return str(len(frames))


def pack_exported_webcam_storyboard(
    wb_exported: dict, out_path: Path
) -> list:
    """Pack exported webcam frame dicts into a tiled storyboard sheet or single-frame tuples."""
    wb = [
        (f["ts"], Path(f["path"]), f["b64"], f"WEBCAM ONLY ({f.get('role') or 'frame'})")
        for f in (wb_exported.get("frames") or ())
    ]
    if len(wb) >= 2:
        sheet = assemble_webcam_storyboard(wb, out_path)
        if sheet is not None:
            return [sheet]
    return wb


__all__ = [
    "assemble_webcam_storyboard",
    "count_packed_panels",
    "format_webcam_count",
    "grid_dims",
    "pack_exported_webcam_storyboard",
]
