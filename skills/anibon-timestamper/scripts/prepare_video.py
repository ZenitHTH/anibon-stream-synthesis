# scripts/prepare_video.py
import sys, argparse
from pathlib import Path

# Point to shared lib/  (4 levels up: scripts/ -> skill/ -> skills/ -> plugin root -> lib/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "lib"))

from anibon import ytdlp, cleaner
from anibon.resources import load_default_mappings
from anibon.chunk_io import write_chunk_json, write_chunk_xml, write_chunk_txt


def chunk_transcript(workspace: Path, block: int, overlap: int, fmt: str) -> int:
    """Load transcript, clean, and write chunk files. Returns number of chunks."""
    transcript = ytdlp.load_transcript(workspace)
    mappings = load_default_mappings()
    cleaned = cleaner.correct_transcript(transcript, mappings)

    if not cleaned:
        return 0

    chunk_dir = workspace / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    total = int(cleaned[-1]["start"] + cleaned[-1].get("duration", 0))
    step = block - overlap
    idx = 0

    for start in range(0, total, step):
        end = start + block
        items = [x for x in cleaned if start <= x["start"] < end]
        if not items:
            continue
        path = chunk_dir / f"chunk_{idx:02d}.{fmt}"
        if fmt == "txt":
            write_chunk_txt(path, idx, start, end, overlap, items)
        elif fmt == "xml":
            write_chunk_xml(path, idx, start, end, items)
        else:
            write_chunk_json(path, start, end, items)
        idx += 1
    return idx


def main():
    ap = argparse.ArgumentParser(
        description="Download and chunk a YouTube transcript for AI timestamping."
    )
    ap.add_argument("url", help="YouTube video URL or ID")
    ap.add_argument("--format", choices=["json", "txt", "xml"], default="json",
                    help="Output format: json (Gemini), xml (Claude), or txt (local). Default: json")
    ap.add_argument("--block", type=int, default=300,
                    help="Chunk block size in seconds (default: 300 = 5 min)")
    ap.add_argument("--overlap", type=int, default=30,
                    help="Chunk overlap in seconds (default: 30)")
    ap.add_argument("--vision", action="store_true",
                    help="Extract and annotate visual frames for ambiguous pronoun cues")
    args = ap.parse_args()

    # Extract video_id from URL or use as-is
    url = args.url
    vid = url.split("v=")[-1].split("&")[0].split("/")[-1].split("?")[0]

    workspace = Path.home() / f"youtube_{vid}_workspace"
    workspace.mkdir(exist_ok=True)
    print(f"[*] Workspace: {workspace}", file=sys.stderr)

    ytdlp.download_transcript(url, workspace)
    n = chunk_transcript(workspace, block=args.block, overlap=args.overlap, fmt=args.format)

    if args.vision and args.format in ["json", "xml"]:
        import _vision
        _vision.run(workspace, url)

    print(f"[*] Done! Wrote {n} chunks ({args.format}) to {workspace}/chunks/")


if __name__ == "__main__":
    main()
