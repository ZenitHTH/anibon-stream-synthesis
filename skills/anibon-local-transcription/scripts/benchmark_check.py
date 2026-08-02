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
