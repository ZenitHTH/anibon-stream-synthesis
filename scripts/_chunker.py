# scripts/_chunker.py
import json, re, os
from pathlib import Path

def _fmt(s: float) -> str:
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

def _clean(transcript: list, mappings: dict) -> list:
    """Apply text correction mappings in-place."""
    for item in transcript:
        text = re.sub(r'\s+', ' ', item['text']).strip()
        for mapping in mappings.get('mappings', []):
            for pat in mapping.get('patterns', []):
                excludes = mapping.get('exclude_if_contains', [])
                if any(re.search(re.escape(ex), text, re.I) for ex in excludes):
                    continue
                text = re.sub(re.escape(pat), mapping['correct'], text, flags=re.I)
        item['text'] = text
    return transcript

def _write_json(path: Path, start_sec: int, end_sec: int, items: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"start_sec": start_sec, "end_sec": end_sec, "items": items},
                  f, ensure_ascii=False, indent=2)

def _write_txt(path: Path, idx: int, start_sec: int, end_sec: int,
               overlap: int, items: list) -> None:
    cutoff = end_sec - overlap
    header = f"CHUNK {idx:02d} | {_fmt(start_sec)}–{_fmt(end_sec)} | cutoff={_fmt(cutoff)}"
    lines = [header] + [f"({i['timestamp']}) {i['text']}" for i in items]
    path.write_text("\n".join(lines), encoding="utf-8")

def run(workspace: Path, block: int = 300, overlap: int = 30,
        fmt: str = "json") -> int:
    """Chunk the cleaned transcript and write files. Returns number of chunks."""
    # Load transcript
    raw = json.loads((workspace / "raw_transcript.json").read_text(encoding="utf-8"))
    from _transcript import _flatten_json3
    transcript = _flatten_json3(raw) if "events" in raw else raw

    # Load mappings
    plugin_root = Path(__file__).parent.parent
    map_path = plugin_root / "resources" / "default_mappings.json"
    mappings = json.loads(map_path.read_text(encoding="utf-8"))
    cleaned = _clean(transcript, mappings)

    if not cleaned:
        return 0

    # Compute chunks
    chunk_dir = workspace / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    total = int(cleaned[-1]['start'] + cleaned[-1].get('duration', 0))
    step = block - overlap
    idx = 0

    for start in range(0, total, step):
        end = start + block
        items = [x for x in cleaned if start <= x['start'] < end]
        if not items:
            continue
        ext = "txt" if fmt == "txt" else "json"
        path = chunk_dir / f"chunk_{idx:02d}.{ext}"
        if fmt == "txt":
            _write_txt(path, idx, start, end, overlap, items)
        else:
            _write_json(path, start, end, items)
        idx += 1

    return idx
