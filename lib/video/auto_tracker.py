"""Spatial grid any-position webcam tracker fallback when fixed presets miss."""
from __future__ import annotations

from collections import deque
from typing import List, Optional, Tuple

from video.motion_types import WEBCAM_BOX_PRESETS, FaceBox

_GRID_N = 8


def _crop_cell(frame: bytes, size: int, cell: Tuple[int, int]) -> bytes:
    """Slice RGB24 bytes for grid cell (gx, gy)."""
    gx, gy = cell
    x0, x1 = (gx * size) // _GRID_N, ((gx + 1) * size) // _GRID_N
    y0, y1 = (gy * size) // _GRID_N, ((gy + 1) * size) // _GRID_N
    return b"".join(frame[(y * size + x0) * 3 : (y * size + x1) * 3] for y in range(y0, y1))


def _cell_activity(frames: List[bytes], size: int, cell: Tuple[int, int]) -> float:
    """Score temporal MAD boosted by spatial contrast for one grid cell."""
    crops = [_crop_cell(f, size, cell) for f in frames]
    n_bytes = len(crops[0]) if crops else 0
    if len(crops) < 2 or n_bytes == 0:
        return 0.0
    mad = sum(
        abs(a - b) for i in range(1, len(crops)) for a, b in zip(crops[i - 1], crops[i])
    ) / ((len(crops) - 1) * n_bytes * 255.0)
    mean_v = sum(crops[-1]) / n_bytes
    cont = sum(abs(p - mean_v) for p in crops[-1]) / (n_bytes * 255.0)
    return mad * (1.0 + 2.0 * cont)


def _bfs_component(active: List[List[bool]], start: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Collect 4-connected active cells starting from (gx, gy)."""
    sx, sy = start
    active[sy][sx] = False
    q: deque[Tuple[int, int]] = deque([(sx, sy)])
    comp: List[Tuple[int, int]] = []
    while q:
        cx, cy = q.popleft()
        comp.append((cx, cy))
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < _GRID_N and 0 <= ny < _GRID_N and active[ny][nx]:
                active[ny][nx] = False
                q.append((nx, ny))
    return comp


def _best_component(grid: List[List[float]], thresh: float) -> List[Tuple[int, int]]:
    """Find highest-scoring connected cluster of active grid cells."""
    active = [[v >= thresh for v in row] for row in grid]
    best: List[Tuple[int, int]] = []
    best_score = 0.0
    for gy in range(_GRID_N):
        for gx in range(_GRID_N):
            if not active[gy][gx]:
                continue
            comp = _bfs_component(active, (gx, gy))
            score = sum(grid[y][x] for x, y in comp)
            if score > best_score:
                best, best_score = comp, score
    return best


def _classify_component(comp: List[Tuple[int, int]]) -> Tuple[str, Optional[FaceBox]]:
    """Convert winning grid cluster into ('auto-tracked'|'fullscreen', FaceBox)."""
    if not comp:
        return ("none", None)
    xs, ys = [c[0] for c in comp], [c[1] for c in comp]
    x0, x1 = min(xs) / _GRID_N, (max(xs) + 1) / _GRID_N
    y0, y1 = min(ys) / _GRID_N, (max(ys) + 1) / _GRID_N
    box = FaceBox(x0, y0, x1 - x0, y1 - y0, "auto-tracked").clamped()
    coverage = len(comp) / (_GRID_N * _GRID_N)
    is_wide_center = box.w >= 0.35 and box.h >= 0.50 and 0.15 <= box.x <= 0.45
    if coverage >= 0.45 or is_wide_center:
        return ("fullscreen", WEBCAM_BOX_PRESETS["fullscreen"])
    return ("auto-tracked", box)


def box_iou(box_a: Optional[FaceBox], box_b: Optional[FaceBox]) -> float:
    """Compute intersection-over-union between two normalized FaceBox regions."""
    if box_a is None or box_b is None:
        return 0.0
    ix0, iy0 = max(box_a.x, box_b.x), max(box_a.y, box_b.y)
    ix1, iy1 = min(box_a.x + box_a.w, box_b.x + box_b.w), min(box_a.y + box_a.h, box_b.y + box_b.h)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = box_a.w * box_a.h + box_b.w * box_b.h - inter
    return inter / union if union > 0.0 else 0.0


def track_webcam_any_position(
    frames: List[bytes], sample_size: int = 48
) -> Tuple[str, Optional[FaceBox]]:
    """Scan spatial grid across [0..1]x[0..1] for coherent webcam motion clusters."""
    if len(frames) < 2:
        return ("none", None)
    grid = [[_cell_activity(frames, sample_size, (gx, gy)) for gx in range(_GRID_N)] for gy in range(_GRID_N)]
    max_sc = max(v for row in grid for v in row)
    if max_sc < 0.008:
        return ("none", None)
    best = _best_component(grid, max(0.008, 0.35 * max_sc))
    return _classify_component(best)
