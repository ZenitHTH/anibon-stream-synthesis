---
name: anibon-local-transcription
description: Transcribe YouTube audio locally using whisper.cpp when YouTube has no subtitles or auto-captions. Alternative path loaded by anibon-timestamper.
disable-model-invocation: true
---

# Anibon Local Audio Transcription

## Overview & Triggers

Use when YouTube has no subtitles or auto-captions for the target video.

## 1. Audio Extraction

Download audio stream directly as mono 16kHz 16-bit PCM WAV (avoids temporary files and >4GB WAV header overflow on long 8h+ streams):

```bash
# Direct single-pass extraction via yt-dlp + ffmpeg:
yt-dlp -f ba -x --audio-format wav --postprocessor-args "-ar 16000 -ac 1 -c:a pcm_s16le" -o "audio_16k.%(ext)s" "VIDEO_URL"
```

Or convert existing audio:
```bash
ffmpeg -i audio.wav -ar 16000 -ac 1 -c:a pcm_s16le audio_16k.wav
```

## 2. Local Transcription

Run GPU-accelerated whisper.cpp build:

Check for `whisper-cli` in system PATH or local `$HOME/whisper.cpp` build directory:
- `$HOME/whisper.cpp/build/bin/whisper-cli` (or `.exe` on Windows)
- `$HOME/whisper.cpp/main`

Model path defaults to `$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin`.

**Execution:**
```bash
# Linux/macOS
whisper-cli -m models/ggml-large-v3-turbo.bin -f audio_16k.wav -l th -ot 240000 -t 8 --output-json -of whisper_output

# Windows (Vulkan Device 0: RX 7600, or Device 1: Tesla P100):
C:\Users\peter\whisper.cpp\build\bin\whisper-cli.exe -m C:\Users\peter\whisper.cpp\models\ggml-large-v3-turbo.bin -f audio_16k.wav -ot 240000 -l th -t 8 --output-json -of whisper_output --print-progress
```
*(`-ot 240000` offset skips the first 4 minutes of standby/intro silence to avoid repetition loop bugs on silence).*

For full build options and platform configurations, see [BUILD_WHISPERCPP_GUILD.md](../anibon-timestamper/references/BUILD_WHISPERCPP_GUILD.md).

## 3. Format Conversion & Windows Invariants

Convert whisper-cli raw JSON output to pipeline-standard `raw_transcript.json`:

> [!IMPORTANT]
> **Windows UTF-8 Invariant**:
> 1. Windows default console encoding (`cp1252`/`charmap`) crashes when printing Thai text. Always run scripts with `python -X utf8`.
> 2. MSVC `whisper-cli` output can split multibyte Thai UTF-8 characters across segment buffer cuts. Always decode JSON with `errors="replace"`:
>    ```python
>    with open("whisper_output.json", "rb") as f:
>        data = json.loads(f.read().decode("utf-8", errors="replace"))
>    ```

```bash
python -X utf8 convert_whisper_and_chunk.py
```

Then proceed with the standard pipeline (chunking, signal detection, subagents).

## 4. Hallucination Detection & Recovery

Detect repetition loops / hallucinations via frequency analysis and auto-trigger recovery:

```bash
python3 scripts/detect_hallucinations.py whisper_output.json --audio audio_16k.wav -o recovered_transcript.json
```

