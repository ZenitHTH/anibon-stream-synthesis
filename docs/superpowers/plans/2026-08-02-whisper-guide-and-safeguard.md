# Whisper.cpp Build Guide & 3-Hour Benchmark Safeguard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 3-Hour Benchmark Safeguard script and update `BUILD_WHISPERCPP_GUILD.md` with multi-platform build guides and i3-12100 AVX2 speed benchmarks.

**Architecture:** Create a standalone Python benchmark pre-check utility (`benchmark_check.py`) for the local transcription skill, and rewrite `BUILD_WHISPERCPP_GUILD.md` to document hardware safeguards, MinGW/CUDA/HIP/Metal builds, and RTF benchmark tables.

**Tech Stack:** Python 3.10+, PowerShell, `whisper-cli.exe`, Markdown.

## Global Constraints
- Threshold limit: 3 hours (10,800 seconds).
- Windows compiler: MinGW GCC 15.2 + CMake (`pip install cmake`).
- Target binary: `C:\Users\SMTE-PC\whisper.cpp\build\bin\whisper-cli.exe`.

---

### Task 1: Create Pre-Flight Benchmark Safeguard Script (`benchmark_check.py`)

**Files:**
- Create: `C:\Users\SMTE-PC\.gemini\config\plugins\anibon-stream-synthesis\skills\anibon-local-transcription\scripts\benchmark_check.py`

**Interfaces:**
- Consumes: Audio file path, total audio duration (seconds), whisper-cli path, model path.
- Produces: Command exit code `0` (pass) or `1` (fail: exceeds 3 hours).

- [ ] **Step 1: Write `benchmark_check.py`**

```python
import sys
import subprocess
import time
import argparse

def run_benchmark(whisper_cli: str, model: str, audio: str, total_duration_sec: float) -> bool:
    print("[*] Running 10-second pre-flight benchmark test...")
    start_time = time.time()
    
    cmd = [
        whisper_cli,
        "-m", model,
        "-f", audio,
        "-d", "10000",  # 10 seconds in ms
        "-l", "th",
        "-t", "8",
        "-np"
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        elapsed = time.time() - start_time
        if res.returncode != 0:
            print(f"[!] Benchmark error: {res.stderr}")
            return False
            
        speed_ratio = 10.0 / max(elapsed, 0.001)
        predicted_seconds = total_duration_sec / speed_ratio
        predicted_hours = predicted_seconds / 3600.0
        
        print(f"[*] Benchmark elapsed for 10s sample: {elapsed:.2f}s")
        print(f"[*] Estimated Speed Ratio: {speed_ratio:.2f}x real-time")
        print(f"[*] Predicted Total Render Time: {predicted_hours:.2f} hours ({predicted_seconds:.0f}s)")
        
        if predicted_hours > 3.0:
            print(f"[ERROR] Predicted render time ({predicted_hours:.2f}h) exceeds 3.0-hour limit! Refusing full render.")
            return False
        else:
            print("[SUCCESS] Hardware benchmark passed (render time < 3 hours). Proceeding with full transcription.")
            return True
            
    except Exception as e:
        print(f"[!] Benchmark execution failed: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-flight benchmark check for whisper.cpp")
    parser.add_argument("--cli", required=True, help="Path to whisper-cli executable")
    parser.add_argument("--model", required=True, help="Path to whisper ggml model")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--duration", type=float, required=True, help="Total audio duration in seconds")
    args = parser.parse_args()
    
    ok = run_benchmark(args.cli, args.model, args.audio, args.duration)
    sys.exit(0 if ok else 1)
```

- [ ] **Step 2: Test `benchmark_check.py` help output**

Run: `python C:\Users\SMTE-PC\.gemini\config\plugins\anibon-stream-synthesis\skills\anibon-local-transcription\scripts\benchmark_check.py --help`
Expected: Print CLI usage help without syntax errors.

---

### Task 2: Rewrite `BUILD_WHISPERCPP_GUILD.md`

**Files:**
- Modify: `C:\Users\SMTE-PC\.gemini\config\plugins\anibon-stream-synthesis\skills\anibon-timestamper\BUILD_WHISPERCPP_GUILD.md`

- [ ] **Step 1: Write updated `BUILD_WHISPERCPP_GUILD.md`**

Incorporate Section 1 (3-Hour Pre-Flight Benchmark Safeguard), Section 2 (Multi-Platform Builds), Section 3 (Hardware Benchmarks & i3-12100 AVX2 Speed Table), and Section 4 (SIMD Diagnostics).

- [ ] **Step 2: Verify `BUILD_WHISPERCPP_GUILD.md` file exists and is rendered cleanly**

View `BUILD_WHISPERCPP_GUILD.md` to ensure all links and tables are formatted correctly.
