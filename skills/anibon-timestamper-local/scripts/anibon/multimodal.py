"""anibon/multimodal.py — Storyboard keyframe extraction and multi-image chunk analysis."""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from PIL import Image

SYSTEM_PROMPT = """\
You are an expert livestream editor for Thai livestreams by Pu Boat (Anibon Official).
CRITICAL INSTRUCTION: Keep your internal thinking under 2 sentences. \
Do NOT list items or transcribe text in your thinking. \
Proceed immediately to outputting the final decision."""


def unpack_mhtml_storyboard(mhtml_path: Path, out_dir: Path) -> int:
    """Unpack MHTML multipart storyboard slides into clean JPEG files."""
    mhtml_path = Path(mhtml_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not mhtml_path.exists():
        return 0

    with open(mhtml_path, "rb") as f:
        data = f.read()

    m = re.search(b"--[a-f0-9]{32}", data)
    if not m:
        return 0
    boundary = m.group(0)

    parts = data.split(boundary)
    count = 0
    for p in parts:
        if b"image/jpeg" in p:
            header_end = p.find(b"\r\n\r\n")
            if header_end != -1:
                body = p[header_end + 4 :]
            else:
                header_end = p.find(b"\n\n")
                body = p[header_end + 2 :]
            body = body.rstrip(b"\r\n-")
            if body:
                count += 1
                slide_file = out_dir / f"slide_{count:04d}.jpg"
                with open(slide_file, "wb") as sf:
                    sf.write(body)

    return count


def prepare_storyboard_slides(workspace: Path) -> Optional[Path]:
    """Find or unpack storyboard slide sheets in workspace."""
    workspace = Path(workspace)
    frames_dir = workspace / "frames"

    # 1. Existing clean slides
    for d in [frames_dir / "slides_clean", frames_dir / "slides_sb0", frames_dir / "slides"]:
        if d.is_dir() and len(list(d.glob("slide_*.jpg"))) > 10:
            return d

    # 2. Check for MHTML storyboard to unpack
    for m in [frames_dir / "sb0.mhtml", frames_dir / "storyboard.mhtml", frames_dir / "sb1.mhtml"]:
        if m.is_file():
            clean_dir = frames_dir / "slides_clean"
            count = unpack_mhtml_storyboard(m, clean_dir)
            if count > 0:
                return clean_dir

    return None


def sec_to_ts(sec: int) -> str:
    """Format seconds into HH:MM:SS."""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def sample_chunk_keyframes(
    start_sec: int,
    end_sec: int,
    slides_dir: Path,
    out_dir: Path,
    num_frames: int = 3,
    sec_per_slide: float = 88.94,
    sec_per_tile: float = 9.88,
) -> List[Tuple[str, Path, str]]:
    """Sample keyframes across chunk bounds and crop 320x180 tiles.

    Returns:
        List of tuples: (timestamp_string, tile_file_path, base64_encoded_image)
    """
    slides_dir = Path(slides_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    available_slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not available_slides:
        return []

    max_slide_idx = len(available_slides) - 1

    dur = max(1, end_sec - start_sec)
    if num_frames == 1:
        target_secs = [(start_sec + end_sec) // 2]
    elif num_frames == 2:
        target_secs = [start_sec + 25, end_sec - 25]
    else:
        target_secs = [
            start_sec + 25,
            (start_sec + end_sec) // 2,
            max(start_sec + 30, end_sec - 25),
        ]

    results = []
    for sec in target_secs:
        ts_str = sec_to_ts(sec)
        out_tile = out_dir / f"tile_{sec:06d}.jpg"

        if not out_tile.exists():
            slide_idx = min(max_slide_idx, max(0, int(sec / sec_per_slide)))
            slide_file = slides_dir / f"slide_{slide_idx + 1:04d}.jpg"
            if not slide_file.exists():
                slide_file = available_slides[min(slide_idx, max_slide_idx)]

            offset = sec - slide_idx * sec_per_slide
            tile_idx = min(8, max(0, int(offset / sec_per_tile)))
            row, col = tile_idx // 3, tile_idx % 3

            try:
                im = Image.open(slide_file)
                tile = im.crop((col * 320, row * 180, (col + 1) * 320, (row + 1) * 180))
                tile.save(out_tile, quality=95)
            except Exception as e:
                print(f"[multimodal] tile crop error at {sec}s: {e}", file=sys.stderr)
                continue

        try:
            with open(out_tile, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            results.append((ts_str, out_tile, b64))
        except Exception:
            pass

    return results


def build_multimodal_content(prompt_text: str, keyframes: List[Tuple[str, Path, str]]) -> List[dict]:
    """Construct standard OpenAI multi-modal messages content list."""
    content: List[dict] = [{"type": "text", "text": prompt_text}]
    for ts_str, _, b64_data in keyframes:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
        })
    return content


def call_multimodal(
    endpoint: str,
    model: str,
    content_list: List[dict],
    max_tokens: int = 4096,
    temperature: float = 0.1,
    timeout: int = 120,
    api_key: Optional[str] = None,
) -> str:
    """Send multimodal payload to OpenAI-compatible VLM endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content_list},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    api_key = (
        api_key
        or os.environ.get("TOKENME_API_KEY")
        or os.environ.get("LM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""
