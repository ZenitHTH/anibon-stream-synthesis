# Vision FFmpeg Bottleneck Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify `_vision.py` to download a low-resolution reference video locally and extract frames from it to prevent remote `ffmpeg` calls from hanging due to YouTube throttling.

**Architecture:** We will replace `get_stream_url` with `download_reference_video` which uses `yt-dlp` to save a 480p mp4 file to the workspace. We will then update `extract_frame` to use this local file path and add a 15-second timeout to the `ffmpeg` subprocess to ensure resilience.

**Tech Stack:** Python, subprocess, yt-dlp, ffmpeg

---

### Task 1: Replace `get_stream_url` with `download_reference_video`

**Files:**
- Modify: `scripts/_vision.py`
- Modify: `tests/test_vision.py`

- [ ] **Step 1: Write the failing test**

Modify `tests/test_vision.py` to replace the `test_get_stream_url` test with a test for `download_reference_video`.

```python
@patch("subprocess.run")
def test_download_reference_video(mock_run, tmp_path):
    # Setup mock
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_run.return_value = mock_proc
    
    # Test successful download
    result = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
    
    # Assertions
    assert result == tmp_path / "reference_video.mp4"
    mock_run.assert_called_once()
    
    # Test skipping download if file exists
    (tmp_path / "reference_video.mp4").touch()
    mock_run.reset_mock()
    result_existing = _vision.download_reference_video("https://youtube.com/watch?v=123", tmp_path)
    assert result_existing == tmp_path / "reference_video.mp4"
    mock_run.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vision.py::test_download_reference_video -v`
Expected: FAIL with "module '_vision' has no attribute 'download_reference_video'"

- [ ] **Step 3: Write minimal implementation**

Modify `scripts/_vision.py`. Replace `get_stream_url` (lines 11-21) with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vision.py::test_download_reference_video -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_vision.py scripts/_vision.py
git commit -m "feat: replace stream url fetching with local reference video download"
```

### Task 2: Update `extract_frame` with Timeout

**Files:**
- Modify: `scripts/_vision.py`
- Modify: `tests/test_vision.py`

- [ ] **Step 1: Write the failing test**

Add a test for `extract_frame` timeouts to `tests/test_vision.py`:

```python
@patch("subprocess.run")
def test_extract_frame_timeout(mock_run, tmp_path):
    import subprocess
    # Setup mock to raise TimeoutExpired
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15)
    
    video_path = tmp_path / "reference_video.mp4"
    out_path = tmp_path / "frame.jpg"
    
    result = _vision.extract_frame(video_path, 10.5, out_path)
    
    # It should catch the timeout and return False
    assert result is False
    mock_run.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vision.py::test_extract_frame_timeout -v`
Expected: FAIL because `subprocess.run` inside the current `extract_frame` doesn't catch `TimeoutExpired` properly or doesn't have a timeout parameter.

- [ ] **Step 3: Write minimal implementation**

Modify `scripts/_vision.py`. Update the `extract_frame` function to:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vision.py::test_extract_frame_timeout -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_vision.py scripts/_vision.py
git commit -m "feat: add timeout to extract_frame and support local video path"
```

### Task 3: Update `run` wiring

**Files:**
- Modify: `scripts/_vision.py`

- [ ] **Step 1: Write the minimal implementation**

In `scripts/_vision.py`, update the `run` function to use `download_reference_video`.
Replace lines 65-67 (`stream_url = get_stream_url(video_url) ...`) with:

```python
    video_path = download_reference_video(video_url, workspace)
    if not video_path:
        return 0
```

Then, further down in the loop, change `extract_frame(stream_url, ...)` to `extract_frame(video_path, ...)`:

```python
        if out_path.exists() or extract_frame(video_path, start_sec, out_path):
```

- [ ] **Step 2: Run the full test suite to ensure no regressions**

Run: `pytest tests/test_vision.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/_vision.py
git commit -m "refactor: wire run() to use local reference video download"
```
