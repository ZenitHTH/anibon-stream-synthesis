# Hardware, Endpoints & Runtime Tuning Reference

Load this reference when provisioning LM Studio / remote APIs, sizing VRAM on 16GB GPUs, tuning multimodal/webcam reaction flags, overriding `config.json`, running on Windows, or inspecting pause mechanics.

## 1. LM Studio Model Loading & Shared-Host VRAM Sizing

`/v1/models` lists models on disk, not those resident in VRAM. If inference starts without an active loaded model, calls time out after 60s or return `"Model is unloaded."`. Check resident models first:

```bash
curl -s --max-time 8 http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'
```

> **LM Studio Unreachable vs. Ollama `*:cloud` Trap**: If `100.115.25.30:1234` refuses or times out, check Tailscale status (an empty 5–8s probe reply can be UDP wake-up — retry once if `active`). If the desktop host is idle, ask the user to start LM Studio before falling back. **Never** point `process_chunks_local.py` at local Ollama `*:cloud` tags (e.g. `gemma4:cloud`): `HTTP 402: Payment Required` forces `lib/common/lmstudio.py` into blackout-recovery retries.

Load payload (`POST http://100.115.25.30:1234/api/v1/models/load`):

```json
{
  "model": "gemma-4-12b-it-qat@q4_k_xl",
  "parallel": 1,
  "context_length": 49152,
  "eval_batch_size": 1024,
  "flash_attention": true,
  "offload_kv_cache_to_gpu": true
}
```

- **2× Context Headroom Rule (`"context_length": 49152`, `"parallel": 1` — CRITICAL ANTI-HALLUCINATION)**: In Full-Context Prep-First mode (untrimmed transcript lines + full LiveChat + full World Identity + up to 24 storyboard frames + webcam peak/silence sheets + 4,096 output tokens), peak per-chunk token usage reaches `~20,000–24,500` tokens (average `~13,400`). Running at `24576` fills `81–98%` of the context window ("ปริ่มขอบ") and causes attention degradation and hallucinations. **Always double (`× 2`) the peak requirement to `"context_length": 49152` (48K, or `65536` / 64K)** with `"parallel": 1`, `"flash_attention": true`, and `"offload_kv_cache_to_gpu": true`. Because Gemma 4 12B uses Sliding Window Attention (SWA) on alternating layers, `49152` at `"parallel": 1` fits comfortably inside P100 16GB VRAM.
- **Verified 16GB Tesla P100 Full-Context Profile**: `gemma-4-12b-it-qat@q4_k_xl`, `"parallel": 1`, `"context_length": 49152`, `"context_checkpoints": 0`, `"eval_batch_size": 1024`, `"physical_batch_size": 1120`, `"offload_kv_cache_to_gpu": true` with CLI `--eval-batch-size 49152 --max-chunk-frames 24`.
- Always smoke-test with `--max-chunks 1` before launching a 50+ chunk run.

## 2. Model Selection Benchmark (Tesla P100 16GB)

Controlled A/B across 5 multimodal chunks (`22.5 min`, 25 Storyboard keyframes, LiveChat + `entity_glossary.json`, `--eval-batch-size 8192 --max-chunk-frames 6`):

| Metric / Dimension | `gemma-4-12b-it-qat@q4_k_xl` (Default) | `gemma-4-26b-a4b-it@q2_k_xl` |
|---|---|---|
| Architecture & Quant | 12B Dense, Q4_K_XL (QAT, 4 bpw) | 26B Total / 4B Active MoE, Q2_K_XL (2 bpw) |
| GGUF File Size | `6.93 GB` (`6,925,879,040` B) | `12.84 GB` (`12,838,138,581` B) |
| P100 VRAM Headroom | Safe at `context_length: 24576` (`90.50s` cold load) | OOM/drops at `24576` (`12.84 GB` + `mmproj` + KV > `14.5 GB`); requires `<= 16384` (`209.11s` load) |
| 5-Chunk + Pass 2 Wall Time | `293.24s` (`~48.9s` / call) | `172.89s` (`~28.8s` / call, 1.70× faster) |
| Pass 1 Topic Recall | **10 stamps** — `4/5` chunks detect `is_continuation: false` shifts | **7 stamps** — locks `is_continuation: true` across chunks `01`–`04`, drops 3 sub-topics |
| Proper Noun Retention | Retains `มาซึากะดันโจ` (`00:15:12`), `มาโฮโย` IMAX (`00:19:44`) | Collapses `มาโฮโย` to generic `"การรอชมอนิเมะในโรง IMAX"`; fixes `"Cero Nightman"` → `"Chaos Zero Nightmare"` |
| Pass 2 Summarizer & Gates | Occasional heuristic part fallback (`⚠️ Header appears truncated`); **0** verb warnings | Clean JSON headers, but over-splits 6 stamps into 3 micro-parts (`3L, 2L, 1L`) and repeats `"เม้าท์มอย"` (`>20%`) |

**Decision Rules:**
1. Default to `gemma-4-12b-it-qat@q4_k_xl` (`google/gemma-4-12b-qat`) for Pass 1: 4-bit QAT preserves `is_continuation` shift sensitivity, Thai proper-noun recall, and 16-frame VRAM stability.
2. When using `gemma-4-26b-a4b-it@q2_k_xl`, cap `"context_length": 16384` (never `>= 24576` with vision on 16GB VRAM) and audit for swallowed sub-topics caused by sticky `is_continuation: true`.

## 3. Remote / TokenMe Endpoints & Config Overrides

- **Endpoint Auto-Probe**: `lib/common/lmstudio.py` (`resolve_endpoint()`) probes `http://100.115.25.30:1234` (1.0s TCP socket) and automatically falls back to `http://127.0.0.1:1234` when unreachable.
- **TokenMe & OpenAI-Compatible Remotes**: Target `--endpoint https://api.tokenme.limited/api/v1/chat/completions` (or `api.tokenme.limited`) with `TOKENME_API_KEY` / `LM_API_KEY` or `--api-key`:
  - **Max 8 Images**: Remote endpoints enforce `<= 8` images/request. Pass `--max-chunk-frames 8` (runner also auto-subsamples `<= 8` for TokenMe URLs).
  - **Case-Sensitive Model IDs**: Slugs are strictly case-sensitive (`google/gemma-4-31b-it`; `31B` returns HTTP 400 `Model not found`). Query `GET /api/v1/models` on 400 errors.
  - **HTTPS Recovery & Routing**: `_wait_for_network_recovery` resolves implicit port `443` (`https://`) and `80` (`http://`) before `1234`. Both `/v1/chat/completions` and `/api/v1/chat/completions` route automatically with `Authorization: Bearer <KEY>` and browser `User-Agent` (Cloudflare WAF code 1010 bypass). Vision uses base64 `image_url` payloads.
- **Configuration (`config.json` & `--config`)**: Numeric defaults, timeouts, temperatures, pruning bounds, and multimodal settings live in `skills/anibon-timestamper-local/config.json` and load via `lib/common/config.py` (zero dependencies). Keep secrets in gitignored `.env`. Override per run via `--config /path/to/config.json` (`--env-file` alias) or env vars (`ANIBON_CHUNK_MAX_TOKENS`, `ANIBON_TEMPERATURE`, etc.).

## 3.5 Remote `audio.cpp` & `whisper.cpp` Servers (P100 Host)

- **`audio.cpp` (`100.115.25.30:8080`)**: Set `AUDIOCPP_URL="http://100.115.25.30:8080/v1/tasks/run"` and `USE_AUDIOCPP=1` (or pass `--audiocpp-url` to `scripts/enrich_chunks.py`).
- **`whisper.cpp` (`100.115.25.30:8082`)**: Set `WHISPER_ENDPOINT="http://100.115.25.30:8082/inference"` for both `enrich_chunks.py` and Stage 3 `whisper_dispatcher.py`.
- **Crash / VRAM Contention Check**: Probe `GET http://100.115.25.30:8082/` and test one `audio_slices/cluster_*.wav` via `curl -F file=@...` if Stage 3 logs curl exit `56`/`28`. When `whisper-server` shares 16GB VRAM with LM Studio (`google/gemma-4-12b-qat`), transient crash/restarts can drop early slices (`cluster_000`–`002`); if `8082` remains down, omit `WHISPER_ENDPOINT` to fall back to local `whisper-cli` (`ggml-large-v3-turbo.bin`).

## 4. Multimodal Storyboard Tuning (`--multimodal-chunks`)

Storyboard keyframe sampling is enabled by default (`"multimodal_chunks": true`). Key tuning flags:

```bash
# Tune adaptive frame budget & sensitivity:
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace \
  --eval-batch-size 12288 --max-chunk-frames 16 --scene-delta-threshold 0.06

# Fixed frame spacing (disable scene deduplication) or text-only opt-out:
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace --no-scene-dedup --max-chunk-frames 12
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace --no-multimodal
```

- **Token Budget vs. LM Studio Physical Batch (CRITICAL)**: LM Studio load payload `"eval_batch_size": 1024` is `llama.cpp`'s physical prefill batch size, whereas CLI `--eval-batch-size` sets the **combined text + image token budget** in `compute_frame_budget()` (`avail = eval_batch_size - text_tokens`, `260` tokens/frame). With `--live-chat` + World Identity active, `text_tokens` runs `~5,100–6,500`, so passing `--eval-batch-size 1024` or `4096` starves `avail` to `0` and clamps every chunk to **1 frame**. `config.json` defaults `"eval_batch_size"` to `16384` (and `"scene_delta_threshold": 0.12`); use `8192` (`--max-chunk-frames 6`) or `12288`/`16384` (`--max-chunk-frames 16` at `context_length >= 24576`).
- **Adaptive Selector (`scene_dedup=True`)**: Drops static talking-head screens to 1–2 frames; scales dynamic scenes up to `--max-chunk-frames` (16); pins frames on Thai deictic cues (`"ดูอันนี้"`, `"ในจอ"`, `"ตรงนี้"`, `"[?]"`); caches 16×9 432-byte RGB sidecars (`tile_XXXXXX.rgb`) alongside `.jpg` tiles.
- **`--no-resume` Clean Slate**: Automatically unlinks stale `recursive_outputs/chunk_*.json` files and clears any leftover `.pause` marker. Pass `--byte-cap` only when splitting sections under 3,500 bytes for single-comment YouTube pasting.

## 5. Webcam Reaction Gating & Mid-Stream Switch (`--reaction-verify`)

- **Verify-First Default**: Always run pre-chunk `scripts/enrich_chunks.py` + `--reaction-verify` first unless the user explicitly asks to skip verification. Download format `18` (`yt-dlp --extractor-args "youtube:player_client=android" -f 18 -o <ws>/video_360p.mp4`) once up front so `enrich_chunks.py` and `--reaction-verify` seek locally instead of firing 199+ remote `--remote-snap` HTTP requests (`enrich_chunks.py` skips all chunks silently if neither local media nor `--remote-snap` is present).
- **Free-Talk Tradeoff**: Because `--reaction-verify` on Free-Talk streams still runs VLM rewrites, audit `reaction_verify_log.json` closely in Stage 5 to revert emotion-verb saturation (`"ตกใจ"`) and verdict flips.
- **Built-in Dynamic Switching (when `--reaction-verify` is on)**:
  - **Pass 1 (`lib/video/dynamic_balance.py`, `lib/video/chunk_peak_select.py`)**: Calm chunks stay `tier="low"` (`webcam=0`). Switches to `medium`/`high` (`4–12` webcam frames) when `mean_mad >= 0.095` (`>= 0.135` high), `EMOTION_REACTION_CUES` match, or `max_audio_z >= 2.5` (`>= 2.0` with LiveChat echo).
  - **Pass 2 (`needs_reaction_verify`)**: Snaps only `[Reaction]` tags, active co-triggers (`triggers.has_any`), or `score_item_situations >= 2.0`.
- **Mid-Stream Switch Recovery (when a talk run started without `--reaction-verify`)**:
  1. Let Pass 1 finish (or park via `control_chunks_local.py <ws> pause`).
  2. Delete **only** affected `recursive_outputs/chunk_XX.json` (+ `frames/webcam_chunk/wc_*`) and `anibon_timestamper_state.json`.
  3. Re-run `process_chunks_local.py` **without `--no-resume`**, adding `--reaction-verify --remote-snap` (or local `video*.mp4`).

## 6. Windows Launchers & Pause Control Internals

**Windows (PowerShell / CMD):**

```powershell
python scripts\prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" --workspace "$HOME\youtube_<VIDEO_ID>_workspace" --format txt --block 150 --overlap 15 --live-chat
python -X utf8 skills\anibon-timestamper-local\scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th
powershell -ExecutionPolicy Bypass -File "skills\anibon-timestamper-local\scripts\launch_local.ps1" -Workspace "$HOME\youtube_<VIDEO_ID>_workspace" -Endpoint "100.115.25.30"
```

Add `--vision-verify` to inspect `[?]` / deictic markers when a local `video_360p.mp4` / `video.mp4` or `--video-file` is present.

```cmd
skills\anibon-timestamper-local\scripts\launch_local.bat "%USERPROFILE%\youtube_<VIDEO_ID>_workspace" 100.115.25.30 auto th
```

**Pause Control Mechanics (`control_chunks_local.py`, `lib/chunk/pause.py`):**
- `pause` (default `--timeout 180`, pass `--timeout 0` for non-blocking): verifies live `timestamper.pid` first (exits `1` without writing `.pause` if dead/stale), creates `<workspace>/.pause`, and waits for `"phase": "paused"` in `anibon_timestamper_state.json`. Pressing `Ctrl-C` during `pause` exits `0` while keeping `.pause` armed.
- **Checkpoints**: Parks cleanly after active chunk (`recursive`), active group (`group`), inside `_wait_for_network_recovery`, or `before assembly`, polling every `1.0s` with zero GPU/HTTP traffic.
- **Guards & Scope**: Only the worker prints `[pause]`/`[resume]` to `timestamper.log`. `launch_local.sh` refuses if already running while paused. PID liveness (`os.kill(pid, 0)`) targets POSIX active loops (`--summarize-only` runs one-shot without PID/pause tracking).
