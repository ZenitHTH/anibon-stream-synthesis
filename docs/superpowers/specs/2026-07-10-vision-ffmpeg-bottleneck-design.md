# Vision FFmpeg Bottleneck Fix

## Goal
Resolve the issue where `_vision.py` freezes indefinitely during execution because `ffmpeg` hangs when trying to fetch frames synchronously from a remote YouTube stream URL.

## Context
When running `prepare_video.py --vision`, the script uses `_vision.py` to extract frames for ambiguous pronouns (e.g., "he", "this guy"). Currently, it gets the remote stream URL via `yt-dlp` and calls `ffmpeg` for each timestamp. For a 7-hour video, this generates hundreds of remote stream requests, causing network timeouts and permanent subprocess hangs.

## Architecture & Data Flow
1. **Local Download**: Instead of streaming, `_vision.py` will use `yt-dlp` to download a low-resolution (<= 480p) video file to the user's workspace (e.g., `temp_video.mp4`).
2. **Local Extraction**: The `extract_frame` function will be modified to accept the local file path instead of the remote URL. 
3. **Iterative Processing**: The existing loop will remain unchanged, calling `ffmpeg` for each candidate timestamp. Because it reads a local file, there will be no network latency or throttling.
4. **Cleanup**: Once all candidate frames are extracted (or if the script errors out during extraction), the `temp_video.mp4` file will be deleted to free up disk space.

## Error Handling & Resilience
- **Download Failure**: The `yt-dlp` download subprocess will have `check=True`. If it fails, the script will catch the exception, log an error message to `sys.stderr`, and exit the vision phase gracefully without crashing the whole application or leaving broken chunks.
- **Subprocess Timeouts**: The local `ffmpeg` subprocess calls in `extract_frame` will have a strict `timeout=15` applied. If a local extraction hangs, it will be terminated, a warning will be logged, and the loop will continue to the next frame.

## Affected Files
- `scripts/_vision.py`
