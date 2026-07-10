# scripts/_vision.py
import sys, os, subprocess, json, re
from pathlib import Path

KEYWORDS = [
    r"\bhe\b", r"\bshe\b", r"\bthis guy\b", r"\bthis character\b", r"\bthis card\b",
    r"\bimage\b", r"\bpicture\b", r"\bwho\b",
    "คนนี้", "คนนั้น", "ใคร", "รูป", "ภาพ", "การ์ด", "ตัวนี้", "ตัวละคร", "เขา"
]

def download_reference_video(video_url: str, workspace: Path) -> Path | None:
    """Download a low-res reference video using yt-dlp."""
    out_path = workspace / "reference_video.mp4"
    if out_path.exists():
        print(f"[*] Reference video already exists at {out_path}", file=sys.stderr)
        return out_path

    print(f"[*] Downloading reference video via yt-dlp...", file=sys.stderr)
    try:
        subprocess.run([
            "yt-dlp", "-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", str(out_path), video_url
        ], capture_output=False, check=True)
        return out_path
    except Exception as e:
        print(f"[!] Failed to download reference video: {e}", file=sys.stderr)
        return None

def extract_frame(video_path: Path, start_sec: float, out_path: Path) -> bool:
    """Extract a single frame at start_sec using ffmpeg."""
    out_path.parent.mkdir(exist_ok=True)
    h = int(start_sec // 3600)
    m = int((start_sec % 3600) // 60)
    s = start_sec % 60
    ts_str = f"{h:02d}:{m:02d}:{s:06.3f}"
    
    cmd = [
        "ffmpeg", "-y", "-ss", ts_str, "-i", str(video_path),
        "-vframes", "1", "-vf", "scale=480:-1", "-q:v", "5", str(out_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, check=False, timeout=15)
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[!] ffmpeg timed out extracting frame at {ts_str}", file=sys.stderr)
        return False
    except Exception:
        return False

def run(workspace: Path, video_url: str) -> int:
    """Scan transcript, extract frames for pronoun cues, and annotate chunks."""
    raw_path = workspace / "raw_transcript.json"
    if not raw_path.exists():
        print(f"[!] raw_transcript.json not found in {workspace}", file=sys.stderr)
        return 0

    from _transcript import load
    items = load(workspace)
    
    patterns = [re.compile(p, re.I) for p in KEYWORDS]
    
    candidates = []
    for item in items:
        text = item.get("text", "")
        if any(p.search(text) for p in patterns):
            candidates.append(item)
            
    if not candidates:
        print("[*] No visual keywords found in transcript.", file=sys.stderr)
        return 0
        
    print(f"[*] Found {len(candidates)} potential visual references.", file=sys.stderr)
    
    video_path = download_reference_video(video_url, workspace)
    if not video_path:
        return 0
        
    frames_dir = workspace / "frames"
    frames_dir.mkdir(exist_ok=True)
    
    extracted_count = 0
    annotated_items = {}
    
    for item in candidates:
        start_sec = item["start"]
        ts_name = item["timestamp"].replace(":", "_")
        out_name = f"frame_{ts_name}.jpg"
        out_path = frames_dir / out_name
        
        if out_path.exists() or extract_frame(video_path, start_sec, out_path):
            annotated_items[start_sec] = f"frames/{out_name}"
            extracted_count += 1
            if extracted_count % 10 == 0:
                print(f"[*] Extracted {extracted_count} frames...", file=sys.stderr)
                
    chunk_dir = workspace / "chunks"
    if not chunk_dir.exists():
        return extracted_count
        
    updated_chunks = 0
    for chunk_file in chunk_dir.glob("chunk_*.json"):
        try:
            data = json.loads(chunk_file.read_text(encoding="utf-8"))
            dirty = False
            for item in data.get("items", []):
                start = item.get("start")
                if start in annotated_items:
                    item["image"] = annotated_items[start]
                    dirty = True
            if dirty:
                chunk_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                updated_chunks += 1
        except Exception as e:
            print(f"[!] Error updating {chunk_file.name}: {e}", file=sys.stderr)
            
    print(f"[*] Done! Extracted {extracted_count} frames and updated {updated_chunks} chunk files.", file=sys.stderr)
    return extracted_count
