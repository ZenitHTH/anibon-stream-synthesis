---
name: whisper-corruption-recovery
description: Use when Whisper transcription contains repetition loops, repeated identical phrases, or long-audio transcripts contain corrupt segments.
---

# Whisper Corruption Recovery

## Overview
Whisper on audio ≥2h can enter repetition loops — in-segment phoneme repeats or cross-segment multi-line loops (e.g. A-B-A-B). The `whisper-corruption-recovery` skill provides a **BFS Parallel Divide-and-Conquer (D&C)** engine with sub-1-second mathematical base-case guarantees, `[?]` text prepending, and visual frame context extraction.

---

## Automated Recovery Scripts

### 1. BFS Parallel Audio Recovery (`scripts/fix_hallucinations.py`)

Scans transcripts for in-segment phoneme loops and cross-segment multi-sentence loops ($A-A-A-A$, $A-B-A-B$, $A-B-C-A-B-C$), chunks corrupt ranges into 30s tasks matching Whisper's native context window, and executes parallel BFS D&C recovery down to sub-1-second slices.

```bash
# Single GPU (Fastest: RX 7600 Vulkan matrix cores)
python3 scripts/fix_hallucinations.py <whisper_json> <audio_wav> --devices 0 -w 3 -o recovered_transcript.json

# Dual-GPU Parallel (RX 7600 + Tesla P100 concurrently)
python3 scripts/fix_hallucinations.py <whisper_json> <audio_wav> --devices 0 1 -w 4 -o recovered_transcript.json
```

**Options**:
- `-dev` / `--devices` — GPU device ID(s) pool (e.g., `--devices 0` for single GPU or `--devices 0 1` for dual-GPU load balancing, default: `0`).
- `-w 4` / `--workers 4` — Number of concurrent worker threads (default: `4`).
- `-t 4` / `--threads 4` — CPU thread count per worker (default: `4`).
- `--threshold 0.4` — Repetition n-gram ratio threshold (default: 0.4).
- `--min-duration 1.0` — Minimum duration in seconds before hitting the base case (default: 1.0s).
- `-o output.json` — Path for final recovered transcript JSON.

**Key Guarantees**:
- **Task Deduplication**: Each audio slice splits at most once per task, preventing task explosion.
- **Sub-1-Second Guarantee**: Task bounds halving $(start + end) // 2$ strictly reduces slice duration down to $< 1.0\text{s}$ (max 9 levels).
- **Data Preservation (`[?]`)**: Low-confidence/uncertain items are **never deleted**. The original text attempt is prepended with `"[?] "` (e.g., `"[?] มา มา มา มา"`) so human/vision reviewers can verify by listening or inspecting video frames.

---

### 2. Visual Context Frame Extractor (`scripts/enrich_uncertain_with_vision.py`)

Scans `recovered_transcript.json` for all `[?]` uncertain items, extracts video frames at their exact timestamps using `ffmpeg`, and creates a visual inspection report for vision-model review.

```bash
python3 scripts/enrich_uncertain_with_vision.py recovered_transcript.json stream_video.mp4 -o frames_uncertain
```

**Workflow with Vision Proxy (`antigravity-vision-proxy`)**:
```powershell
# Extract frames and generate README.md report
python3 scripts/enrich_uncertain_with_vision.py recovered_transcript.json video_360p.mp4 -o frames_uncertain

# Run Gemini Vision analysis to fulfill [?] text context
agy --model "Gemini 3.6 Flash (Medium)" --dangerously-skip-permissions `
  --print "Identify per frame: 1) Game/Screen State 2) On-screen text/dialogue 3) Fulfill [?] speech context" `
  --add-dir frames_uncertain
```

---

## Key Rules & Prohibitions

1. **Never re-run Whisper on the full audio file**. Full re-runs repeat the same corruption boundaries. Always split into 30s chunks first.
2. **D&C Scoping**:
   - **Cross-segment sentence loops** ($A-A-A-A$, $A-B-A-B$) $\to$ Trigger D&C audio recovery.
   - **In-segment word repeats** $\to$ Mark with `"[?] "` for review (DO NOT trigger audio splitting).
3. **Data Integrity**: Never silently discard sub-second or uncertain items; preserve text attempts prepended with `"[?] "`.
