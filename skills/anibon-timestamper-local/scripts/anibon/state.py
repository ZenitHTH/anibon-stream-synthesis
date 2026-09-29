"""State persistence, chunk file loading, and multimodal context utilities.

Handles:
- Session checkpoint saving and resuming (anibon_timestamper_state.json)
- Discovery and loading of transcript chunk files (.txt, .json)
- Loading LiveChat highlights, visual activity, and 555 meme pulse metrics
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from anibon.time import parse_ts
from signal_detector import normalize_transcript


def load_state(workspace: Path) -> dict:
    """Load session state from workspace/anibon_timestamper_state.json."""
    state_path = workspace / "anibon_timestamper_state.json"
    if state_path.exists():
        try:
            with open(state_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(workspace: Path, state: dict) -> None:
    """Save session state to workspace/anibon_timestamper_state.json with timestamp."""
    state_path = workspace / "anibon_timestamper_state.json"
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] Failed to save state: {e}")


def load_chunk_livechat(workspace: Path, chunk_idx: str) -> str:
    """Return top chat snippet for this chunk if available."""
    lc_file = workspace / "livechat" / f"livechat_{chunk_idx}.txt"
    if lc_file.exists():
        try:
            lines = [l.strip() for l in lc_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                return "\n".join(lines[:6])
        except Exception:
            pass
    return ""


def load_chunk_activity(workspace: Path, chunk_idx: str) -> str:
    """Return visual activity summary (game on screen, webcam state) if available."""
    act_file = workspace / "activity" / f"activity_{chunk_idx}.txt"
    if act_file.exists():
        try:
            return act_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def load_chunk_mood(workspace: Path, chunk_idx: str) -> str:
    """Return 555 laugh/meme pulse verdict if available."""
    mood_file = workspace / "mood_555.json"
    if mood_file.exists():
        try:
            with open(mood_file, encoding="utf-8") as f:
                data = json.load(f)
                info = data.get(chunk_idx)
                if info and info.get("verdict") and info.get("verdict") != "QUIET":
                    tone_desc = info.get("tone", {}).get("tone", "")
                    return f"Chat Mood: {info.get('verdict')} ({tone_desc})"
        except Exception:
            pass
    return ""


def discover_chunks(workspace: Path) -> List[Path]:
    """Find and sort all chunk transcript files in workspace/chunks/.

    Prioritizes .txt files (formatted chunks with explicit time ranges).
    Falls back to .json files only if no .txt files exist. Never mixes both.
    """
    chunks_dir = workspace / "chunks"
    if not chunks_dir.exists():
        raise FileNotFoundError(f"No chunks dir: {chunks_dir}")

    txt_files = list(chunks_dir.glob("chunk_*.txt"))
    if txt_files:
        files = sorted(
            txt_files,
            key=lambda f: int(re.search(r"chunk_(\d+)", f.stem).group(1)),
        )
    else:
        json_files = list(chunks_dir.glob("chunk_*.json"))
        files = sorted(
            json_files,
            key=lambda f: int(re.search(r"chunk_(\d+)", f.stem).group(1)),
        )

    if not files:
        raise FileNotFoundError(f"No chunk files in: {chunks_dir}")
    return files


def load_chunk_file(path: Path, mappings: Optional[list] = None) -> dict:
    """Load and normalize transcript items from a single chunk file."""
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for it in data.get("items", []):
            if it.get("text"):
                it["text"] = normalize_transcript(it["text"], mappings or [])
        return data

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    items = []
    start_sec = 0
    end_sec = 0
    cutoff = 0

    if lines:
        header = lines[0]
        m = re.search(r"(\d{2}:\d{2}:\d{2})[–-](\d{2}:\d{2}:\d{2})", header)
        if m:
            start_sec = parse_ts(m.group(1))
            end_sec = parse_ts(m.group(2))
        mc = re.search(r"cutoff=(\d{2}:\d{2}:\d{2})", header)
        if mc:
            cutoff = parse_ts(mc.group(1)) if mc else end_sec

        for line in lines[1:]:
            lm = re.match(r"\((\d{2}:\d{2}:\d{2})\)\s+(.*)", line)
            if lm:
                ts = lm.group(1)
                sec = parse_ts(ts)
                if cutoff and sec > cutoff:
                    continue
                raw_text = lm.group(2)
                clean_text = normalize_transcript(raw_text, mappings or [])
                items.append({"start": float(sec), "timestamp": ts, "text": clean_text})

    return {"start_sec": start_sec, "end_sec": end_sec, "items": items}
