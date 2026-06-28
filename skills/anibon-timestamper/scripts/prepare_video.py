import sys, os, subprocess, shutil
from pathlib import Path

# ponytail: One script to rule them all. 
# Replaces 50 lines of complex cross-platform shell escaping prompt engineering for local LLMs.
# Ceiling: blocks synchronously. Upgrade path: async execution if yt-dlp gets slow.

def main():
    if len(sys.argv) < 2:
        print("Usage: python prepare_video.py <VIDEO_URL_OR_ID>")
        sys.exit(1)
        
    url = sys.argv[1]
    video_id = url.split("v=")[-1].split("&")[0].split("/")[-1]
    
    # Force expand ~ to true absolute path for cross-platform safety
    workspace = os.path.expanduser(f"~/youtube_{video_id}_workspace")
    os.makedirs(workspace, exist_ok=True)
    os.chdir(workspace)
    
    print(f"[*] Workspace: {workspace}")
    
    if not os.path.exists("raw_transcript.json"):
        print(f"[*] Downloading transcript for {video_id} via yt-dlp...")
        subprocess.run([
            sys.executable, "-m", "yt_dlp", "-P", ".", "--write-auto-subs", "--sub-lang", "th-orig,th", 
            "--sub-format", "json3", "--skip-download", "--ignore-no-formats-error", 
            "-o", "raw_transcript", url
        ], check=False)
        
        if f := next(Path('.').glob('raw_transcript*.json3'), None):
            f.rename("raw_transcript.json")
                
    if not os.path.exists("raw_transcript.json"):
        print("[!] Error: Failed to download transcript. Check URL, yt-dlp, or video availability.", file=sys.stderr)
        sys.exit(1)
        
    print("[*] Transcript ready. Cleaning and chunking...")
    
    # Resolve absolute path to clean_transcript.py
    clean_script = Path(__file__).parent / "clean_transcript.py"
    
    subprocess.run([
        sys.executable, str(clean_script), "raw_transcript.json", 
        "--chunk", "--chunk-dir", "chunks", "--block", "300", "--overlap", "30"
    ], check=True)
    
    print(f"[*] Pipeline complete! You can now analyze chunks in {workspace}/chunks/")

if __name__ == "__main__":
    main()
