"""Pre-chunk storyboard screen tile preparation for Pass 1 grounding."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from common import config as _cfg
from common.log import log_warn
from process.multimodal import sample_chunk_keyframes

_TILES_SUBDIR = ("frames", "chunk_tiles")


def _chunk_window(chunk: dict) -> tuple[int, int]:
    """Return chunk (start, end) seconds, preferring header bounds over items."""
    start, end = int(chunk.get("start_sec", 0) or 0), int(chunk.get("end_sec", 0) or 0)
    if end > start:
        return start, end
    items = chunk.get("items") or []
    lo = int(float(items[0].get("start", 0))) if items else 0
    hi = int(float(items[-1].get("start", lo))) + 5 if items else lo + 150
    return lo, hi


def _sample_tiles(chunk: dict, slides_dir: Path, workspace: Path) -> list:
    """Sample scene-deduped storyboard tiles across the whole chunk window."""
    start, end = _chunk_window(chunk)
    return sample_chunk_keyframes(
        start, end, slides_dir, workspace.joinpath(*_TILES_SUBDIR),
        items=chunk.get("items") or [], num_frames=_cfg.MAX_CHUNK_FRAMES,
        scene_dedup=True, eval_batch_size=_cfg.EVAL_BATCH_SIZE,
    )


def prep_chunk_storyboard(chunk: dict, slides_dir: Optional[Path], workspace: Path) -> List[dict]:
    """Cache storyboard screen tiles for one chunk; returns [{ts, path}] (empty without slides)."""
    if not slides_dir or not Path(slides_dir).is_dir():
        return []
    try:
        frames = _sample_tiles(chunk, Path(slides_dir), Path(workspace))
    except Exception as ex:
        log_warn("enrich", f"storyboard prep failed for chunk {chunk.get('_idx')}: {ex}")
        return []
    return [{"ts": f[0], "path": str(f[1])} for f in frames]


__all__ = ["prep_chunk_storyboard"]
