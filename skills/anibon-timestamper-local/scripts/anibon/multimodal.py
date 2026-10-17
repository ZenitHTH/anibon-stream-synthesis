"""anibon/multimodal.py — Storyboard keyframe extraction and multi-image chunk analysis."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from anibon.config import (
    CHUNK_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MULTIMODAL_TIMEOUT_SEC,
)

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    from anibon.ytdlp import download_storyboard
except ImportError:
    download_storyboard = None



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
        if b"image/jpeg" in p or b"image/webp" in p:
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


def prepare_storyboard_slides(workspace: Path, video_url: Optional[str] = None) -> Optional[Path]:
    """Find or unpack storyboard slide sheets in workspace.

    If no slides exist and video_url or .video_url is present, automatically
    downloads storyboard images via yt-dlp before unpacking.
    """
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

    # 3. Auto-download storyboard if URL is available
    resolved_url = video_url
    if not resolved_url and (workspace / ".video_url").is_file():
        try:
            resolved_url = (workspace / ".video_url").read_text(encoding="utf-8").strip()
        except Exception:
            resolved_url = None

    if resolved_url and download_storyboard is not None:
        downloaded = download_storyboard(resolved_url, workspace)
        clean_dir = frames_dir / "slides_clean"
        if clean_dir.is_dir() and len(list(clean_dir.glob("slide_*.jpg"))) > 10:
            return clean_dir

        if downloaded and Path(downloaded).is_file():
            count = unpack_mhtml_storyboard(Path(downloaded), clean_dir)
            if count > 0:
                return clean_dir


    return None



def sec_to_ts(sec: int) -> str:
    """Format seconds into HH:MM:SS."""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


INCOMPLETE_CONTEXT_CUES = (
    "ดูอันนี้", "ดูนี่", "อันนี้", "ตัวนี้", "แบบนี้", "หน้านี้", "รูปนี้", "คลิปนี้",
    "ภาพนี้", "หน้าตา", "เนี่ยดูดิ", "เปิดดู", "ในจอ", "ตรงนี้", "จุดนี้", "นี่ไง",
    "ดูคลิป", "ตัวละครนี้", "สกินนี้", "การ์ดนี้", "เกมนี้", "ใครเนี่ย", "อะไรเนี่ย",
    "โอ้โห", "เฮ้ย", "โห", "ดูดิ", "เนี่ย", "[?]"
)


def select_target_seconds(
    start_sec: int,
    end_sec: int,
    min_frames: int = 3,
    max_frames: int = 5,
    items: Optional[List[dict]] = None,
    num_frames: Optional[int] = None,
) -> List[int]:
    """Select keyframe timestamps based on transcript context completeness.

    1. Incomplete Context: If items contain deictic pronouns, visual pointers, or
       exclamatory reactions where text alone lacks grounding, sample frames directly
       at those cue timestamps to visually fill in the missing context.
    2. Dynamic Count: Sends at least min_frames (default 3), but expands up to max_frames (default 5)
       if multiple distinct visual moments/cues need grounding in this chunk.
    3. Full/Self-Contained Context: If text is complete, sample frames from the most
       interesting moments (longest statements, topic shifts, emphasis) distributed
       across the chunk.
    """
    if num_frames is not None:
        min_frames = num_frames
        max_frames = num_frames

    if not items:
        if min_frames <= 1:
            return [(start_sec + end_sec) // 2]
        if min_frames == 2:
            return [start_sec + 25, end_sec - 25]
        return [start_sec + 25, (start_sec + end_sec) // 2, max(start_sec + 30, end_sec - 25)]

    # 1. Search for incomplete context cues
    cue_candidates: List[Tuple[float, int]] = []
    for it in items:
        txt = it.get("text", "")
        sec = int(it.get("start", 0))
        if sec < start_sec or sec > end_sec:
            continue

        score = 0
        for cue in INCOMPLETE_CONTEXT_CUES:
            if cue in txt:
                score += 2 if cue in ("ดูอันนี้", "ดูนี่", "เนี่ยดูดิ", "เปิดดู", "ในจอ", "ตรงนี้", "[?]") else 1

        if score > 0:
            cue_candidates.append((score, sec))

    # Pick top cues with temporal spacing guard (>= 25s apart) up to max_frames
    selected_secs: List[int] = []
    cue_candidates.sort(key=lambda x: x[0], reverse=True)
    for _, sec in cue_candidates:
        if all(abs(sec - s) >= 25 for s in selected_secs):
            selected_secs.append(sec)
            if len(selected_secs) == max_frames:
                break

    # 2. If chunk has fewer than min_frames, supplement from interesting context
    if len(selected_secs) < min_frames:
        interesting_candidates: List[Tuple[float, int]] = []
        for it in items:
            txt = it.get("text", "")
            sec = int(it.get("start", 0))
            if sec < start_sec or sec > end_sec:
                continue

            int_score = len(txt) / 10.0
            if any(p in txt for p in ("!", "?", "555", "แต่ว่า", "เพราะว่า", "คือ")):
                int_score += 2.0
            interesting_candidates.append((int_score, sec))

        interesting_candidates.sort(key=lambda x: x[0], reverse=True)
        for _, sec in interesting_candidates:
            if all(abs(sec - s) >= 25 for s in selected_secs):
                selected_secs.append(sec)
                if len(selected_secs) >= min_frames:
                    break

    # 3. Fill any remaining slots up to min_frames evenly across chunk bounds
    fallback_pool = [
        start_sec + 25,
        (start_sec + end_sec) // 2,
        max(start_sec + 30, end_sec - 25),
        start_sec + 80,
        end_sec - 80,
    ]
    for fb in fallback_pool:
        if len(selected_secs) >= min_frames:
            break
        if all(abs(fb - s) >= 20 for s in selected_secs):
            selected_secs.append(fb)

    selected_secs.sort()
    return selected_secs[:max_frames]


def sample_chunk_keyframes(
    start_sec: int,
    end_sec: int,
    slides_dir: Path,
    out_dir: Path,
    min_frames: int = 3,
    max_frames: int = 5,
    sec_per_slide: float = 88.94,
    sec_per_tile: float = 9.88,
    items: Optional[List[dict]] = None,
    num_frames: Optional[int] = None,
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

    target_secs = select_target_seconds(
        start_sec, end_sec, min_frames=min_frames, max_frames=max_frames, items=items, num_frames=num_frames
    )

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
                if Image is not None:
                    im = Image.open(slide_file)
                    tile = im.crop((col * 320, row * 180, (col + 1) * 320, (row + 1) * 180))
                    tile.save(out_tile, quality=95)
                else:
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", str(slide_file),
                            "-vf", f"crop=320:180:{col * 320}:{row * 180}",
                            "-frames:v", "1", "-q:v", "2", str(out_tile),
                        ],
                        capture_output=True,
                        check=True,
                        timeout=15,
                    )
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
    """Construct standard OpenAI multi-modal messages content list.

    Pairs each image with explicit text stating its exact timestamp and instructing
    the model to save/emit that timestamp if the visual marks a key event/shift.
    """
    content: List[dict] = [{"type": "text", "text": prompt_text}]
    for i, (ts_str, _, b64_data) in enumerate(keyframes):
        content.append({
            "type": "text",
            "text": f"[Attached Frame {i+1} at timestamp {ts_str} — Save and use this exact timestamp {ts_str} when referencing this visual event in your output]:"
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
        })
    return content


def call_multimodal(
    endpoint: str,
    model: str,
    content_list: List[dict],
    max_tokens: int = CHUNK_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = MULTIMODAL_TIMEOUT_SEC,
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
