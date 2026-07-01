# scripts/prepare_video.py
import sys, os, argparse
from pathlib import Path

# Add scripts/ dir to path so _transcript and _chunker can be imported
sys.path.insert(0, str(Path(__file__).parent))
import _transcript
import _chunker

def main():
    ap = argparse.ArgumentParser(
        description="Download and chunk a YouTube transcript for AI timestamping."
    )
    ap.add_argument("url", help="YouTube video URL or ID")
    ap.add_argument("--format", choices=["json", "txt"], default="json",
                    help="Output format: json (cloud/Gemini) or txt (local/Gemma). Default: json")
    ap.add_argument("--block", type=int, default=300,
                    help="Chunk block size in seconds (default: 300 = 5 min)")
    ap.add_argument("--overlap", type=int, default=30,
                    help="Chunk overlap in seconds (default: 30)")
    ap.add_argument("--vision", action="store_true",
                    help="Extract and annotate visual frame frames for ambiguous pronoun cues")
    args = ap.parse_args()

    # Extract video_id from URL or use as-is
    url = args.url
    vid = url.split("v=")[-1].split("&")[0].split("/")[-1].split("?")[0]

    workspace = Path.home() / f"youtube_{vid}_workspace"
    workspace.mkdir(exist_ok=True)
    print(f"[*] Workspace: {workspace}", file=sys.stderr)

    _transcript.download(url, workspace)
    n = _chunker.run(workspace, block=args.block, overlap=args.overlap, fmt=args.format)
    
    if args.vision and args.format == "json":
        import _vision
        _vision.run(workspace, url)

    ext = "txt" if args.format == "txt" else "json"
    print(f"[*] Done! Wrote {n} chunks ({ext}) to {workspace}/chunks/")

if __name__ == "__main__":
    main()
