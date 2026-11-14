"""IO loaders for speaker transcript chunks (.txt, .json, .xml, .jsonl.gz)."""
from __future__ import annotations

import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


def _read_json_chunk(raw: str) -> str:
    """Extract dialogue lines from JSON chunk dicts or segment lists."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict):
        items = data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        return raw
    if not isinstance(items, list):
        return raw
    return "\n".join(
        str(it.get("text") or "").strip()
        for it in items
        if isinstance(it, dict) and it.get("text")
    )


def _read_xml_chunk(chunk_path: Path) -> Optional[str]:
    """Extract text from any nested <item> tags inside an XML chunk."""
    try:
        root = ET.parse(chunk_path).getroot()
        return "\n".join((el.text or "").strip() for el in root.iter("item") if el.text)
    except ET.ParseError:
        return None


def read_chunk_text(chunk_path: Path) -> str:
    """Read raw dialogue text from .txt, .json, or .xml chunk files."""
    if chunk_path.suffix == ".json":
        return _read_json_chunk(chunk_path.read_text(encoding="utf-8", errors="ignore"))
    if chunk_path.suffix == ".xml":
        parsed = _read_xml_chunk(chunk_path)
        if parsed is not None:
            return parsed
    return chunk_path.read_text(encoding="utf-8", errors="ignore")


def resolve_speaker_chunk_path(chunks_dir: Optional[Path], chunk_id: str) -> Optional[Path]:
    """Locate chunks/<chunk_id>.(txt|json|xml) (or zero-padded variant) if present."""
    if not chunks_dir or not chunks_dir.is_dir():
        return None
    m = re.search(r"(\d+)$", chunk_id)
    stems = [chunk_id] + ([f"chunk_{int(m.group(1)):02d}"] if m else [])
    for stem in stems:
        for ext in (".txt", ".json", ".xml"):
            cand = chunks_dir / f"{stem}{ext}"
            if cand.exists():
                return cand
    return None


def _safe_start(item: dict) -> float:
    """Parse segment start seconds defensively from arbitrary JSON values."""
    try:
        return float(item.get("start") or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_gz_items(gz_path: Path) -> List[dict]:
    """Load valid dict records from a gzipped JSONL transcript archive."""
    items: List[dict] = []
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                items.append(obj)
    return items


def slice_jsonl_gz_chunks(
    gz_path: Path, step_sec: int = 270, win_sec: int = 300
) -> Dict[str, str]:
    """Slice an archived transcript_<vid>.jsonl.gz into overlapping time windows."""
    items = _parse_gz_items(gz_path)
    if not items:
        return {}
    max_start = max(_safe_start(it) for it in items)
    n_chunks = (int(max_start) // step_sec) + 1
    out: Dict[str, str] = {}
    for idx in range(n_chunks):
        st, en = idx * step_sec, idx * step_sec + win_sec
        out[f"chunk_{idx:02d}"] = "\n".join(
            str(it.get("text") or "") for it in items if st <= _safe_start(it) < en
        )
    return out
