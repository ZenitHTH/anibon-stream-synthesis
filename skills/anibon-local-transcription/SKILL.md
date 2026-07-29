---
name: anibon-local-transcription
description: Transcribe YouTube audio locally using whisper.cpp when YouTube has no subtitles or auto-captions. Alternative path loaded by anibon-timestamper.
disable-model-invocation: true
---

# Anibon Local Audio Transcription

Use when YouTube has no subtitles or auto-captions for the target video.

## 1. Audio Extraction

Download audio stream as mono 16kHz WAV file (required for whisper.cpp miniaudio and to prevent >4GB WAV header overflow on long streams):

```bash
yt-dlp -x --audio-format wav --exec "ffmpeg -i {} -ar 16000 -ac 1 -c:a pcm_s16le audio_16k.wav && rm {}" "VIDEO_URL" -o "temp_audio.%(ext)s"
```
Or convert existing audio:
```bash
ffmpeg -i audio.wav -ar 16000 -ac 1 -c:a pcm_s16le audio_16k.wav
```

## 2. Local Transcription

Run GPU-accelerated whisper.cpp build:

Check for `whisper-cli` in system PATH or local `$HOME/whisper.cpp` build directory:
- `$HOME/whisper.cpp/build/bin/whisper-cli`
- `$HOME/whisper.cpp/main`
- `$HOME/whisper.cpp/whisper-cli`

Model path defaults to `$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin`.

**Execution:**
```bash
~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-large-v3-turbo.bin -l th -f audio.wav --output-json -of whisper_output 2>&1
```
*(`-ot 540000` optional offset to skip silent start screens and avoid repetition loop bugs)*

For full build options and platform configurations, see [BUILD_GPU.md](BUILD_GPU.md).

## 3. Format Conversion

Convert whisper-cli raw JSON output to pipeline-standard `raw_transcript.json`:

```bash
python3 ../cleaning-auto-transcripts/scripts/clean_transcript.py whisper_output.json --format whisper --output raw_transcript.json
```

Then proceed with the standard pipeline (chunking, signal detection, subagents).
