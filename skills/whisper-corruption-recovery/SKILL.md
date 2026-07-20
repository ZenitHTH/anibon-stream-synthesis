---
name: whisper-corruption-recovery
description: Detect Whisper repetition-loop corruption in long audio, recover by splitting at corruption boundary, re-running on segments, and dedup-merging clean output.
---

# Whisper Corruption Recovery

Whisper on long audio (5h+) can enter repetition loops — same phrase repeats indefinitely from some point onward. This skill detects and recovers.

## Detection

Corruption signature: same N-word phrase repeats 3+ times with identical timestamps spacing.

```
powershell -c "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$json = (Get-Content -Encoding UTF8 'workspace\raw_transcript.json' -Raw | ConvertFrom-Json); `$last = `$json[-20..-1]; `$window = `$json[-100..-81]; `$repeat = 0; 0..(`$last.Count-1) | %% { if (`$last[`$_].text -eq `$window[`$_].text -and `$last[`$_].text.Length -gt 5) { `$repeat++ } }; Write-Host \"Repeat ratio: `$(`$repeat/`$last.Count)\""
```

Ratio >0.5 = corrupted. Note the start time of the first repeat entry (= corruption boundary).

## Recovery

1. **Split audio at corruption boundary** using ffmpeg:
```
ffmpeg -i workspace\full_video.mp4 -ss 02:35:00 -acodec pcm_s16le -ar 16000 workspace\tail_raw.wav
```

Or split into N equal segments from boundary to end:
```
ffmpeg -i workspace\tail_raw.wav -f segment -segment_time 900 -c copy workspace\tail_%02d.wav
```

2. **Re-run Whisper on each segment**:
```
whisper workspace\tail_01.wav --model large-v3-turbo --language th --output_dir workspace
```

Use `--temperature 0.2` and `--compression_ratio_threshold 2.0` on segments still showing corruption.

3. **Merge** clean segments. Dedup by timestamp: if segment B starts before segment A ends, only keep entries from B with timestamps > last A timestamp.

```powershell
# Simple dedup merge (PowerShell one-liner pattern):
Get-ChildItem workspace\tail_*.json | Sort-Object Name | % { 
  $data = (Get-Content -Encoding UTF8 $_.FullName -Raw | ConvertFrom-Json)
  $data | ? { $_.start -gt $lastTs } | % { $_; $lastTs = $_.start }
}
```

4. **Re-chunk** merged transcript with original block/overlap for downstream analysis.

## Prevention

For future streams ≥ 2h: never run Whisper on full audio. Process in 10-min segments from the start with overlap. Stitch clean. Corruption in one segment only costs that segment, not entire tail.

## Integration

Load before `anibon-timestamper` when:
- Stream ≥ 4h. Long audio = higher corruption risk.
- Raw transcript has suspiciously short total entries (< 100 for 1h audio).
- Last 50 transcript entries are nearly identical text.

## Iron Rules

- Never re-run Whisper on the full audio file. Split first.
- Verify segment duration with `ffprobe` before re-running.
- Dedup by timestamp, not by text (legitimate repeated phrases exist in gameplay).
- If `full_video.mp4` unavailable, re-download with `yt-dlp -f bestaudio`.
