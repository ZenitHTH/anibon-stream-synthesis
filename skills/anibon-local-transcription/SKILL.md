---
name: anibon-local-transcription
description: Transcribe YouTube audio locally using whisper.cpp when YouTube has no subtitles or auto-captions. Alternative path loaded by anibon-timestamper.
disable-model-invocation: true
---

# Anibon Local Audio Transcription

Use when YouTube has no subtitles or auto-captions for the target video.

## 1. Audio Extraction

Download audio stream as a mono 16kHz WAV file:

```bash
yt-dlp -x --audio-format wav --audio-quality 16K "VIDEO_URL" -o "audio.wav"
```

## 2. Local Transcription

Run GPU-accelerated whisper.cpp build:

**Windows (Vulkan/AMD):**
```powershell
.\whisper-cli.exe -m ggml-large-v3-turbo.bin -l th -f audio.wav -ot 540000 2>&1
```
*(`-ot 540000` = 9 min offset to skip silent start screens and avoid repetition loop bugs)*

For full build options and platform configurations, see [BUILD_GPU.md](BUILD_GPU.md).

## 3. Format Conversion

Convert whisper-cli raw JSON output to pipeline-standard `raw_transcript.json`:

```bash
python3 scripts/clean_transcript.py whisper_output.json --format whisper --output raw_transcript.json
```

Then proceed with the standard pipeline (chunking, signal detection, subagents).
