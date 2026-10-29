---
name: anibon-timestamper-local
description: Use when generating YouTube timestamps and topic summaries for long livestreams locally on a single GPU (such as NVIDIA Tesla P100 16GB, LM Studio, Ollama) without cloud API costs. For cloud/frontier models (Claude 3.5 Sonnet, Gemini Pro) with parallel subagents, use anibon-timestamper.
---

# Anibon Timestamper (Local P100 Edition)

## Overview

Local processing pipeline for generating YouTube timestamps and summaries from long livestreams via Dynamic Recursive Rolling Summary state-machines (`--mode recursive`) or group batching (`--mode group`), multi-modal context fusion, automatic tag normalization, and two-pass YouTube comment formatting.

## When to Use

- When processing livestreams locally on a single GPU (e.g. NVIDIA Tesla P100 16GB, Apple Silicon Metal, LM Studio, Ollama) without incurring cloud API costs.
- **For Cloud / Frontier Models**: If the user has cloud API access and wants high-concurrency subagent orchestration (Claude 3.5 Sonnet, Gemini 2.0 Pro), use **`anibon-timestamper`** instead.

## Companion Skills & Required Sub-Skills

- **`anibon-world-identity` (MANDATORY)**: Must be loaded whenever the stream covers gaming, anime, Pokémon, Tokusatsu, or pop-culture topics. The agent must verify character names, game titles, and terms against local references (`references/INDEX.md`, `atlas_fgo.db`, `pokemon.db`, `garbled_replacements.json`) before finalizing timestamps.
- **`anibon-livechat-analysis`**: Download, parse, and align YouTube LiveChat replays, or extract burned-in on-screen chat via vision OCR fallback. Provides dual-side perspective (streamer + watchers), SuperChat highlights, and viewer reaction peaks.
- **`whisper-corruption-recovery`**: Automatically invoked if Whisper transcription contains repetition loops or silence stutter.
- **`anibon-local-transcription`**: Used when YouTube has no subtitles or auto-captions to extract 16kHz audio and run local GPU whisper.cpp.

## Pipeline Architecture

Pipeline commands run from the plugin root directory (`anibon-stream-synthesis`). Shared CLI utilities live in `scripts/`; skill-specific runners live in `skills/anibon-timestamper-local/scripts/`.

| Stage | Script / Module | Inputs / Outputs | Description |
|-------|-----------------|------------------|-------------|
| **0. Noise Cleaning, Music Anchors & Pre-normalization** | `lib/process/signals/detector.py` (auto) | `garbled_replacements.json` + `default_mappings.json` → `music_anchors.json` | Strips ASR speaker markers (`>>`), sound effect tags (`[เพลง]`, `[Applause]`), music symbols (`♪`), extracts `music_anchors.json`, repetitive stutter loops, and corrects phonetic drift before chunk loading/signal detection. |
| **0.5 Knowledge Self-Reading** | `lib/process/knowledge_reader.py` (auto) | `signals.json` + `references/*.md` + DBs → `entity_glossary.json` | Self-reads domain markdown references matched in signals, queries local SQLite databases (`atlas_fgo.db`, `pokemon.db`), and builds chunk-filtered verified entity glossaries. Bypass via `--no-knowledge-reader`. |
| **1. Preparation & Chunking** | `scripts/prepare_video.py` | YouTube URL → `raw_transcript.json`, `chunks/*.txt` | Downloads subtitles and segments audio/transcript into overlapping chunks. Pass `--live-chat` to download & align chat in one step. |
| **1.5 LiveChat, Mood & Proactive Music Detection** | `scripts/align_live_chat.py` / `scripts/patch_music_chunks.py` / `lib/process/music/` | `livechat/`, `music_anchors.json` → `mood_555.json`, patched `chunks/*.txt` | Aligns LiveChat replay events to transcript chunks, auto-detects 555 bursts, proactively detects background songs via Stage 0 anchors and chat music density, and patches chunks with `[Song Context Briefing]` and DSP vocal isolation. |
| **2. Topic Segmentation (Pass 1)** | `skills/anibon-timestamper-local/scripts/process_chunks_local.py` | `chunks/`, `signals.json`, Storyboard keyframes (`--multimodal-chunks`), `livechat/` | Detects shifts/continuations, emits timestamps via local LLM/VLM with visual ground truth, LiveChat highlights, and mood tone hints. |
| **2.5 Vision Ground Truth (Optional)** | `lib/process/vision_verify.py` (`--vision-verify`) | `video_360p.mp4` + ambiguous stamps | Inspects on-screen video frames via local vision model for vague proper nouns or `[?]` tags before Pass 2 assembly. |
| **3. Summarizer & Assembly (Pass 2)** | `lib/process/summarizer.py` (auto) | `all_timestamps.txt` → `anibon_timestamps.md` | Clusters timestamps into cohesive macro-thematic parts (typically 4–6 parts) and snaps to transition cues (`find_best_boundary`). |
| **4. Garbled Collector & Whisper Ground Truth** | `scripts/whisper_dispatcher.py` (auto post-pass) | `garbled_notes_raw/` → `garbled_notes.json` → `garbled_replacements.json` | Automatically runs after summary: guards against attention collapse loops via `detect_repetition_anomaly`, slices audio on-the-fly, transcribes phonetic ground truth via local whisper.cpp, and auto-grows shared dictionary. |
| **4.5 Post-Recovery Timestamp Unpacking & Sync** | Manual / CLI Runner | `recovery_report_*.md` → `all_timestamps.txt`, `anibon_timestamps_full.md`, `anibon_timestamps.md` | When speech is recovered from music-polluted or garbled segments, unpacks coarse single-timestamp placeholders into granular reaction/dialogue entries ($\ge 45\text{s}$ spacing) and atomically synchronizes all three output files. |
| **5. Deterministic Parity Gates** | `lib/process/parity_gates.py` (auto post-pass) | `all_timestamps.txt`, `anibon_timestamps.md` | Runs front-tier parity checks: `scripts/audit_gaps.py` (enforces NO GAPS > 10m), `scripts/check_sections.py` (audits timestamp line counts [target 15–20, max 25 lines/part] and ASR garble patterns), and `scripts/validate_mood.py` (validates mood-bearing timestamps honour mood_555 verdicts). |

### Modular Library Architecture (`lib/`)

- `lib/process/livechat.py`: End-to-end LiveChat replay downloader (yt-dlp), raw event parser, chunk boundary aligner (`align_livechat_feed`), and mood pulse detection hook.
- `lib/process/multimodal.py`: Storyboard slide unpacking, adaptive scene-change & evaluation-batch keyframe selector (1–16 frames per chunk, 16×9 RGB sidecar caching, Thai deictic cue pinning), OpenAI-compatible multi-image payload construction, and VLM execution.
- `lib/process/knowledge_reader.py`: Automated domain knowledge discovery from `signals.json`, regex table/bullet entity parser, SQLite DB enricher (`atlas_fgo.db`, `pokemon.db`), and `entity_glossary.json` generator.
- `lib/process/timestamps.py`: Tag normalization (`TAG_REMAP`), timestamp line sanitization, collision guards ($\ge 45\text{s}$ spacing), window validation.
- `lib/process/lmstudio.py`: LM Studio & OpenAI-compatible client (TokenMe, vLLM, Ollama), model resolution (defaults to `gemma-4-12b-it-qat@q4_k_xl` or `unsloth/gemma-4-26b-a4b-it@q2_k_x`), text completions, Bearer auth, Cloudflare bypass, and multi-modal Vision API (`image_url` data URIs for Gemma 4 Vision, Qwen-VL).
- `lib/process/websearch.py`: Lightweight DuckDuckGo search with local JSON cache (`websearch_cache.json`) for zero-cost entity verification.
- `lib/process/prompts.py`: Recursive rolling summary and group batching prompts, World Identity reference injection, and search/vision context blocks.
- `lib/process/summarizer.py`: Pass 2 local summarizer with semantic & chronological deduplication and macro-thematic part assembly (typically 4–6 parts).
- `lib/process/state.py`: Checkpoint persistence (`anibon_timestamper_state.json`), chunk discovery, and multimodal loaders (LiveChat, 555 mood, activity).

### Multi-Layer Anti-Hallucination & Verification Architecture (4-Layer Defense)

Local smaller LLMs (e.g. 12B–27B) lack the vast parametric world knowledge of front-tier models, making them prone to phonetic guessing and hallucinated English titles. `anibon-timestamper-local` implements a deterministic 4-layer defense pipeline:

1. **Layer 1: Two-Stage Signal Detection & Chaining Weights (`signal_detector.py` / `lib/anibon/signal_detector.py`)**
   - **Stage 1 (Game Domain Identification)**:
     - Ingests video title, description, and tags from `info.json` via `extract_metadata_signals()`.
     - Dynamically discovers all reference markdown games in `anibon-world-identity/references/*.md` via `discover_reference_games()`.
     - Detects game presence via exclusive special words and title signals with chaining weights across sequential chunks.
     - Strips common Japanese character names (*Yuki*, *Rin*, *Ren*) and generic gaming standing words (*E*, *C*, *AP*, *FTK*, *E6*, *Preset*) from triggering false game candidates.
     - Decays candidate probabilities across chunks to preserve ongoing gameplay context while discarding weak tail noise (`prob < 0.15`).
   - **Chronology & Callback Validation**: Cross-checks detected game versions against `references/<Game>.md` to prevent retrospective streamer commentary from corrupting the active update title.
   - **Stage 2 (Entity Scoping via `allowed_sources`)**:
     - Scopes entity glossary queries and prompt context strictly to `allowed_sources` returned from Stage 1 candidates.
   - **Zero-Example Prompt Discipline**:
     - Prompt templates and few-shot examples must NEVER hardcode real game titles (*Wuthering Waves*, *Zelda*, *Bleach*) as static text; use abstract token placeholders (`<Game_A>`, `<Character_X>`) to prevent local models (e.g. Gemma 4 12B) from latching onto them as hallucinations.

2. **Layer 2: Pre-Inference Buffer Normalization & Scrubbing (`state.py`)**
   - Automatically scrubs ASR speaker drift (`ปู่บอท`, `ลุงบอท`, `ปู่โบต` → `ปู่โบ๊ต`) during chunk loading in `load_chunk_file()`.
   - Applies phonetic mappings from `default_mappings.json` before passing text to the LLM prompt.

3. **Layer 3: Anti-Guessing & Invariant Prompt Directives (`prompts.py`)**
   - Enforces `STREAMER IDENTITY` invariant: The streamer is exclusively `'ปู่โบ๊ต' (Boat)`. Never write `'ปู่บอท'`, `'ลุงบอท'`, or `'ปู่โบต'`.
   - Enforces `ANTI-GUESSING CONSTRAINT`: Never arbitrarily translate Thai phonetic loanwords into novel English spellings. If not found in `VERIFIED DOMAIN ENTITIES`, write phonetic Thai or describe the action in Thai. Never invent novel English proper nouns.
   - Enforces `POKÉMON NAMING RULE`: Pokémon entities must strictly follow `'ชื่อไทย (English Name)'` (Thai community/official name followed by English name in parentheses).
   - Enforces `CAVEMAN TIMESTAMP STYLE INVARIANT`:
     - NEVER start timestamp descriptions or section titles with `'ปู่โบ๊ต'`.
     - **Dynamic Recent-Verb Blacklist**: Extracts opening verbs from `recent_timestamps` and explicitly bans reusing them in the next chunk.
     - **No Redundant Title Suffixes**: When a whole section covers one main title, name specific characters/events rather than appending `'ใน <Title>'` to every line.
     - Use varied action-first or topic-first verbs: `ส่อง`, `ชำแหละ`, `เทียบ`, `เจาะลึก`, `เม้าท์มอย`, `สรุปดราม่า`, `กางทฤษฎี`, `รีวิว`, `พักเบรก`, `ปิดไลฟ์`.
     - Keep 100% of proper nouns while eliminating redundant conversational padding.

4. **Layer 4: Stage 5 Deterministic Auto-Sanitization (`process_chunks_local.py`)**
   - Automatically executes `sanitize_and_audit_timestamps()` during Pass 2 summary assembly.
   - Deterministically corrects residual speaker misspellings and canonical dictionary patterns (`garbled_replacements.json`, e.g. `Archen` → `Arcane`, `Victor` → `Viktor`).
   - **Lexical Diversity Sanitizer & Gate (`world_sanitizer.py` & `check_sections.py`)**: Deterministically rotates overused opening verbs (`วิเคราะห์`, `อึ้ง!`, `พูดถึง`) and audits that no single opening verb exceeds 2 consecutive lines or 20% of total stamps.
   - Audits timestamp lines for unverified capitalized Latin words against whitelisted tags and glossaries, raising deterministic audit warnings for suspect hallucinations.

---

## Execution Modes

### Mode 1: Recursive Rolling Summary (`--mode recursive`, Default & Recommended)
Pu Boat's discussions follow organic content flow rather than clock boundaries. A topic may last 3 minutes or 25 minutes.
- **`SAME_TOPIC`**: If Chunk $N$ continues the ongoing topic, it merges into the rolling summary without emitting a timestamp (0 timestamps).
  - **Long-Form Talk/News Exception**: If a monologue or societal debate continues across multiple chunks (>8–10 minutes without a stamp), the model MUST extract a distinct sub-angle or specific policy critique (1 timestamp) rather than leaving long blanks.
  - **Unbounded Chaining Summary Invariant**: `build_recursive_prompt()` and state persistence (`anibon_timestamper_state.json`, `recursive_outputs/chunk_XX.json`) must pass the full `rolling_summary` and `chunk_summary` text without hardcoded character truncation so multi-chunk topic context is never clipped.
- **`TOPIC_SHIFT` / Highlights**: When the topic shifts, it flushes previous context and stamps the shift. Emits 1 timestamp by default, 2 MAX per chunk ($\ge$45s apart).
- **Thematic Part Grouping**: Pass 2 summarizer groups timestamps by overarching thematic category into sequential integer parts (`ส่วนที่ 1, 2, 3...` typically 4–6 parts total) using `find_best_boundary` to snap part borders to streamer transition cues (e.g. `สรุป... และเตรียมเปลี่ยนไปคุย`, `เตรียมเริ่มเล่นเกม`). Over-splitting into 10–18 micro-parts is disallowed; cohesive topic discussions (e.g. complete series reviews or gaming sessions) remain unified in a single part for viewer navigation convenience. Consecutive same-game grinding is consolidated within 10 minutes while talk/news sub-topics use a 4-minute window.

### Mode 2: Fixed Window Groups (`--mode group`, Alternative)
Combines 4 chunks (~16–20 min) per group with chronological loop-breakers and collision guards.

---

## Core Pipeline & Quick Reference

### Quick Commands

#### 0. Denoising & Pre-normalization (Automatic)
Before any signal detection or LLM analysis, `clean_transcript_noise()` automatically cleans ASR artifacts (`>>`, `[เพลง]`, `♪`, character repetitions), and applies 2000+ Whisper ground truths from `garbled_replacements.json` and `default_mappings.json`. No manual invocation needed.

#### 0.5 Knowledge Self-Reading & Entity Glossary (Stage 0.5, Automatic)
Before processing chunks, `run_knowledge_discovery()` inspects `signals.json`, self-reads matched markdown references in `anibon-world-identity/references/*.md`, queries local databases (`atlas_fgo.db`, `pokemon.db`), and emits `<workspace>/entity_glossary.json`. Chunk prompts automatically filter relevant entities (capped to ~300 tokens) into the prompt context.
- To bypass entity glossary discovery: pass `--no-knowledge-reader`.


#### 1. Download & Chunk (Skip if chunks/chunk_00.txt exists)
**macOS / Linux:**
```bash
python3 scripts/prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" \
    --workspace "~/youtube_<VIDEO_ID>_workspace" \
    --format txt --block 300 --overlap 30
```

**Windows (PowerShell / Command Prompt):**
```powershell
python scripts\prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" --workspace "$HOME\youtube_<VIDEO_ID>_workspace" --format txt --block 300 --overlap 30
```

#### 1.5 Download & Align LiveChat (Optional but preferred)
Gives the local model the watchers' chat for its own chunk, so situation + emotion are read from BOTH talks and chat. Requires network; if a VOD has no `live_chat` subtitle, skip this step and rely on transcript-only emotion.

**Automated 1-Step (via prepare_video.py):**
```bash
python3 scripts/prepare_video.py "https://www.youtube.com/watch?v=<VIDEO_ID>" \
    --workspace "~/youtube_<VIDEO_ID>_workspace" \
    --format txt --block 300 --overlap 30 --live-chat
```

**Manual / Step-by-Step Execution:**
```bash
# 1. Download LiveChat replay (network required)
yt-dlp --sub-langs live_chat --write-sub --skip-download "https://www.youtube.com/watch?v=<VIDEO_ID>" -o "<workspace>/%(id)s.%(ext)s"

# 2. Parse to coarse chunks + a seconds-prefixed raw event feed
python3 -X utf8 skills/anibon-livechat-analysis/scripts/parse_live_chat.py <workspace>/<id>.live_chat.json --chunk-minutes 90 --raw-events <workspace>/livechat_events.txt -o <workspace>/livechat_90/

# 3. Align raw feed to transcript chunk windows
python3 -X utf8 scripts/align_live_chat.py --events <workspace>/livechat_events.txt --chunks <workspace>/chunks/ -o <workspace>/livechat/

# 4. Detect Thai-Laugh / Meme Pulses (auto-run by process_chunks_local.py or run manually)
python3 -X utf8 scripts/analyze_555.py \
  --livechat ~/youtube_<id>_workspace/livechat/ \
  --index ~/youtube_<id>_workspace/livechat/livechat_index.json \
  --out ~/youtube_<id>_workspace/mood_555.json
```

Output: `<workspace>/livechat/livechat_chunk_NN.txt` + `livechat/livechat_index.json` and `mood_555.json`.

**Fallback for Edited Livestreams / Missing `.live_chat.json` (Visual Chat Extraction):**
When a livestream has been trimmed or edited in YouTube Studio, YouTube permanently deletes the `.live_chat.json` chat replay track. Use `extract_visual_livechat.py` from `anibon-livechat-analysis` to OCR the burned-in chat overlay:
```bash
# 1. Spot-extract visual livechat for target chunk time range
python3 -X utf8 skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py \
  --video-id <VIDEO_ID> \
  --range HH:MM:SS-HH:MM:SS \
  -o <workspace>/visual_livechat_events.txt

# 2. Align visual raw event feed directly to chunk windows
python3 -X utf8 scripts/align_live_chat.py \
  --events <workspace>/visual_livechat_events.txt \
  --chunks <workspace>/chunks/ \
  -o <workspace>/livechat/
```

> [!NOTE]
> **Emoji Dictionary Reference**: Refer to [`references/anibon_emoji_dictionary.md`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/references/anibon_emoji_dictionary.md) for channel-exclusive emote mapping (`:_CunnyBoat:`, `:_MonkeyBoat:`, `:_Nerd:`, `:_shutup:`, `:Grind:`, `:_Ripfish:`, `:_noname:`, `:_What:`, `:_WOW:`, `:_Ahh:`, `:_Meh:`, `:_MoneyBoat:`, `:_Tahaan:`, `:_KonDee:`, `:_NeoSlim:`, `:_Slim:`, `:_BoatSOM:`) and YouTube global emotes to mood pulse weights.

#### 1.9 Verify Model is Resident in VRAM (MANDATORY)
`/v1/models` lists all models on disk, not those currently loaded in VRAM. If inference starts without an active model, calls will timeout after 60s or return `"Model is unloaded."`. Always check:
```bash
curl -s http://100.115.25.30:1234/api/v1/models | jq '.models[] | select(.loaded_instances | length > 0) | .key'
```
If empty, explicitly load the recommended profile before starting the run:
```bash
curl -s -X POST http://100.115.25.30:1234/api/v1/models/load \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-4-12b-qat",
    "context_length": 262144,
    "eval_batch_size": 1024,
    "flash_attention": true,
    "offload_kv_cache_to_gpu": true
  }'
```
Smoke-test with `--max-chunks 1` before launching a full 50+ chunk run.

#### 2. Run Timestamper Directly (Foreground)
**macOS / Linux:**
```bash
python3 -X utf8 skills/anibon-timestamper-local/scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
    --mode recursive --lang th
```

**Windows (PowerShell):**
```powershell
python -X utf8 skills\anibon-timestamper-local\scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th
```

> [!TIP]
> **Single Comment Byte Limit (`--byte-cap`)**:
> Pass `--byte-cap` if you need each part strictly under 3,500 bytes for YouTube single-comment pasting. By default, byte-capping is disabled to preserve cohesive macro-thematic grouping (4–6 parts).


#### 2.1 In-Pipeline Vision Verification (Optional)
Inspect on-screen video frames for ambiguous or vague timestamps (deictic pronouns, missing game names, `[?]` markers) using the local vision model before Pass 2 summary:
```powershell
python -X utf8 skills\anibon-timestamper-local\scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th --vision-verify
```

#### 2.2 Multimodal Chunk Analysis with Storyboard Keyframes (Default: Enabled)
Samples high-resolution Storyboard keyframes per chunk directly into the VLM (e.g. Gemma 4 12B Vision, Qwen-VL) alongside the transcript text during Pass 1. Enabled by default via `config.json` (`"multimodal_chunks": true`). Eliminates game title misattribution and grounds event/chapter subtitles in real time:
```bash
# Enabled by default (Adaptive Scene-Change Mode):
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace --mode recursive --lang th

# To tune visual sensitivity or evaluation batch size:
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace \
  --eval-batch-size 8192 \
  --max-chunk-frames 16 \
  --scene-delta-threshold 0.06

# To disable adaptive scene deduplication (fallback to legacy fixed 3-5 frames):
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace --no-scene-dedup

# To disable all multimodal analysis and run in text-only mode:
python3 skills/anibon-timestamper-local/scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace --no-multimodal
```

**Adaptive Scene-Change Keyframe Selector (`scene_dedup=True`):**
- **Static Screens**: Drops static talking-head / waiting screens down to 1–2 frames (saving physical batch compute and prompt tokens).
- **Dynamic Action**: Automatically expands up to 16 frames per 5-min chunk whenever visual scene transitions occur, bounded by `--eval-batch-size` (default `8192`).
- **Thai Deictic Cue Pinning**: Pins exact visual frames whenever Pu Boat uses deictic pointers (`"ดูอันนี้"`, `"ในจอ"`, `"ตรงนี้"`, `"[?]"`).
- **RGB Sidecar Caching**: Automatically persists 16×9 432-byte downsampled buffers (`tile_XXXXXX.rgb`) alongside `.jpg` tiles, eliminating repeated `ffmpeg` subprocess overhead across comparisons and reruns.
- **Clean-Slate `--no-resume`**: Passing `--no-resume` automatically unlinks stale `recursive_outputs/chunk_*.json` files to guarantee clean execution without leftover chunk contamination.

**Re-running an Existing Workspace while Preserving Previous Results (e.g. Text-Only → Multimodal):**
```bash
cd ~/youtube_<VIDEO_ID>_workspace
cp -a . ~/youtube_<VIDEO_ID>_workspace_text_backup
cp anibon_timestamps.md anibon_timestamps_text_only.md
cp all_timestamps.txt all_timestamps_text_only.txt
mv recursive_outputs recursive_outputs_text_only && mkdir -p recursive_outputs
cp anibon_timestamper_state.json anibon_timestamper_state_text_only.json
rm -f anibon_timestamper_state.json all_timestamps.txt anibon_timestamps.md timestamper.pid
```


#### 3. Detached Background Launch (3 OS Families)
Runs inference detached in background so agent sessions or timeouts do not kill the run.

**macOS / Linux (Bash):**
```bash
./skills/anibon-timestamper-local/scripts/launch_local.sh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File "skills\anibon-timestamper-local\scripts\launch_local.ps1" -Workspace "$HOME\youtube_<VIDEO_ID>_workspace" -Endpoint "100.115.25.30"
```

**Windows (CMD Batch):**
```cmd
skills\anibon-timestamper-local\scripts\launch_local.bat "%USERPROFILE%\youtube_<VIDEO_ID>_workspace" 100.115.25.30 auto th
```

> [!NOTE]
> **Endpoint Auto-Probe & Fallback Rule**: All runners and Python client (`anibon.lmstudio.resolve_endpoint()`) automatically probe `http://100.115.25.30:1234` with a 1.0s TCP socket test. If unreachable (indicating execution on localhost itself), they immediately and safely fall back to `http://127.0.0.1:1234`.

> [!TIP]
> **Remote / TokenMe Endpoint Support**:
> You can target remote OpenAI-compatible endpoints such as TokenMe (`--endpoint https://api.tokenme.limited/v1` or `api.tokenme.limited`) by passing `TOKENME_API_KEY` (or `LM_API_KEY`) in the environment or `--api-key`.
> - The client sets standard `Authorization: Bearer <KEY>` and browser `User-Agent` headers to bypass Cloudflare WAF code 1010.
> - Remote models like `nvidia/Gemma-4-26B-A4B-NVFP4` support multimodal vision inspection via base64 `image_url` payloads out-of-the-box.

> [!TIP]
> **Configuration (`config.json` and `--config`)**:
> Numeric constants, token limits, timeouts, temperatures, pruning bounds, and default endpoints are managed via `skills/anibon-timestamper-local/config.json` and loaded automatically by `anibon/config.py` with zero dependencies.
> - Secrets (like `TOKENME_API_KEY` or `LM_API_KEY`) belong in `.env` (which is gitignored).
> - To customize parameters for a specific run or hardware setup, copy or create a JSON config file and pass `--config /path/to/config.json` (or `--env-file` for backward compatibility).
> - Environment variables (`ANIBON_CHUNK_MAX_TOKENS`, `ANIBON_TEMPERATURE`, etc.) seamlessly override `config.json` values without touching files.

- **Section Splitting Rule (Line Count over Byte Count)**:
  - Macro-parts (`ส่วนที่ X`) are grouped and split strictly by timestamp line count.
  - **Target**: 15–20 lines/part. **Hard split limit**: > 25 lines/part.
  - Byte counting is canceled for section splitting decisions (avoiding false alarms from 3-byte Thai UTF-8 text).
  - Splitting snaps to the nearest topic transition marker or line midpoint (`len(stamps) // 2`).

#### 4. Garbled Collector & Whisper Ground Truth (Automatic Post-Pass)
After `anibon_timestamps.md` summary assembly finishes, `process_chunks_local.py` automatically checks for surviving phonetic garbles in `<workspace>/garbled_notes_raw/` and invokes `whisper_dispatcher.py` with local `whisper.cpp` to slice audio, aligns acoustic segments via `resolve_garbled_notes`, and updates `garbled_replacements.json`.

- **Garbled Collector Safety Rules**:
  - Rejects ASCII patterns `< 5` characters (`"ON"`, `"MDB"`) to avoid substring corruptions (e.g. `"Donghua"` → `"DNexonghua"`).
  - Rejects patterns where `garbled.lower() in target.lower()` (e.g. `"on"` in `"Nexon"`).
  - Rejects ungrounded LLM targets not found in dictionary, glossary, stream title, or Whisper audio segments.
  - Re-cleans both `chunks/*.txt` and `anibon_timestamps.md` upon updating the dictionary.

- To pass video URL for on-the-fly stream slicing without full audio downloads:
  ```bash
  python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
      --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>"
  ```
- To disable automatic garbled collection pass:
  ```bash
  python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
      --no-garbled-collector
  ```
- To run garbled collection manually at any time:
  ```bash
  python3 scripts/whisper_dispatcher.py ~/youtube_<VIDEO_ID>_workspace \
      --video-url "https://www.youtube.com/watch?v=<VIDEO_ID>" --verbose
  python3 ../cleaning-auto-transcripts/scripts/update_garbled_dictionary.py \
      --from-notes ~/youtube_<VIDEO_ID>_workspace/garbled_notes.json \
      --workspace ~/youtube_<VIDEO_ID>_workspace
  ```

#### 5. World Identity & Fact Verification Audit (Mandatory Pass)
Immediately after generating `all_timestamps.txt` and `anibon_timestamps.md`:
1. **Load `anibon-world-identity`**: Scan all emitted timestamp titles and descriptions against local knowledge bases:
   - **FGO Servants / Classes**: Query `atlas_fgo.db` (do NOT confuse Ashiya Douman with Ascalon/Asclepius).
   - **Pokémon Entities**: Query `pokemon.db` and enforce Thai community/official names first (e.g. `แบกซ์แคลิเบอร์ (Baxcalibur)`).
   - **Anime / Gacha Titles**: Verify against `references/*.md` (e.g. `Chaos_Zero_Nightmare.md`, `Genshin_Impact.md`, `Honkai_Star_Rail.md`, `Wuthering_Waves.md`).
   - **Unfamiliar Indie / Web / Thai Games**: If the streamer plays an unindexed game genre (e.g. probability life sims like *1 in 8 Billion*, *1 ชีวิต ณ กรุงศรี*, *หนึ่งในอสงไขย*), research and scaffold `references/<Topic>.md` first, then reconstruct timestamps directly from `raw_transcript.json`.
   - **New Competitive Games (Deadlock, etc.)**: Cross-reference hero names (Baba / Baba Yaga, Celeste, Abrams) via web search or patch notes.
2. **Audit Against `raw_transcript.json` for 4 Local-Model Distortion Patterns**:
   - **Domain Context Bleeding**: Check non-gaming talk segments adjacent to gaming segments. Local 12B models often distort general words (e.g. `"บริษัทนั้น"` in a food/political news story) into `"บริษัทเกม"`. Verify the actual subject in `raw_transcript.json`.
   - **Comparative Analogy Promotion**: When a secondary title (e.g. *Heaven Burns Red*, *Yu-Gi-Oh! GX*, *Bleach*) appears in a section dedicated to another main topic (e.g. *Wuthering Waves*), verify whether it was only used as a comparative example (e.g. ensemble cast or companion writing) and frame the timestamp around the primary topic.
   - **Gameplay vs. Gacha Pulling Transitions**: During gameplay segments of gacha games (*Nikke*, *Arknights: Endfield*, *WuWa*), check the transcript for gacha pull keywords (`หลุดเรท`, `ตู้ถาวร`, `เพชรหมด`, `Token Exchange`) so gacha sessions are not mislabeled as continuing gameplay mechanics (e.g. factory/belt building).
   - **Dual-Track Desync (Gameplay State vs. Talk Topic)**: Pu Boat often sets up an in-game action (summoning mobs to fight each other, AFK farms, long crafts, waiting for a boss) and then talks about something unrelated for 5–40 minutes while it runs. Track both every time:
     1. **Gameplay Track**: Find the *plan statement* that explains the current scene. Search the transcript backward (up to ~20 min) for intent verbs (`เดี๋ยวให้มันสู้กัน`, `รอ`, `ปล่อยไว้`, `เสก`, `ล่อ`). Confirm it with storyboard frames: quest tracker text, boss bar name, and the mobs actually present. A creature on screen does NOT mean Boat is fighting it.
     2. **Talk Track**: Find the topic Boat is actually speaking about (donations, news, Q&A).
     3. **Label Rule**: If both tracks run at the same time, write one stamp that names both. Use the talk tag when speech dominates, and keep the game state as context (e.g. `[Talk] เฝ้า <Mob_A> สู้กับ <Mob_B> พร้อมถกประเด็น <Topic>`). Never drop either track. Close the gameplay arc with a payoff stamp when it resolves (e.g. loot collected, quest completed).
3. **Apply Entity & Chronology Corrections**: Correct phonetic drifts, inverted topic order, or LLM hallucinations directly in `anibon_timestamps.md`, and verify spacing ($\ge 45\text{s}$ min gap, $\le 600\text{s}$ max gap).
4. **Persist Knowledge**:
   - Add confirmed phonetic drift patterns (e.g. `เคราสเซียร์นี้แม่` → `Chaos Zero Nightmare`, `อัชเฉร้อน` → `อาชิยะ โดมัน`) to `garbled_replacements.json` across root and skill resources.
   - Add newly verified franchises/characters to `anibon-world-identity/references/`.


---

## Discipline & Anti-Rationalization

### The Iron Rule of Local Processing

```
NEVER TIME-LOCK TOPICS TO ARBITRARY MINUTE BOUNDARIES
```

Livestreams flow organically. Use the Recursive Rolling Summary state-machine to detect true content shifts rather than stamping every $N$ minutes.

### Rationalization Table

| Rationalization | Reality | Counter-Measure |
| :--- | :--- | :--- |
| *"Single chunk is faster to run."* | Produces 35+ micro-stamps that clutter comment sections. | Use `--mode recursive` with rolling summaries. |
| *"I can invent tags like [วิเคราะห์] because it fits the content."* | Front-tier benchmarks reject non-standard tags; breaks comment parsers. | Normalizer automatically remaps `[วิเคราะห์]` → `[Talk]`. |
| *"I'll just summarize the whole 3-hour transcript in 1 prompt."* | Exceeds context and degrades entity recall on 12B models. | Sequential rolling state-machine keeps prompt under 2k tokens. |
| *"Let's write a custom Python script to speed this up."* | Ad-hoc scripts break state tracking, resume logic, and encoding. | Strictly use `process_chunks_local.py` flags. |
| *"The timestamps look good enough without checking World Identity."* | Hallucinates post-cutoff games or uses bare English Pokémon names without community Thai transliteration. | Strictly invoke `/anibon-world-identity` gate before final handoff. |

### Red Flags — STOP and Reset
- Delivering timestamp output to user without verifying franchise entities against `/anibon-world-identity`.
- Attempting to run timestamper before transcript recovery pipeline is 100% complete and validated (`whisper-corruption-recovery`).
- Output file contains 35+ timestamps for a 2-hour stream (micro-stamping symptom).
- Output tags include non-whitelisted words (`[วิเคราะห์]`, `[ชำแหละ]`, `[เปิดตัว]`).
- Over-splitting topics into excessive micro-parts (>6–8 parts for a stream). Viewer navigation and thematic cohesion take precedence over artificial comment byte limits.
- Script crashes with `UnicodeEncodeError: 'charmap'` (forgot `-X utf8`).
- Outro omitted when ending chunk is marked continuation. Always verify final 5 minutes for closing stamp.
- Attributing endgame mechanics ("หอรี", "เฟ้อกว่าเวเนซุเอลา") to a previously discussed game when a new game was booted up.
- Hallucinating unmentioned lore/chapter titles (e.g., "Lostbelt") solely due to pre-training association with a franchise.
- Labeling viewer donation alerts with custom avatars as literal product reviews or figure showcases (`[Talk] โชว์ฟิกเกอร์`).
- Labeling a stamp `[Gameplay] สู้กับ X` only because X appears in a frame, without verifying the boss bar, quest HUD, or the streamer's stated plan. Equally wrong: replacing it with a pure `[Talk]` stamp that erases the running game state.

### Pre-Roll Standby / Waiting Screen Invariant
If the opening transcript (chunk 00) contains predominantly `[เพลง]`, sound effect markers, or isolated foreign ASR phonetic tokens (Japanese, Korean, English lyrics) before the streamer speaks the first coherent Thai sentence:
- MUST mark `00:00:00 - [Intro]` (e.g. `00:00:00 - [Intro] เปิดไลฟ์ทักทายยามเย็น...`).
- Anchor the first topical timestamp strictly to the streamer's opening Thai speech.
- NEVER infer stream topics, reactions, or anime titles from background waiting music (e.g. mistaking opening waiting BGM for "ดูอนิเมะสาวน้อยเวทมนตร์").

### Stream Ending / Outro Invariant
In `--mode recursive`, long unbroken gameplay or concluding sessions must not allow `is_continuation=True` to swallow the stream outro.
The final 5 minutes of transcript must always be checked for closing tokens (`ขอบคุณครับ`, `ลงไลฟ์`, `ราตรีสวัสดิ์`, `เจอกัน`, `บ๊ายบาย`) and emit:
1. **SuperChat / Birthday Shoutouts**: Use `[Donation]` for reading donor lists, SuperChats, and member birthday blessings (`HH:MM:SS - [Donation] อ่านโดเนท ขอบคุณผู้สนับสนุน และอวยพรวันเกิดสมาชิก`).
2. **Closing Sign-off**: Use `[Ending]` for the final wrap-up statement and next-stream announcements (`HH:MM:SS - [Ending] กล่าวปิดสตรีมและแจ้งกำหนดการไลฟ์รอบถัดไป...`). Do NOT begin descriptions with `'ปู่โบ๊ต'`.
3. **Recurring Live Routine Guardrail**: Pu Boat frequently schedules a 22:00 Tokusatsu stream ("ไลฟ์โทกุ", "คอนเทนต์โทกุ 3 เรื่อง 3 รส"). Phonetic ASR artifacts (`โทกกู`, `ทั่วกุ`, `คอนเทนทุกคึ`) must strictly map to `โทคุซัตสึ (Tokusatsu)`, NEVER "Tokyo Ghoul".

### Macro-Thematic Part Grouping Invariant (No 3,500-Byte Cap Over-Splitting)
Timestamps are grouped strictly into broad, cohesive macro-thematic parts (typically 4–6 parts for a long stream).
Prioritize viewer navigation and thematic cohesion: keep related discussions (such as an entire series review, media watchparty, or gaming session) unified in a single part rather than arbitrarily slicing into 10–18 micro-parts to fit single-comment byte limits.
`assemble_parts()` and `run_local_summarizer_pass()` do not enforce byte caps by default. `enforce_byte_cap()` is retained as an opt-in utility only if single-comment splitting is explicitly requested.

### Essential Curated Timestamps Selection Invariant
When generating timestamps from long livestreams (4–8 hours), follow these operating standards:
1. **Primary Output Focus**: Present the primary result as a curated essential edition (~40–60 timestamps for a 7–8 hour stream, or approximately 8–15 stamps per macro-thematic part).
   - **Automated Essential Pruning (`prune_essential`)**: For streams yielding >60 timestamps, `finalize_and_assemble_timestamps()` automatically queries the local model to distill essential pivot points, news, gameplay milestones, and core conclusions down to ~40–60 stamps. The pipeline enforces strict verbatim matching against raw timestamps, guarantees retention of opening and `[Ending]` timestamps, and falls back cleanly if the LLM call fails.
     > [!NOTE]
     > If `prune_essential` fails to extract matches (e.g. local 12B model emits modified text that fails verbatim matching), the pipeline falls back to the full timestamp list. Reviewers should manually prune micro-talk stamps down to essential milestones before delivery.
2. **Essential Selection Criteria**:
   - Major topic starts or pivot points (Topic Shift / Pivot).
   - Official news, announcements, releases, or statistical data (Official News, Releases, Data).
   - In-depth analytical conclusions and core takeaways (In-depth Analysis & Core Takeaways).
   - Key gameplay milestones (tutorial start, exploring new characters/skills, key item crafting, boss spawns, highlight fights, victory/defeat).
   - Stream outro and closing thanks (Stream Outro).
3. **Pruning Micro-Stamps**:
   - Prune micro-talk stamps repeating the same talking point within a short window (e.g. if the streamer dissects a point for 5–10 minutes, do not place stamps every 2 minutes).
   - Prune casual chat chatter, minor jokes, or banter that does not impact the core narrative.
   - **Wrap Same-Topic Clusters**: Consolidate consecutive stamps that belong to the same topic group into a single comprehensive timestamp.
   - **Skip Fleeting Micro-Talk**: Never create a timestamp for an offhand reaction or passing thought spanning only 2–3 sentences (e.g. praising how a game translated a boss name into Thai).
4. **Dual-File Storage**:
   - Save the curated essential timestamps file to `anibon_timestamps_essential.md` (or `anibon_timestamps.md`).
   - Retain the exhaustive, full chronological timestamp log in `anibon_timestamps_full.md` (and `all_timestamps.txt`) for reference and archival lookup.

### Macro-Topic Boundary Snapping Invariant

Major domain/topic transitions (e.g. Thai Politics → Anime/Series review, Gaming → SuperChat Q&A) MUST NOT begin with 1–4 straggler stamps at the tail of an unrelated topic section.
`assemble_parts()` automatically snaps partition boundaries to transition markers (`สรุปการพูดคุย... และเตรียมเปลี่ยนไปคุย`, `เตรียมเริ่มเล่นเกม`, `เตรียมเข้าสู่ช่วง`) using `find_best_boundary()`. This ensures viewer-friendly, clean topical grouping without stragglers.

### Timestamp Lead-in & Analogy Attribution Invariant
1. **Lead-in Anchor**: The start time of a timestamp must always anchor to the opening sentence of the topic. Never mark the timestamp at or after the keyword appears mid-sentence, ensuring viewers who click the link do not miss critical context spoken 10–20 seconds earlier.
2. **Off-hand Analogy Rule**: Never use the name of a work, person, or place mentioned only briefly in passing (1–2 sentences) as an analogy or rhetorical comparison as the main title of a timestamp.
   - *Incorrect*: `Comparing standards... with Frieren` (when the topic is a critique of One Punch Man Season 3 and Frieren was only mentioned in a single comparative sentence).
   - *Correct*: `Critiquing One Punch Man Season 3 and J.C.Staff's 'watchable' standard (noted that it cannot compare to major productions like Frieren)`.


### World Identity Audit Invariant
NEVER deliver the final timestamp output without performing an `anibon-world-identity` audit on all proper nouns, game titles, and character names. Thai Whisper outputs are phonetic; local LLMs hallucinate well-known games (Genshin, Dota) when hearing unfamiliar ones (CZN, Deadlock). Local references (`references/*.md`) and card/entity databases (`atlas_fgo.db`, `pokemon.db`) take strict precedence over model memory. `process_chunks_local.py` automatically audits generated `anibon_timestamps.md` against `<workspace>/entity_glossary.json` upon completion to replace confirmed phonetic variants.

### Stream Title Token Grounding Invariant
Proper nouns, mod names, and franchise titles in the stream's own YouTube metadata (`info.json` title, description) are ground-truth anchors.
1. **Title Token Priority**: When an emitted timestamp description contains a phonetic near-match or truncated form of an entity present in the stream title (e.g. ASR transcribed `Vity` while the title explicitly specifies `Verity`, or `Nania` vs `Narnia`), the pipeline must deterministically snap to the title's canonical spelling.
2. **Title vs. ASR Phonetic Drift**: Stream titles reflect the streamer's deliberate broadcast topic. ASR phonetic drift within the video must never overwrite or degrade entities verified in the title.

### LiveChat Dual-Side & Mood Invariants
1. **READ BOTH SIDES Invariant**: When `livechat/` exists, prompt context automatically loads `LiveChat Highlights:` (prioritizing SuperChats, donations, and direct questions to Pu Boat). The model must evaluate both streamer dialogue and audience reactions to prevent one-sided factual misinterpretations.
2. **HONOUR THE MOOD VERDICT Invariant**: When `mood_555.json` exists, each chunk receives `Viewer Reaction:` mood classification and Thai tone hints (`tone` + suggested `verbs`). The model keeps its own verb creativity, but must not flatline high-energy meme peaks (`MEME_PULSE`, `SHOCK_HYPE_PULSE`) into dry, detached monologues.

---

## Common Mistakes & Troubleshooting

1. **LM Studio Model Eviction**:
   - *Symptom*: LM Studio unloads Gemma 4 and reloads another model, causing 60-second stalls.
   - *Fix*: Keep `--model auto`. `resolve_model` automatically latches onto the active in-memory model.

2. **Gemma 4 Thinking Token Trap**:
   - *Symptom*: Output timestamp is blank or truncated.
   - *Cause*: Model used token budget in `reasoning_content`.
   - *Fix*: Built-in system prompt limits thinking to <2 sentences; regex extractor extracts structured JSON directly from content or reasoning.

3. **ASR Phonetic Drift**:
   - *Symptom*: Names like "นครโตะ" appear instead of "Naucrate (นอคราเต้)".
   - *Fix*: `process_chunks_local.py` loads `resources/default_mappings.json` and runs TF-IDF signal detection before prompt generation.

4. **Missing Multimodal Projector (`mmproj`) on Vision Prompts**:
   - *Symptom*: Image verification or storyboard inspection responds with *"I cannot see an image or video"*.
   - *Cause*: Model GGUF has multimodal prompt tokens but was loaded into LM Studio / `llama.cpp` without its companion `mmproj-*.gguf` file.
   - *Fix*: Explicitly attach the `mmproj` file in LM Studio model settings or `llama-server --mmproj`, or switch to a unified vision model like `Qwen2.5-VL-7B`.

5. **Re-running with Modified/Recovered Transcript**:
   - *Symptom*: Timestamper finishes in 1 second showing `[skip] chunk_XX (already processed)`.
   - *Cause*: Script caches per-chunk responses in `<workspace>/recursive_outputs/chunk_XX.json` as well as `anibon_timestamper_state.json`.
   - *Fix*: Pass `--no-resume` and remove `recursive_outputs/` and `anibon_timestamper_state.json`.

6. **Outro Swallowed by Continuation Trap**:
   - *Symptom*: Output timestamp stops 30–60 minutes before video end, missing streamer's closing remarks.
   - *Cause*: `is_continuation=True` in recursive rolling mode treated the final session as unbroken gameplay, discarding outro.
   - *Fix*: Outro invariant — final 5 minutes must always be scanned for `[Ending]` / farewell stamps.

7. **Storyboard MHTML with WebP Content-Type**:
   - *Symptom*: `prepare_storyboard_slides()` extracts 0 slides despite `storyboard.mhtml` being downloaded (20MB+).
   - *Cause*: YouTube's `yt-dlp` often packages multipart storyboard slides with `Content-type: image/webp` (`RIFF...WEBP`) rather than `image/jpeg`.
   - *Fix*: `anibon/multimodal.py` checks both `image/jpeg` and `image/webp`. FFmpeg crops tiles from either format to high-res JPEG output without requiring PIL.

8. **`yt-dlp` Storyboard `--skip-download` Trap & Empty Slide Directories**:
   - *Symptom*: `download_storyboard()` exits 0 but produces no `.mhtml` file, or `prepare_storyboard_slides()` returns an empty `slides_clean/` directory.
   - *Cause*: Unlike `--write-auto-subs --skip-download`, storyboard (`-f sb0/sb1/sb2/sb3`) is the primary format; passing `--skip-download` skips downloading it entirely. Checking `clean_dir.exists()` without globbing `slide_*.jpg` also false-positives on empty directories.
   - *Fix*: Never pass `--skip-download` when downloading `-f sb0/sb1/sb2/sb3`, and always verify `clean_dir.is_dir() and any(clean_dir.glob("slide_*.jpg"))`.

9. **Multimodal Endpoint Missing `/v1/chat/completions` (`KeyError: 'choices'`)**:
   - *Symptom*: `call_multimodal()` raises `KeyError: 'choices'` when passed a bare `http://host:1234` endpoint.
   - *Cause*: `urllib.request` hits the LM Studio root endpoint instead of `/v1/chat/completions`.
   - *Fix*: Always normalize `url` in `call_multimodal()` to append `/v1/chat/completions` if not already present.

10. **Missing YouTube Storyboards (`sb0/sb1/sb2/sb3` Not Available) in Multimodal Mode**:
   - *Symptom*: `yt-dlp -f sb0/sb1/sb2/sb3` fails with `Requested format is not available`, leaving `frames/slides_clean/` empty.
   - *Cause*: Certain YouTube livestream VODs do not generate MHTML storyboard streams.
   - *Fix*: Download the lightweight 144p video stream (`-f 160`, ~190MB for an 8.5h stream) and synthesize native-compatible 960×540 3×3 storyboard slide sheets directly into `frames/slides_clean/`:
     ```bash
     yt-dlp -f 160 -o "$WORKSPACE/frames/video_144p.mp4" "https://www.youtube.com/watch?v=<VIDEO_ID>"
     mkdir -p "$WORKSPACE/frames/slides_clean"
     # Compute interval = total_duration_sec / (350 * 9) or ~1 frame every 10s:
     ffmpeg -i "$WORKSPACE/frames/video_144p.mp4" -vf "fps=1/10,scale=320:180,tile=3x3" -q:v 3 "$WORKSPACE/frames/slides_clean/slide_%04d.jpg"
     ```

11. **`call_local()` Positional Timeout Collision (HTTP 400 Bad Request)**:
    - *Symptom*: Summarizer or Pruning pass fails with `HTTP Error 400: Bad Request` and falls back to heuristics.
    - *Cause*: Calling `call_local(ep, model, prompt, max_tokens, temp, TIMEOUT)` places the integer timeout into the `system_prompt` parameter (arg 6), creating `{"role": "system", "content": 180}`.
    - *Fix*: Always pass timeout via keyword argument `timeout=...`. `lmstudio.call_local()` includes an `isinstance(system_prompt, (int, float))` guard to reroute legacy positional timeouts.

12. **Tokusatsu Stage Show & TTFC Phonetic Traps**:
    - *Stage Show Forms vs. Gacha Games*: Stage show original forms (`Chaos Drone`, `Extra Shadow`, `Advance`) must not be attributed to gacha games (`Chaos Zero Nightmare`).
    - *ASR "ชิรูบิ"*: Maps to `ไรเดอร์ชิโนบิ (Kamen Rider Shinobi)` (TTFC series).
    - *Actor Memorials & Old Interviews*: News regarding `Today is Friday in California` refers to actor `Hiroshi Tsuchida` (Sasuke / Kakuranger). Actor `Shu Watanabe` (Eiji Hino / Kamen Rider OOO) must never be confused with anime characters like `Gojo Satoru`.
    - *Live-Action vs Anime*: Chinese Tokusatsu series like *Armor Hero* (นักล่าอสูรราชันผงาด / โอเมก้าฮอร์น) are live-action Tokusatsu, not anime.

13. **MTP (Multi-Token Prediction) & Speculative Decoding Pauses**:
    - Pausing a long run to attach MTP speculative decoding or adjust VRAM contexts in LM Studio is fully supported.
    - Re-running the identical command automatically discovers `recursive_outputs/chunk_XX.json` and state files, resuming immediately from the paused chunk without re-billing previous inferences.
