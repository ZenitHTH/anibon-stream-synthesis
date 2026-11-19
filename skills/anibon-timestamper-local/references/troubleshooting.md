# Troubleshooting & Manual Fallbacks Reference

Load this reference when automatic LiveChat/Whisper/storyboard stages fail, when re-running/preserving an existing workspace, or when diagnosing runtime LM Studio / vision errors.

## 1. Manual LiveChat & Visual OCR Fallback (Edited VODs)

**4-Step Manual LiveChat Pipeline** (runs from plugin root):

```bash
yt-dlp --sub-langs live_chat --write-sub --skip-download "https://www.youtube.com/watch?v=<VIDEO_ID>" -o "<workspace>/%(id)s.%(ext)s"
python3 -X utf8 skills/anibon-livechat-analysis/scripts/parse_live_chat.py <workspace>/<id>.live_chat.json --chunk-minutes 90 --raw-events <workspace>/livechat_events.txt -o <workspace>/livechat_90/
python3 -X utf8 scripts/align_live_chat.py --events <workspace>/livechat_events.txt --chunks <workspace>/chunks/ -o <workspace>/livechat/
python3 -X utf8 scripts/analyze_555.py --livechat ~/youtube_<id>_workspace/livechat/ --index ~/youtube_<id>_workspace/livechat/livechat_index.json --out ~/youtube_<id>_workspace/mood_555.json
```

Outputs: `<workspace>/livechat/livechat_chunk_NN.txt`, `livechat/livechat_index.json`, `mood_555.json`.

**Visual Chat OCR Fallback** (when YouTube Studio trim permanently deleted `.live_chat.json`):

```bash
python3 -X utf8 skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py --video-id <VIDEO_ID> --range HH:MM:SS-HH:MM:SS -o <workspace>/visual_livechat_events.txt
python3 -X utf8 scripts/align_live_chat.py --events <workspace>/visual_livechat_events.txt --chunks <workspace>/chunks/ -o <workspace>/livechat/
```

## 2. Manual Whisper & Garbled Dictionary Sync

```bash
WHISPER_ENDPOINT="http://100.115.25.30:8082/inference" \
python3 scripts/whisper_dispatcher.py ~/youtube_<VIDEO_ID>_workspace \
    --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>" --verbose

python3 skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py \
    --from-notes ~/youtube_<VIDEO_ID>_workspace/garbled_notes.json \
    --workspace ~/youtube_<VIDEO_ID>_workspace
```

## 3. Workspace Re-Run & Selective Cache Hygiene

**Preserve Text-Only Output Before Multimodal Re-Run:**

```bash
cd ~/youtube_<VIDEO_ID>_workspace
cp -a . ~/youtube_<VIDEO_ID>_workspace_text_backup
cp anibon_timestamps.md anibon_timestamps_text_only.md
cp all_timestamps.txt all_timestamps_text_only.txt
mv recursive_outputs recursive_outputs_text_only && mkdir -p recursive_outputs
cp anibon_timestamper_state.json anibon_timestamper_state_text_only.json
rm -f anibon_timestamper_state.json all_timestamps.txt anibon_timestamps.md timestamper.pid
```

- **Full Clean Re-Run**: Pass `--no-resume` to unlink stale `recursive_outputs/chunk_*.json` and clear `.pause`.
- **Selective Cache Hygiene**: For map-grass or 1-frame webcam glitches, inspect `frames/webcam_chunk/wc_sheet_*`; delete **only** affected `recursive_outputs/chunk_XX.json` + matching `wc_*` / `wc_sheet_*` files instead of wiping healthy chunks.

## 4. Runtime Failure & Edge-Case Catalog

| Symptom | Cause | Fix |
|---|---|---|
| 60s stalls from LM Studio model eviction | LM Studio unloads Gemma 4 and reloads another model | Keep `--model auto`; `resolve_model` latches onto the active VRAM model. |
| Blank or truncated output from Gemma 4 | Output budget consumed in `reasoning_content` | Built-in prompt caps thinking `<2` sentences; regex extractor parses JSON from content or reasoning. |
| Phonetic ASR drift (`"นครโตะ"` vs `Naucrate`) | Thai ASR phonetic spelling error | Automatic: `process_chunks_local.py` loads `resources/default_mappings.json` + TF-IDF signal detection pre-prompt. |
| Vision says *"I cannot see an image or video"* | GGUF loaded without companion `mmproj-*.gguf` | Attach `mmproj` in LM Studio or `llama-server --mmproj`, or switch to unified vision model (`Qwen2.5-VL-7B`). |
| Finishes in 1s with `[skip] chunk_XX` after transcript edit | Cached `recursive_outputs/chunk_XX.json` + state file reused | Pass `--no-resume` or remove `recursive_outputs/` and `anibon_timestamper_state.json`. |
| Outro cut off 30–60 min before VOD end | `is_continuation=True` swallowed closing segment | Inspect final 5 minutes of `chunks/` for closing tokens and emit `[Ending]`. |
| `prepare_storyboard_slides()` extracts 0 slides from 20MB+ `.mhtml` | YouTube packages slides as `Content-type: image/webp` | `lib/process/multimodal.py` handles both `image/jpeg` and `image/webp` via FFmpeg without PIL. |
| `download_storyboard()` exits 0 with empty `slides_clean/` | Passed `--skip-download` with `-f sb0/sb1/sb2/sb3`, or empty dir false-positive | Never pass `--skip-download` for storyboards; check `clean_dir.is_dir() and any(clean_dir.glob("slide_*.jpg"))`. |
| `call_multimodal()` raises `KeyError: 'choices'` | Bare `http://host:1234` hit root instead of `/v1/chat/completions` | Normalize `url` to append `/v1/chat/completions`. |
| `yt-dlp -f sb0/sb1/sb2/sb3` reports `Requested format is not available` | VOD has no YouTube MHTML storyboard stream | Synthesize 960×540 3×3 slides from 144p video (`-f 160`, see below). |
| Summarizer/pruner fails HTTP 400 Bad Request | Positional arg 6 passed `timeout` into `call_local(..., system_prompt)` | Pass `timeout=` by keyword (`lib/common/lmstudio.py` also guards `isinstance(system_prompt, (int, float))`). |
| Need to pause for MTP speculative decoding / VRAM tweak | Changing LM Studio runtime config mid-run | Park via `control_chunks_local.py <ws> pause`, reconfigure, and `continue` (or relaunch same command) with zero re-billing. |
| `[multimodal] fallback to text-only for chunk_XX: The read operation timed out` | Remote latency spiked past `multimodal_timeout_sec` | Non-fatal: pipeline falls back to text-only for that single chunk and resumes multimodal on subsequent chunks. |
| Past hour 4, `tile_XXXXXX.jpg` shows events 5–7 min ahead of transcript/livechat | `lib/process/multimodal.py` defaults `sec_per_slide=88.94` vs MHTML `X.yt-dlp.Duration: 89.959916` (`+1.15%` drift) | Cross-check the burned-in LiveChat clock or `livechat/*.txt` inside tiles past hour 4 instead of trusting `tile_XXXXXX` seconds alone. |
| macOS `_wait_for_network_recovery` falsely treats remote host as down | Unconfigured Homebrew `tailscale` CLI vs Tailscale GUI app | Query `/Applications/Tailscale.app/Contents/MacOS/Tailscale status`. |

**144p (`-f 160`) Fallback Storyboard Synthesis** (when `sb0..sb3` unavailable):

```bash
yt-dlp -f 160 -o "$WORKSPACE/frames/video_144p.mp4" "https://www.youtube.com/watch?v=<VIDEO_ID>"
mkdir -p "$WORKSPACE/frames/slides_clean"
# Interval ~ total_duration_sec / (350 * 9) or ~1 frame every 10s:
ffmpeg -i "$WORKSPACE/frames/video_144p.mp4" -vf "fps=1/10,scale=320:180,tile=3x3" -q:v 3 "$WORKSPACE/frames/slides_clean/slide_%04d.jpg"
```
