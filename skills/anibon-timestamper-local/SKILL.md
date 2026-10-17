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
- **`whisper-corruption-recovery`**: Automatically invoked if Whisper transcription contains repetition loops or silence stutter.
- **`anibon-local-transcription`**: Used when YouTube has no subtitles or auto-captions to extract 16kHz audio and run local GPU whisper.cpp.

## Pipeline Architecture

| **0. Noise Cleaning & Pre-normalization** | `signal_detector.py` / `anibon/` (auto) | `garbled_replacements.json` + `default_mappings.json` | Strips ASR speaker markers (`>>`), sound effect tags (`[เพลง]`, `[Applause]`), music symbols (`♪`), repetitive stutter loops, and corrects phonetic drift before chunk loading/signal detection. |
| **0.5 Knowledge Self-Reading** | `anibon/knowledge_reader.py` (auto) | `signals.json` + `references/*.md` + DBs → `entity_glossary.json` | Self-reads domain markdown references matched in signals, queries local SQLite databases (`atlas_fgo.db`, `pokemon.db`), and builds chunk-filtered verified entity glossaries. Bypass via `--no-knowledge-reader`. |
| **1. Preparation & Chunking** | `prepare_video.py` | YouTube URL → `raw_transcript.json`, `chunks/*.txt` | Downloads subtitles and segments audio/transcript into overlapping chunks. |
| **1.5 LiveChat & Mood Detection** | `anibon/parity_gates.py` (`analyze_555.py`) | `livechat/` → `mood_555.json` | Auto-detects 555/laugh bursts and classifies chunk mood/tone (`*_PULSE`, `HOT`, `WARM`, `QUIET`) for prompt tone guidance. |
| **2. Topic Segmentation (Pass 1)** | `process_chunks_local.py` | `chunks/`, `signals.json`, Storyboard keyframes (`--multimodal-chunks`) | Detects shifts/continuations, emits timestamps via local LLM/VLM with visual ground truth and mood tone hints. |
| **2.5 Vision Ground Truth (Optional)** | `anibon/vision_verify.py` (`--vision-verify`) | `video_360p.mp4` + ambiguous stamps | Inspects on-screen video frames via local vision model for vague proper nouns or `[?]` tags before Pass 2 assembly. |
| **3. Summarizer & Assembly (Pass 2)** | `anibon/summarizer.py` (auto) | `all_timestamps.txt` → `anibon_timestamps.md` | Clusters timestamps into cohesive macro-thematic parts (typically 4–6 parts) and snaps to transition cues (`find_best_boundary`). |
| **4. Garbled Collector & Whisper Ground Truth** | `whisper_dispatcher.py` (auto post-pass) | `garbled_notes_raw/` → `garbled_notes.json` → `garbled_replacements.json` | Automatically runs after summary: slices audio on-the-fly, transcribes phonetic ground truth via local whisper.cpp, and auto-grows shared dictionary. |
| **5. Deterministic Parity Gates** | `anibon/parity_gates.py` (auto post-pass) | `all_timestamps.txt`, `anibon_timestamps.md` | Runs front-tier parity checks: `audit_gaps.py` (enforces NO GAPS > 10m) and `check_sections.py` (audits byte sizes and ASR garble patterns; report-only). |

### Modular Library Architecture (`scripts/anibon/`)

`process_chunks_local.py` is decomposed into single-responsibility, unit-tested modules:
- `anibon/multimodal.py`: Storyboard slide unpacking, 3-keyframe sampling per chunk bounds, OpenAI-compatible multi-image payload construction, and VLM execution.
- `anibon/knowledge_reader.py`: Automated domain knowledge discovery from `signals.json`, regex table/bullet entity parser, SQLite DB enricher (`atlas_fgo.db`, `pokemon.db`), and `entity_glossary.json` generator.
- `anibon/timestamps.py`: Tag normalization (`TAG_REMAP`), timestamp line sanitization, collision guards ($\ge 45\text{s}$ spacing), window validation.
- `anibon/lmstudio.py`: LM Studio & OpenAI-compatible client (TokenMe, vLLM, Ollama), model resolution (defaults to `gemma-4-12b-it-qat@q4_k_xl` or `unsloth/gemma-4-26b-a4b-it@q2_k_x`), text completions, Bearer auth, Cloudflare bypass, and multi-modal Vision API (`image_url` data URIs for Gemma 4 Vision, Qwen-VL).
- `anibon/websearch.py`: Lightweight DuckDuckGo search with local JSON cache (`websearch_cache.json`) for zero-cost entity verification.
- `anibon/prompts.py`: Recursive rolling summary and group batching prompts, World Identity reference injection, and search/vision context blocks.
- `anibon/summarizer.py`: Pass 2 local summarizer with semantic & chronological deduplication and macro-thematic part assembly (typically 4–6 parts).
- `anibon/state.py`: Checkpoint persistence (`anibon_timestamper_state.json`), chunk discovery, and multimodal loaders (LiveChat, 555 mood, activity).

### Multi-Layer Anti-Hallucination & Verification Architecture (4-Layer Defense)

Local smaller LLMs (e.g. 12B–27B) lack the vast parametric world knowledge of front-tier models, making them prone to phonetic guessing and hallucinated English titles. `anibon-timestamper-local` implements a deterministic 4-layer defense pipeline:

1. **Layer 1: Metadata & Title Signal Ingestion (`signal_detector.py`)**
   - Ingests video title, description, and tags from `info.json` via `extract_metadata_signals()`.
   - Dynamically discovers all reference markdown games in `anibon-world-identity/references/*.md` via `discover_reference_games()`.
   - Anchors stream context before inference to prevent misidentifying specific games as generic categories.

2. **Layer 2: Pre-Inference Buffer Normalization & Scrubbing (`state.py`)**
   - Automatically scrubs ASR speaker drift (`ปู่บอท`, `ลุงบอท`, `ปู่โบต` → `ปู่โบ๊ต`) during chunk loading in `load_chunk_file()`.
   - Applies phonetic mappings from `default_mappings.json` before passing text to the LLM prompt.

3. **Layer 3: Anti-Guessing & Invariant Prompt Directives (`prompts.py`)**
   - Enforces `STREAMER IDENTITY` invariant: The streamer is exclusively `'ปู่โบ๊ต' (Boat)`. Never write `'ปู่บอท'`, `'ลุงบอท'`, or `'ปู่โบต'`.
   - Enforces `ANTI-GUESSING CONSTRAINT`: Never arbitrarily translate Thai phonetic loanwords into novel English spellings. If not found in `VERIFIED DOMAIN ENTITIES`, write phonetic Thai or describe the action in Thai. Never invent novel English proper nouns.
   - Enforces `POKÉMON NAMING RULE`: Pokémon entities must strictly follow `'ชื่อไทย (English Name)'` (Thai community/official name followed by English name in parentheses).

4. **Layer 4: Stage 5 Deterministic Auto-Sanitization (`process_chunks_local.py`)**
   - Automatically executes `sanitize_and_audit_timestamps()` during Pass 2 summary assembly.
   - Deterministically corrects residual speaker misspellings and canonical dictionary patterns (`garbled_replacements.json`, e.g. `Archen` → `Arcane`, `Victor` → `Viktor`).
   - Audits timestamp lines for unverified capitalized Latin words against whitelisted tags and glossaries, raising deterministic audit warnings for suspect hallucinations.

---

## Execution Modes

### Mode 1: Recursive Rolling Summary (`--mode recursive`, Default & Recommended)
Pu Boat's discussions follow organic content flow rather than clock boundaries. A topic may last 3 minutes or 25 minutes.
- **`SAME_TOPIC`**: If Chunk $N$ continues the ongoing topic, it merges into the rolling summary without emitting a timestamp (0 timestamps).
  - **Long-Form Talk/News Exception**: If a monologue or societal debate continues across multiple chunks (>8–10 minutes without a stamp), the model MUST extract a distinct sub-angle or specific policy critique (1 timestamp) rather than leaving long blanks.
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

#### 2. Run Timestamper Directly (Foreground)
**macOS / Linux:**
```bash
python3 -X utf8 scripts/process_chunks_local.py "~/youtube_<VIDEO_ID>_workspace" \
    --mode recursive --lang th
```

**Windows (PowerShell):**
```powershell
python -X utf8 scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th
```

> [!TIP]
> **Single Comment Byte Limit (`--byte-cap`)**:
> Pass `--byte-cap` if you need each part strictly under 3,500 bytes for YouTube single-comment pasting. By default, byte-capping is disabled to preserve cohesive macro-thematic grouping (4–6 parts).


#### 2.1 In-Pipeline Vision Verification (Optional)
Inspect on-screen video frames for ambiguous or vague timestamps (deictic pronouns, missing game names, `[?]` markers) using the local vision model before Pass 2 summary:
```powershell
python -X utf8 scripts\process_chunks_local.py "$HOME\youtube_<VIDEO_ID>_workspace" --mode recursive --lang th --vision-verify
```

#### 2.2 Multimodal Chunk Analysis with Storyboard Keyframes (`--multimodal-chunks`)
Samples 3 high-resolution Storyboard keyframes per chunk directly into the VLM (e.g. Gemma 4 12B Vision) alongside the transcript text during Pass 1. Eliminates game title misattribution and grounds event/chapter subtitles in real time:
```bash
python3 scripts/process_chunks_local.py ~/youtube_<VIDEO_ID>_workspace \
    --mode recursive --lang th --multimodal-chunks
```

#### 3. Detached Background Launch (3 OS Families)
Runs inference detached in background so agent sessions or timeouts do not kill the run.

**macOS (Zsh / Bash):**
```zsh
./scripts/launch_local.zsh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th
```

**Linux (Bash):**
```bash
./scripts/launch_local.sh ~/youtube_<VIDEO_ID>_workspace 100.115.25.30 auto th
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File "scripts\launch_local.ps1" -Workspace "$HOME\youtube_<VIDEO_ID>_workspace" -Endpoint "100.115.25.30"
```

**Windows (CMD Batch):**
```cmd
scripts\launch_local.bat "%USERPROFILE%\youtube_<VIDEO_ID>_workspace" 100.115.25.30 auto th
```

> [!NOTE]
> **Endpoint Auto-Probe & Fallback Rule**: All runners and Python client (`anibon.lmstudio.resolve_endpoint()`) automatically probe `http://100.115.25.30:1234` with a 1.0s TCP socket test. If unreachable (indicating execution on localhost itself), they immediately and safely fall back to `http://127.0.0.1:1234`.

> [!TIP]
> **Remote / TokenMe Endpoint Support**:
> You can target remote OpenAI-compatible endpoints such as TokenMe (`--endpoint https://api.tokenme.limited/v1` or `api.tokenme.limited`) by passing `TOKENME_API_KEY` (or `LM_API_KEY`) in the environment or `--api-key`.
> - The client sets standard `Authorization: Bearer <KEY>` and browser `User-Agent` headers to bypass Cloudflare WAF code 1010.
> - Remote models like `nvidia/Gemma-4-26B-A4B-NVFP4` support multimodal vision inspection via base64 `image_url` payloads out-of-the-box.

#### 4. Garbled Collector & Whisper Ground Truth (Automatic Post-Pass)
After `anibon_timestamps.md` summary assembly finishes, `process_chunks_local.py` automatically checks for surviving phonetic garbles in `<workspace>/garbled_notes_raw/` and invokes `whisper_dispatcher.py` with local `whisper.cpp` to slice audio and update `garbled_replacements.json`.

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
   - **New Competitive Games (Deadlock, etc.)**: Cross-reference hero names (Baba / Baba Yaga, Celeste, Abrams) via web search or patch notes.
2. **Apply Entity Corrections**: Correct phonetic drifts, misheard titles, or LLM hallucinations directly in `anibon_timestamps.md`.
3. **Persist Knowledge**:
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

### Stream Ending / Outro Invariant
In `--mode recursive`, long unbroken gameplay or concluding sessions must not allow `is_continuation=True` to swallow the stream outro.
The final 5 minutes of transcript must always be checked for closing tokens (`ขอบคุณครับ`, `ลงไลฟ์`, `ราตรีสวัสดิ์`, `เจอกัน`, `บ๊ายบาย`) and emit:
`HH:MM:SS - [Ending] ปู่โบ๊ตขอบคุณผู้ชมและกล่าวปิดสตรีม`

### Macro-Thematic Part Grouping Invariant (No 3,500-Byte Cap Over-Splitting)
Timestamps are grouped strictly into broad, cohesive macro-thematic parts (typically 4–6 parts for a long stream).
Prioritize viewer navigation and thematic cohesion: keep related discussions (such as an entire series review, media watchparty, or gaming session) unified in a single part rather than arbitrarily slicing into 10–18 micro-parts to fit single-comment byte limits.
`assemble_parts()` and `run_local_summarizer_pass()` do not enforce byte caps by default. `enforce_byte_cap()` is retained as an opt-in utility only if single-comment splitting is explicitly requested.

### Essential Curated Timestamps Selection Invariant
When generating timestamps from long livestreams (4–8 hours), follow these operating standards:
1. **Primary Output Focus**: Present the primary result as a curated essential edition (~40–60 timestamps for a 7–8 hour stream, or approximately 8–15 stamps per macro-thematic part).
   - **Automated Essential Pruning (`prune_essential`)**: For streams yielding >60 timestamps, `finalize_and_assemble_timestamps()` automatically queries the local model to distill essential pivot points, news, gameplay milestones, and core conclusions down to ~40–60 stamps. The pipeline enforces strict verbatim matching against raw timestamps, guarantees retention of opening and `[Ending]` timestamps, and falls back cleanly if the LLM call fails.
2. **Essential Selection Criteria**:
   - Major topic starts or pivot points (Topic Shift / Pivot).
   - Official news, announcements, releases, or statistical data (Official News, Releases, Data).
   - In-depth analytical conclusions and core takeaways (In-depth Analysis & Core Takeaways).
   - Key gameplay milestones (tutorial start, exploring new characters/skills, key item crafting, boss spawns, highlight fights, victory/defeat).
   - Stream outro and closing thanks (Stream Outro).
3. **Pruning Micro-Stamps**:
   - Prune micro-talk stamps repeating the same talking point within a short window (e.g. if the streamer dissects a point for 5–10 minutes, do not place stamps every 2 minutes).
   - Prune casual chat chatter, minor jokes, or banter that does not impact the core narrative.
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
