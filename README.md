# Anibon Stream Synthesis Plugin

![Version](https://img.shields.io/badge/version-1.2.2-blue)
[![Release](https://img.shields.io/github/v/release/ZenitHTH/anibon-stream-synthesis)](https://github.com/ZenitHTH/anibon-stream-synthesis/releases/tag/v1.2.2)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)

A full-stack AI agent skill suite for **Anibon Official (`ปู่โบ๊ต` / Boat)** livestreams: automated YouTube timestamping (Frontier Cloud & Local P100 GPU editions), multimodal storyboard & vision grounding, Thai LiveChat subculture mood analysis, Whisper corruption recovery, hybrid archive search, and non-jumpcut highlight video cutting. Works across **Antigravity CLI (`agy`)**, **Claude Code**, **OpenCode**, and **Pi Coding Agent**.

---

## Table of Contents

- [Key Features](#key-features)
- [Prerequisites & Installation](#prerequisites--installation)
- [Quick Start & Usage Guide](#quick-start--usage-guide)
- [Available Skills (23 Skills)](#available-skills-23-skills)
- [Named Subagents](#named-subagents)
- [Directory & Architecture Map](#directory--architecture-map)
- [Testing & Verification](#testing--verification)
- [Further Reading](#further-reading)
- [Contributing](#contributing)

---

## Key Features

- ☁️ **Dual-Engine Timestamping (Cloud Frontier & Local Single-GPU)**:
  - **Frontier Cloud (`anibon-timestamper`)**: Parallel chunk-group MapReduce orchestration via named subagents (`anibon-chunk-timestamper`, `anibon-garbled-notes`, `anibon-summarizer`).
  - **Local P100 / Single-GPU (`anibon-timestamper-local`)**: Zero-API-cost recursive rolling summary (`--mode recursive`) and group batching (`--mode group`) via LM Studio / Ollama / vLLM (`gemma-4-12b-it-qat`, `qwen-vl`), with adaptive multimodal storyboard keyframe selection (1–16 frames/chunk, 16×9 RGB sidecar caching, Thai deictic cue pinning).
- 🧭 **Macro-Thematic Cohesion & Essential Curation**:
  - Groups timestamps into 4–6 cohesive macro-thematic parts by actual stream activity rather than arbitrary 3,500-byte micro-splits.
  - Curates ~40–60 high-impact essential timestamps per 7–8 hour stream while retaining the exhaustive chronological log in `all_timestamps.txt`.
  - Enforces the **NO GAPS (>10m)** rule via `scripts/audit_gaps.py` and the **Stream Outro Guarantee** (`[Ending]`).
- 🛡️ **4-Layer Deterministic Anti-Hallucination Pipeline**:
  - **Layer 1 (Metadata & Knowledge Self-Reading)**: Ingests `info.json` signals, self-reads `anibon-world-identity/references/*.md`, and queries local SQLite databases (`atlas_fgo.db`, `pokemon.db`, `ygo_cards.db`) to build `<workspace>/entity_glossary.json`.
  - **Layer 2 (Buffer Scrubbing)**: Scrubs speaker identity drift (`ปู่บอท`, `ลุงบอท`, `ปู่โบต` → `ปู่โบ๊ต`) and applies `resources/default_mappings.json` before LLM inference.
  - **Layer 3 (Prompt Invariants)**: Enforces anti-guessing phonetic rules and mandatory Thai Pokémon naming (`ชื่อไทย (English Name)`).
  - **Layer 4 (Stage 5 Auto-Sanitization & Whisper Ground Truth)**: Post-processes timestamps against `resources/garbled_replacements.json` (2,100+ canonical targets / 3,100+ patterns) and resolves novel Thai-Latin ASR hybrids via `scripts/whisper_dispatcher.py` + `whisper.cpp`.
- 👁️ **Visual Grounding & Stream Activity Detection**:
  - Unpacks YouTube high-res storyboards (`sb3`/`sb2`) to track on-screen game/app state, webcam presence/AFK, and facial reactions (`anibon-stream-activity`).
  - Slices targeted 60s video windows to verify disputed numbers (`万`/`億`), campaign banners, and streamer misspeaks (`verifying-stream-ground-truth`).
- 🎭 **Thai Internet Subculture & 555 LiveChat Alignment**:
  - `scripts/analyze_555.py` aligns LiveChat replays (or burned-in visual chat OCR via `extract_visual_livechat.py` when `.live_chat.json` is deleted) per chunk, scoring 555 laughter bursts (`MEME_PULSE`) and injecting Thai humor verbs (`ฮาแซว`, `ปั่น`, `อวยมีม`, `ลุ้น 15 HP`).
- 🔍 **Deterministic Hybrid Archive Search (`anibon-search`)**:
  - Searches the `timestamp_workspace` corpus using SQLite FTS5 trigram matching + vector embeddings + Reciprocal Rank Fusion (RRF) with 600s moment collapse.

---

## Prerequisites & Installation

### System Prerequisites

Ensure the following tools are available in your system `PATH` (verified automatically by the `preparing-tools` skill):

- [ ] **Python 3.10+** (Standard library only; zero external pip requirement for core pipeline)
- [ ] **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** (Transcripts, LiveChat replays, storyboards, and targeted video slices)
- [ ] **[ffmpeg](https://ffmpeg.org/)** (Audio slicing, storyboard cropping fallback, and frame-accurate video cutting)
- [ ] **sqlite3** (Bundled with Python; queries FGO, Pokémon, and Yu-Gi-Oh! relational databases)
- [ ] **whisper.cpp** *(Optional)* (Local acoustic ground-truth transcription for missing captions and `GARBLED_NOTES` verification)

> [!TIP]
> Run `python3 scripts/preflight-gate.py --help` or invoke `/preparing-tools` inside your agent to verify all CLI dependencies before starting a run.

### Installation

#### Recommended: Universal Skills CLI
Install all skills globally for Claude Code, Antigravity, OpenCode, Codex, and compatible agents:

```bash
# Install all skills globally
npx skills add zenithth/anibon-stream-synthesis --all -g

# Or install a single skill (e.g. anibon-timestamper)
npx skills add zenithth/anibon-stream-synthesis --skill anibon-timestamper -g -y
```

#### Platform-Specific Plugin Installers

| Platform | Command |
| :--- | :--- |
| **Antigravity CLI (`agy`)** | `agy plugin install https://github.com/zenithth/anibon-stream-synthesis` |
| **OpenCode** | `opencode plugin -g anibon-stream-synthesis@git+https://github.com/ZenitHTH/anibon-stream-synthesis.git` |
| **Pi Coding Agent** | `pi install https://github.com/ZenitHTH/anibon-stream-synthesis.git` |
| **Manual Clone** | `git clone https://github.com/ZenitHTH/anibon-stream-synthesis.git` |

---

## Quick Start & Usage Guide

### 1. Frontier / Cloud Stream Timestamping (`anibon-timestamper`)

Trigger directly in your AI agent:

```text
/anibon-timestamper https://www.youtube.com/watch?v=VIDEO_ID
```

Or run the CLI pipeline stages from the plugin root:

```bash
# 1. Download transcript and chunk into 5-min XML windows with 30s overlap
python3 -X utf8 skills/anibon-timestamper/scripts/prepare_video.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --format xml --block 300 --overlap 30

# 2. Clean Thai-Latin garbled loanwords across chunks
python3 -X utf8 skills/cleaning-auto-transcripts/scripts/clean_garbled_english.py \
  --chunks ~/youtube_VIDEO_ID_workspace/chunks/

# 3. Audit gaps (max 10m) and validate YouTube section sizes after subagent assembly
python3 scripts/audit_gaps.py ~/youtube_VIDEO_ID_workspace/all_timestamps.txt \
  --chunks-dir ~/youtube_VIDEO_ID_workspace/chunks/
python3 scripts/check_sections.py ~/youtube_VIDEO_ID_workspace/anibon_timestamps.md
```

### 2. Local Single-GPU Timestamping (`anibon-timestamper-local`)

Run the full local pipeline (Stage 0 noise scrubbing, Stage 0.5 entity glossary self-reading, multimodal storyboard keyframe selection, Pass 1 recursive rolling summary, Pass 2 macro-thematic assembly, and Stage 5 parity gates):

```bash
# 1. Prepare workspace and text chunks
python3 skills/anibon-timestamper-local/scripts/prepare_video.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --workspace "~/youtube_VIDEO_ID_workspace" --format txt --block 300 --overlap 30

# 2. Run recursive multimodal timestamper via LM Studio / OpenAI-compatible server
python3 -X utf8 skills/anibon-timestamper-local/scripts/process_chunks_local.py \
  "~/youtube_VIDEO_ID_workspace" --mode recursive --lang th
```

#### Common `process_chunks_local.py` Flags
- `--mode {recursive,group}`: Recursive rolling summary (default) or 4-chunk window group mode.
- `--no-resume`: Clean-slate run; unlinks existing checkpoint state (`anibon_timestamper_state.json`).
- `--no-multimodal`: Disable storyboard keyframe extraction and run text-only inference.
- `--vision-verify`: Inspect `video_360p.mp4` frames on ambiguous proper nouns before Pass 2 assembly.
- `--byte-cap`: Opt-in strict 3,500-byte YouTube comment splitting (default groups by macro-thematic cohesion).
- `--config <path>`: Custom JSON config path (defaults to `skills/anibon-timestamper-local/config.json`).

### 3. Search the ANIBON Stream Archive (`anibon-search`)

Query across historical stream timestamps and transcripts in `/Users/zenithth/timestamp_workspace`:

```bash
python3 -m anibon_search search '{"terms": ["Chaos Zero Nightmare", "CZN"], "semantic": "ปู่โบ๊ตวิจารณ์ระบบเกมและเนื้อเรื่อง", "tags": ["Talk", "Gaming"], "limit": 10}'
```

### 4. Verify On-Screen Ground Truth (`verifying-stream-ground-truth`)

Slice a targeted 60-second window around a disputed timestamp without downloading the full multi-hour VOD:

```bash
python3 skills/verifying-stream-ground-truth/scripts/slice_stream_frame.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" "01:14:45" \
  -o "frames/banner_check.jpg"
```

### 5. Recover Corrupted Whisper Transcripts (`whisper-corruption-recovery`)

Fix Whisper repetition loops via parallel BFS divide-and-conquer and extract frames for `[?]` uncertain dialogue:

```bash
python3 skills/whisper-corruption-recovery/scripts/fix_hallucinations.py \
  whisper_output.json -o recovered_transcript.json --audio stream.wav

python3 skills/whisper-corruption-recovery/scripts/enrich_uncertain_with_vision.py \
  recovered_transcript.json --video stream.mp4
```

### 6. Cut Highlight Videos & Synthesize Meeting Minutes

```text
/creating-highlight-video https://www.youtube.com/watch?v=VIDEO_ID
/youtube-minutes-synthesis https://www.youtube.com/watch?v=VIDEO_ID
```

---

## Available Skills (23 Skills)

### 1. Orchestrator Skills
| Skill | Description | Trigger / Usage |
| :--- | :--- | :--- |
| `anibon-timestamper` | Frontier/cloud master orchestrator for Anibon livestream timestamping via parallel subagents | `/anibon-timestamper <URL>` |
| `anibon-timestamper-local` | Single-GPU local LLM/VLM orchestrator with recursive rolling summary & 4-layer anti-hallucination defense | `/anibon-timestamper-local <URL>` |
| `creating-highlight-video` | End-to-end highlight video orchestrator (Planner → Cutter → Verifier) | `/creating-highlight-video <URL>` |
| `youtube-minutes-synthesis` | Extracts YouTube transcripts into structured meeting minutes and timestamped markdown overviews | `/youtube-minutes-synthesis <URL>` |

### 2. Stream Pipeline & Verification Sub-Skills
| Skill | Description | Trigger / Usage |
| :--- | :--- | :--- |
| `preparing-tools` | Pre-flight verifier for `yt-dlp`, `ffmpeg`, `python3`, and `sqlite3` | Auto-loaded by orchestrators |
| `anibon-world-identity` | Verifies game lore, character names, and cards against 30+ markdown guides and local SQLite DBs (`atlas_fgo.db`, `pokemon.db`, `ygo_cards.db`) | Loaded on gaming/anime/pop-culture signals |
| `anibon-stream-activity` | Unpacks `sb3`/`sb2` storyboards to detect on-screen gameplay, webcam presence/AFK, and facial expressions | Step 3.6 / `--multimodal-chunks` |
| `anibon-livechat-analysis` | Downloads, parses, and aligns YouTube LiveChat replays (plus visual chat OCR fallback) for SuperChats, Q&As, and 555 meme peaks | Step 3.5 & 3.7 / `/anibon-livechat-analysis` |
| `verifying-stream-ground-truth` | Targeted 60s video frame slicing to verify disputed numbers (`万`/`億`), banners, AI image roasts, and showcase titles | On canary bursts or ambiguous nouns |
| `antigravity-vision-proxy` | Storyboard (`sb0`) and video frame inspection proxy via `view_file` or `agy --model "Gemini 3.8 Flash (High)"` | Vision fallback for non-vision agents |
| `cleaning-auto-transcripts` | Normalizes Thai-Whisper garbled English loanwords and syncs `resources/garbled_replacements.json` | `clean_garbled_english.py` / `update_garbled_dictionary.py` |
| `anibon-local-transcription` | Extracts 16kHz WAV audio and renders transcripts via local GPU `whisper.cpp` when captions are missing | Missing caption fallback |
| `whisper-corruption-recovery` | Parallel BFS divide-and-conquer recovery for Whisper repetition loops and `[?]` frame enrichment | On corrupt Whisper tails |
| `masking-royal-news` | Conditional metaphor-based safety masking for sensitive Thai royal/political legal-risk topics | Triggered only on legal-risk signals |
| `batching-subagents-concurrency` | Rate-limit-safe parallel subagent batching (MAX 6–10 concurrent per batch turn) | Auto-loaded by orchestrators |
| `livestream-scene-selection` | Filters and marks timeline scenes with narrative buffers for highlight reels | Used by `creating-highlight-video` |
| `edit-cut-video-ffmpeg` | Frame-accurate FFmpeg cutting, concatenation, and audio/video sync repair | Used by `creating-highlight-video` |
| `anibon-stream-synthesis-ffmpeg` | Advanced FFmpeg waveform cutting and narrative transition synthesis without jump-cuts | Used for video editing workflows |

### 3. Archive, Research & Tooling Skills
| Skill | Description | Trigger / Usage |
| :--- | :--- | :--- |
| `anibon-search` | Deterministic hybrid lexical (FTS5 trigram) + semantic vector search over the `timestamp_workspace` archive | Archive queries ("ปู่โบ๊ตเคยพูดเรื่อง...") |
| `backing-up-timestamps` | Ingests finalized markdown stamps into `~/timestamp_workspace` git catalog and moves raw workspaces to `~/youtube_workspaces/backed_up/` | Post-timestamping archival |
| `synthesizing-knowledge` | Generates multi-source research markdown documents with verified citation links | `/synthesizing-knowledge` |
| `building-reusable-cli-tools` | Engineering patterns for modular, configurable, stdlib-first Python CLI tools | When authoring new `scripts/*.py` |
| `writing-plugin-readme` | Checklist and formatting standards for plugin and tool README documentation | When updating documentation |

---

## Named Subagents

Wired directly into the `anibon-timestamper` pipeline under `agents/` (never substitute generic `Task`/`self` agents):

| Subagent | Role in Pipeline |
| :--- | :--- |
| `anibon-chunk-timestamper` | Processes a sequential group of 4–5 transcript chunks (~20–25 min) alongside LiveChat and activity logs; tracks topic continuity across chunks and emits `HH:MM:SS - [Tag] Description` plus `GARBLED_NOTES:` blocks. |
| `anibon-garbled-notes` | Post-timestamp cleanup agent. Coordinates with `scripts/whisper_dispatcher.py` (`whisper.cpp` audio ground truth), applies anti-cascade validation against raw `.json3` captions, and syncs confirmed rules into `resources/garbled_replacements.json`. |
| `anibon-summarizer` | Final assembly agent. Deduplicates cross-chunk overlaps, curates essential high-value timestamps, groups into cohesive macro-thematic parts by actual stream activity, and outputs the final markdown document. |

---

## Directory & Architecture Map

```text
anibon-stream-synthesis/
├── agents/                              # First-class named subagent definitions
│   ├── anibon-chunk-timestamper.md
│   ├── anibon-garbled-notes.md
│   └── anibon-summarizer.md
├── lib/anibon/                          # Shared core Python library (symlinked across skills)
│   ├── analyzer.py                      # Gap detection & chunk classification
│   ├── chunk_io.py                      # XML/TXT chunk readers & writers
│   ├── cleaner.py                       # V2 grouped garbled-word & noise cleaner
│   ├── corruption.py                    # Whisper repetition loop scanner
│   ├── markdown.py / parsers.py         # Timestamp line & section parsers
│   ├── resources.py                     # Root-first resource_path() resolver
│   └── vision.py / ytdlp.py             # Frame extraction & yt-dlp wrappers
├── resources/                           # Single-source master JSON dictionaries
│   ├── garbled_replacements.json        # 2,130+ canonical targets (3,140+ ASR patterns)
│   ├── default_mappings.json            # Pre-inference phonetic & speaker normalizations
│   ├── knowledge.json / signal_config.json
│   ├── channels.json / emoji_dictionary.json
│   └── tag_macros.json / tone_hints.json
├── scripts/                             # Root CLI gates & pipeline utilities
│   ├── preflight-gate.py                # Pre-spawn analyzer & signal verification gate
│   ├── assembly-gate.py                 # Post-spawn dedup, header & gap gate
│   ├── pack_timestamps.py               # Context-aware timestamp packer
│   ├── analyze_555.py                   # LiveChat 555-pulse mood scorer
│   ├── audit_gaps.py                    # Mandatory max-10-min gap auditor
│   ├── check_sections.py                # Section byte-size & ASR garble validator
│   ├── validate_tags.py                 # Canonical [Tag] validator
│   └── whisper_dispatcher.py            # On-demand audio slicer + whisper.cpp runner
├── skills/                              # 23 self-contained agent skills
│   ├── anibon-timestamper/              # Cloud/Frontier orchestrator & stream references
│   ├── anibon-timestamper-local/        # Local P100 GPU orchestrator & scripts/anibon/ runtime
│   ├── anibon-world-identity/           # 30+ game/anime references & DB bootstrap scripts
│   ├── reference/                       # Local SQLite DBs (atlas_fgo.db, ygo_cards.db)
│   └── ...                              # 19 additional specialized skills
├── docs/                                # Detailed architecture & usage guides
│   ├── SKILLS.md                        # Categorized 23-skill & 3-subagent index
│   ├── USAGE.md                         # MapReduce workflows, Thai humor & 18 Iron Rules
│   └── REFERENCE.md                     # CLI script flags & database schemas
├── tests/                               # Stdlib unittest suite (root + per-skill tests)
├── GEMINI.md                            # Global orchestrator & streamer identity invariants
├── plugin.json / package.json           # Multi-platform plugin manifests
└── CHANGELOG.md                         # Release history
```

---

## Testing & Verification

All tests use Python's standard library `unittest` (zero external test runner required):

```bash
# Run root unit and integration tests
python3 -m unittest discover -s tests -p "test_*.py"

# Run local timestamper test suite (multimodal keyframes, 4-layer sanitization, state resume)
python3 -m unittest discover -s skills/anibon-timestamper-local/tests -p "test_*.py"
```

---

## Further Reading

- [`GEMINI.md`](GEMINI.md) — Global orchestrator pipeline guards and streamer identity invariants (`ปู่โบ๊ต`)
- [`docs/SKILLS.md`](docs/SKILLS.md) — Categorized index of all 23 skills and 3 named subagents
- [`docs/USAGE.md`](docs/USAGE.md) — Hierarchical MapReduce patterns, Thai subculture rules, and the 18 Iron Rules
- [`docs/REFERENCE.md`](docs/REFERENCE.md) — Detailed CLI script arguments, SQLite DB bootstrap commands, and platform compatibility matrix
- [`CHANGELOG.md`](CHANGELOG.md) — Version history and architectural milestones

---

## Contributing

1. Follow `building-reusable-cli-tools` (Python 3.10+ stdlib-first, `from __future__ import annotations`, zero unnecessary third-party dependencies).
2. Keep shared modules in `lib/anibon/` and master dictionaries in `resources/`. Do not create divergent per-skill copies.
3. Add or update `unittest` coverage under `tests/` or `skills/<skill>/tests/` before committing.
