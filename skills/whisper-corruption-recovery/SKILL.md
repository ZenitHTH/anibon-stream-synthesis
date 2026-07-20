---
name: whisper-corruption-recovery
description: Use when Whisper transcription contains repetition loops, repeated identical phrases, or the last N entries of a long-audio transcript are nearly identical.
---

# Whisper Corruption Recovery

## Overview
Whisper on audio ≥2h can enter repetition loops — same phrase repeating indefinitely from a corruption boundary onward. Recovery requires split → segment → re-run → dedup-merge. Never re-run Whisper on the full file.

## Detection (REQUIRED before any analysis)

Corruption signature: last 20 entries match entries 100 lines back at >0.5 ratio.

```powershell
$j = (Get-Content -Encoding UTF8 'raw_transcript.json' -Raw | ConvertFrom-Json)
$last = $j[-20..-1]; $win = $j[-100..-81]
$r = 0; 0..($last.Count-1) | % { if ($last[$_].text -eq $win[$_].text -and $last[$_].text.Length -gt 5) { $r++ } }
Write-Host "Corruption ratio: $($r/$last.Count)"
```

>0.5 = corrupted. First repeat entry's `start` = corruption boundary.

## Recovery Sequence

1. **Split at boundary**: `ffmpeg -ss HH:MM:SS -i full_video.mp4 -acodec pcm_s16le -ar 16000 tail_raw.wav`
2. **Segment** (900s chunks): `ffmpeg -i tail_raw.wav -f segment -segment_time 900 tail_%02d.wav`
3. **Re-run per segment**: `whisper tail_01.wav --model large-v3-turbo --language th`
   If segment still corrupts: `--temperature 0.2 --compression_ratio_threshold 2.0`
4. **Dedup-merge by timestamp** (never by text):
   ```powershell
   gci tail_*.json | Sort Name | % {
     $d = (gc $_ -Raw -Encoding UTF8 | ConvertFrom-Json)
     $d | ? { $_.start -gt $lastTs } | % { $_; $lastTs = $_.start }
   }
   ```
5. **Re-chunk** merged transcript with original block/overlap.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Re-running Whisper on full file | Full re-run hits same corruption. Split first. |
| Dedup by text | Gameplay legitimately repeats phrases. Dedup by timestamp only. |
| Not checking for corruption | Required detection step before any downstream work on ≥2h audio. |
| Skipping segment verify | `ffprobe tail_01.wav` before re-run. Segment durations can drift. |

## Prohibitions

- Never re-run Whisper on the full audio file. Not "just to be safe", not "with different settings". Split first.
- "I'll run it on the full file with temperature changes" → Same corruption, different timing. Split is the only path.
- "The corruption is small, I'll just trim that section" → Trimming without clean re-run leaves gaps.
