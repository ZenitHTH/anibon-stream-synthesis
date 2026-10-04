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
yt-dlp -f ba -x --audio-format wav --postprocessor-args "ExtractAudio:-ar 16000 -ac 1 -c:a pcm_s16le" -o "audio_16k.%(ext)s" "VIDEO_URL"
```

> [!NOTE]
> If YouTube returns `HTTP Error 403: Forbidden`, update yt-dlp first:
> ```bash
> yt-dlp --update
> ```

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

Convert `whisper_output.json` directly to pipeline-standard `raw_transcript.json`:

> [!IMPORTANT]
> **Windows UTF-8 Invariant**:
> 1. Windows default console encoding (`cp1252`/`charmap`) crashes when printing Thai text. Always run scripts with `python -X utf8`.
> 2. MSVC `whisper-cli` output can split multibyte Thai UTF-8 characters across segment buffer cuts. Always decode JSON with `errors="replace"`.

Run inline Python converter:
```powershell
python -X utf8 -c "
import json

def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'

with open('whisper_output.json', 'rb') as f:
    data = json.loads(f.read().decode('utf-8', errors='replace'))

items = []
for seg in data.get('transcription', []):
    text = seg.get('text', '').strip()
    if not text:
        continue
    offsets = seg.get('offsets', {})
    start_sec = offsets.get('from', 0) / 1000.0
    end_sec = offsets.get('to', 0) / 1000.0
    items.append({
        'text': text,
        'start': round(start_sec, 2),
        'duration': round(end_sec - start_sec, 2),
        'timestamp': fmt_ts(start_sec)
    })

with open('raw_transcript.json', 'w', encoding='utf-8') as out:
    json.dump(items, out, ensure_ascii=False, indent=2)
"
```

## 4. Hallucination Detection & Recovery

On livestreams $\ge 2\text{h}$, Whisper may loop on music or silence. Run parallel Divide-and-Conquer recovery:

```powershell
python -X utf8 ..\whisper-corruption-recovery\scripts\fix_hallucinations.py whisper_output.json audio_16k.wav --devices 0 -w 3 -o raw_transcript.json
```

Then run chunking with `prepare_video.py`:
```powershell
python -X utf8 scripts\prepare_video.py <VIDEO_URL> --workspace <WORKSPACE> --format txt --block 300 --overlap 30
```

