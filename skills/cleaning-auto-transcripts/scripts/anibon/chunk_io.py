"""Chunk IO: load/save chunk files in JSON, XML, TXT formats.

Consumers (before extraction):
  load_chunks     — anibon_analyzer_core.py:18, detect_signals.py:116 (2 impls)
  write_chunk_*   — _chunker.py:21-39
  chunk_sort_key  — detect_signals.py:108
"""
import json
import glob
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from anibon.time import fmt_ts


# ── Load ───────────────────────────────────────────────────────────────────


def load_chunks(path: str | Path):
    """Yield (name, start_sec, full_text) for each chunk.

    Supports:
    - Directory of JSON files (preferred) or XML files
    - Single JSON or XML file
    """
    p = Path(path)
    if p.is_file():
        yield _load_chunk_file(p)
        return

    # Prefer JSON; fall back to XML
    candidates = sorted(p.glob("chunk_*.json"), key=chunk_sort_key)
    fmt = "json"
    if not candidates:
        candidates = sorted(p.glob("chunk_*.xml"), key=chunk_sort_key)
        fmt = "xml"

    loader = _load_chunk_xml if fmt == "xml" else _load_chunk_json
    for f in candidates:
        yield loader(f)


def load_chunks_list(workspace_dir: str) -> list[dict]:
    """Load all chunks into a flat list of dicts (anibon_analyzer style).

    Each dict has keys: start_sec, end_sec, items.
    """
    chunks_dir = os.path.join(workspace_dir, "chunks")
    if not os.path.exists(chunks_dir):
        raise FileNotFoundError(f"Directory not found: {chunks_dir}")

    chunk_files = sorted(
        glob.glob(os.path.join(chunks_dir, "chunk_*.json")),
        key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]),
    )
    is_xml = False
    if not chunk_files:
        chunk_files = sorted(
            glob.glob(os.path.join(chunks_dir, "chunk_*.xml")),
            key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]),
        )
        is_xml = True

    if not chunk_files:
        raise FileNotFoundError(f"No chunk files found in: {chunks_dir}")

    chunks = []
    if is_xml:
        for fpath in chunk_files:
            tree = ET.parse(fpath)
            root = tree.getroot()
            chunk_data = {
                "start_sec": int(root.attrib.get("start_sec", 0)),
                "end_sec": int(root.attrib.get("end_sec", 0)),
                "items": [],
            }
            for item in root.findall("item"):
                item_data = {
                    "start": float(item.attrib.get("start", 0.0)),
                    "timestamp": item.attrib.get("timestamp", ""),
                    "text": item.text or "",
                }
                if "image" in item.attrib:
                    item_data["image"] = item.attrib["image"]
                chunk_data["items"].append(item_data)
            chunks.append(chunk_data)
    else:
        for fpath in chunk_files:
            with open(fpath, encoding="utf-8") as f:
                chunks.append(json.load(f))
    return chunks


def _load_chunk_json(path: Path):
    """Load a single JSON chunk. Returns (name, start_sec, full_text)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    texts = [it.get("text", "").strip() for it in data.get("items", []) if it.get("text")]
    return path.stem, data.get("start_sec", 0), " ".join(texts)


def _load_chunk_xml(path: Path):
    """Load a single XML chunk. Returns (name, start_sec, full_text)."""
    tree = ET.parse(path)
    root = tree.getroot()
    texts = []
    for item in root.iter("item"):
        t = (item.text or "").strip()
        if t:
            texts.append(t)
    start_sec = int(root.get("start_sec", 0))
    return path.stem, start_sec, " ".join(texts)


def _load_chunk_file(path: Path):
    """Load a single chunk file, detecting format by extension."""
    if path.suffix == ".xml":
        return _load_chunk_xml(path)
    return _load_chunk_json(path)


def chunk_sort_key(f: Path) -> int:
    """Extract chunk index from filename (chunk_03.json → 3)."""
    try:
        return int(f.stem.split("_")[-1])
    except (ValueError, IndexError):
        return 0


# ── Write ──────────────────────────────────────────────────────────────────


def write_chunk_json(path: Path, start_sec: int, end_sec: int, items: list) -> None:
    """Write a chunk in JSON format."""
    path.write_text(
        json.dumps(
            {"start_sec": start_sec, "end_sec": end_sec, "items": items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_chunk_xml(path: Path, idx: int, start_sec: int, end_sec: int, items: list) -> None:
    """Write a chunk in XML format (Claude-style)."""
    lines = [f'<chunk id="{idx}" start_sec="{start_sec}" end_sec="{end_sec}">']
    for i in items:
        text = i["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'  <item start="{i["start"]}" timestamp="{i["timestamp"]}">{text}</item>')
    lines.append("</chunk>")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_chunk_txt(path: Path, idx: int, start_sec: int, end_sec: int,
                    overlap: int, items: list) -> None:
    """Write a chunk in plain-text format."""
    cutoff = end_sec - overlap
    header = f"CHUNK {idx:02d} | {fmt_ts(start_sec)}–{fmt_ts(end_sec)} | cutoff={fmt_ts(cutoff)}"
    lines = [header] + [f"({i['timestamp']}) {i['text']}" for i in items]
    path.write_text("\n".join(lines), encoding="utf-8")
