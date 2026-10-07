"""vision_verify.py — Ambiguous timestamp detection and visual ground truth verification."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from anibon.lmstudio import call_vision


DEICTIC = ("คุณนี้", "ตัวนี้", "อันนี้", "นี่น่ะ", "นี้น่ะ")
GENERIC = ("สู้มอนสเตอร์", "ในเกม", "เล่นเกมจนจบ")


def stamp_seconds(stamp: str) -> int:
    """Parse HH:MM:SS from timestamp string and return seconds."""
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})", stamp.strip())
    if not m:
        return 0
    h, m_val, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + m_val * 60 + s


def is_ambiguous(stamp: str) -> bool:
    """Determine if a timestamp description needs visual grounding.

    Criteria:
    1. Contains uncertainty marker '[?]'
    2. Description length after '] ' is under 20 characters
    3. Contains deictic pronouns ('คุณนี้', 'ตัวนี้', etc.)
    4. Contains generic gameplay phrases without an identifiable English proper noun (>= 4 chars)
    """
    if "[?]" in stamp:
        return True

    # Extract description after tag: 'HH:MM:SS - [Tag] Description'
    m = re.search(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]\s*(.*)$", stamp.strip())
    if not m:
        return False

    desc = m.group(3).strip()
    if len(desc) < 20:
        return True

    for word in DEICTIC:
        if word in desc:
            return True

    for phrase in GENERIC:
        if phrase in desc:
            # Check if there is an identifiable English entity (>= 4 letters)
            if not re.search(r"[A-Za-z]{4,}", desc):
                return True

    return False


def build_verify_prompt(stamp: str, context: str = "") -> str:
    """Build a prompt asking the vision model to inspect the frame and verify/disambiguate the timestamp."""
    m = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]\s*(.*)$", stamp.strip())
    ts = m.group(1) if m else "00:00:00"
    tag = m.group(2) if m else "Talk"
    desc = m.group(3) if m else stamp

    ctx_block = f"\nContext Transcript around this moment:\n{context}\n" if context else ""

    return f"""Inspect this screenshot from an Anibon livestream at timestamp {ts}.
Original draft timestamp line:
{ts} - [{tag}] {desc}
{ctx_block}
Task:
1. Examine what is literally visible on screen (game title, character/hero names, UI elements, website, steam chart, article, or video).
2. If the draft description is vague, misheard, or phonetically garbled (e.g. 'ตัวละครใหม่' -> 'Acheron ใน Honkai: Star Rail'), correct the entity name accurately in Thai.
3. Keep the EXACT same timestamp '{ts}' and tag '[{tag}]'. Only refine the description text following '[{tag}] '.
4. Never report hyperbolic roasts as literal depiction.
5. Return JSON ONLY in this format:
{{
  "corrected": "{ts} - [{tag}] <accurate Thai description>",
  "confidence": <float between 0.0 and 1.0>
}}"""


def parse_verify_response(raw: str, original: str, min_conf: float = 0.6) -> str:
    """Parse JSON response from vision model and validate constraints.

    Must keep identical HH:MM:SS and [Tag], and meet minimum confidence.
    Returns corrected string if valid, otherwise original.
    """
    if not raw or not isinstance(raw, str):
        return original

    jm = re.search(r"(\{.*\})", raw, re.DOTALL)
    if not jm:
        return original

    try:
        data = json.loads(jm.group(1))
    except Exception:
        return original

    corrected = data.get("corrected")
    if not corrected or not isinstance(corrected, str):
        return original

    try:
        confidence = float(data.get("confidence", 0.0))
    except (ValueError, TypeError):
        return original

    if confidence < min_conf:
        return original

    # Validate that HH:MM:SS and [Tag] are preserved exactly
    m_orig = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]", original.strip())
    m_corr = re.match(r"^(\d{2}:\d{2}:\d{2})\s*-\s*\[([^\]]+)\]", corrected.strip())

    if not m_orig or not m_corr:
        return original

    if m_orig.group(1) != m_corr.group(1):
        # Timestamp changed
        return original

    if m_orig.group(2).strip().lower() != m_corr.group(2).strip().lower():
        # Tag changed
        return original

    return corrected.strip()


def extract_frame(video: Path, sec: int, out: Path) -> Optional[Path]:
    """Extract a single frame from video at given seconds using ffmpeg."""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    ts_str = f"{h:02d}:{m:02d}:{s:02d}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", ts_str,
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return out_path
    except Exception as e:
        print(f"[vision] ffmpeg error at {ts_str}: {e}", file=sys.stderr)
    return None


def verify_ambiguous_stamps(
    stamps: List[str],
    workspace: Path,
    video: Optional[Path],
    endpoint: str,
    model: str,
    context_fn: Callable[[int], str] = lambda s: "",
    call_fn: Callable = call_vision,
    frame_fn: Callable = extract_frame,
) -> List[str]:
    """Orchestrate vision grounding for ambiguous timestamps.

    Extracts frames, queries vision LLM, validates output, and maintains a cache log.
    Returns the verified stamps list in identical order.
    """
    workspace = Path(workspace)
    if not video or not Path(video).exists():
        print(f"[vision] Video not found ({video}), skipping vision verify.", file=sys.stderr)
        return list(stamps)

    frames_dir = workspace / "frames_verify"
    frames_dir.mkdir(parents=True, exist_ok=True)

    log_path = workspace / "vision_verify_log.json"
    cache: Dict[str, dict] = {}
    if log_path.exists():
        try:
            cache = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    verified_stamps: List[str] = []

    for stamp in stamps:
        if not is_ambiguous(stamp):
            verified_stamps.append(stamp)
            continue

        if stamp in cache:
            cached_result = cache[stamp].get("result", stamp)
            verified_stamps.append(cached_result)
            continue

        sec = stamp_seconds(stamp)
        h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
        safe_ts = f"{h:02d}-{m:02d}-{s:02d}"
        frame_path = frames_dir / f"frame_{safe_ts}.jpg"

        extracted = frame_fn(Path(video), sec, frame_path)
        if not extracted or not Path(extracted).exists():
            print(f"[vision] {stamp[:8]} ✗ could not extract frame, keeping original")
            cache[stamp] = {"result": stamp, "accepted": False}
            verified_stamps.append(stamp)
            try:
                log_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            continue

        prompt = build_verify_prompt(stamp, context_fn(sec))
        try:
            raw = call_fn(endpoint, model, prompt, extracted)
            corrected = parse_verify_response(raw, stamp)
            accepted = (corrected != stamp)
            if accepted:
                print(f"[vision] {stamp[:8]} ✓ corrected -> {corrected}")
            else:
                print(f"[vision] {stamp[:8]} ✗ kept original")
            result = corrected
        except Exception as e:
            print(f"[vision] {stamp[:8]} ✗ error: {e}, keeping original", file=sys.stderr)
            result = stamp
            accepted = False

        cache[stamp] = {"result": result, "accepted": accepted}
        verified_stamps.append(result)

        try:
            log_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return verified_stamps


def apply_vision_verify(
    stamps: List[str],
    workspace: Path,
    args: Any,
    model: str,
) -> List[str]:
    """Helper to apply vision verification pass if enabled in CLI args."""
    if not getattr(args, "vision_verify", False):
        return stamps

    workspace = Path(workspace)
    video_file = getattr(args, "video_file", None)
    if video_file:
        video_path = Path(video_file)
    else:
        video_path = workspace / "video_360p.mp4"
        if not video_path.exists():
            video_path = workspace / "video.mp4"

    vision_model = getattr(args, "vision_model", None) or model
    endpoint = getattr(args, "endpoint", "http://127.0.0.1:1234/v1/chat/completions")

    def context_fn(sec: int) -> str:
        chunks_dir = workspace / "chunks"
        if not chunks_dir.exists():
            return ""
        for cf in sorted(chunks_dir.glob("chunk_*.txt")):
            txt = cf.read_text(encoding="utf-8", errors="replace")
            for line in txt.splitlines():
                m = re.match(r"\[(\d{2}):(\d{2}):(\d{2})\]", line)
                if m:
                    line_sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                    if abs(line_sec - sec) <= 45:
                        return line[:200]
        return ""

    verified = verify_ambiguous_stamps(
        stamps,
        workspace,
        video_path,
        endpoint,
        vision_model,
        context_fn=context_fn,
    )

    if verified != stamps:
        raw_ts = workspace / "all_timestamps.txt"
        try:
            raw_ts.write_text("\n".join(verified) + "\n", encoding="utf-8")
        except Exception:
            pass

    return verified
