# Anibon Stream Synthesis Plugin

![Version](https://img.shields.io/badge/version-1.2.0-blue)
[![Release](https://img.shields.io/github/v/release/ZenitHTH/anibon-stream-synthesis)](https://github.com/ZenitHTH/anibon-stream-synthesis/releases/tag/v1.2.0)

A suite of AI agent skills for deep research, live-stream transcript processing, automated timestamping, LiveChat subculture mood analysis, and highlight video cutting. Works across **Antigravity CLI**, **Claude Code**, **OpenCode**, and **Pi Coding Agent**.

---

## Table of Contents

- [Quick Start & Usage](#quick-start--usage)
- [Installation](#installation)
- [Key Features](#key-features)
- [Available Skills](#available-skills)
- [Prerequisites](#prerequisites)
- [Further Reading](#further-reading)
- [License](#license)

---

## Quick Start & Usage

Once installed, simply trigger the skills in your AI agent:

### 1. Generate Stream Timestamps
Extract key topics, gaming moments, story readings, meme bursts, and donations into YouTube comment-ready blocks:
```text
/anibon-timestamper https://www.youtube.com/watch?v=VIDEO_ID
```

- **Full List Reveal Rule**: Automatically parses across adjacent chunk boundaries so multi-item reveals (e.g., 7 animation updates) are never truncated to single-chunk limits.
- **Mood & LiveChat 555 Integration**: Ingests livechat replays to detect `MEME_PULSE` (555 laughter bursts) and enforce Thai internet humor verbs (`ฮาแซว`, `ปั่น`, `อวยมีม`, `ลุ้น 15 HP`). Mood verdicts per chunk are injected as tone guidance into subagent prompts.
- **Garbled-Word Feedback Loop**: Chunk subagents emit `GARBLED_NOTES` for Thai-Latin hybrids that survive cleaning; the `anibon-garbled-notes` subagent consolidates them, writes `garbled_notes.json`, and grows the shared cleaning dictionary so every future stream auto-corrects them.
- **NO GAPS Enforcement**: `audit_gaps.py` + agent guardrails enforce the max-10-minute timestamp gap rule with gap→chunk mapping.
- **Quota Packing**: Groups timestamps into 5 high-density parts optimized for YouTube's 4,500-byte comment cap.

### 2. Cut Highlight Videos
Select key scenes and automatically generate non-jumpcut FFmpeg video edits:
```text
/creating-highlight-video https://www.youtube.com/watch?v=VIDEO_ID
```

### 3. Summarize Video Meeting Minutes
Generate timestamped Markdown meeting minutes from any YouTube video:
```text
/youtube-minutes-synthesis https://www.youtube.com/watch?v=VIDEO_ID
```

### 4. Recover Corrupted Transcripts & Extract Vision Context
Fix Whisper repetition loops and extract frames for `[?]` uncertain dialogue:
```bash
python skills/whisper-corruption-recovery/scripts/fix_hallucinations.py whisper_output.json -o recovered_transcript.json --audio stream.wav
python skills/whisper-corruption-recovery/scripts/enrich_uncertain_with_vision.py recovered_transcript.json --video stream.mp4
```

---

## Key Features

- 🎭 **Thai Internet Subculture & Psychology Integration**:
  - Encodes Thai stream humor, keyboard typos (`ถถถถ`), and 2024–2025 stream slang (`ทำถึง`, `จะ Crazy`, `อ่อม`, `ตึง`, `ตุย`, `สภาพ`).
  - Interprets playful envy ("กด dislike ละ") and meme cult hyping (1★ / 2★ units as META) without literal flattening.
- 📜 **Full List Reveal Protocol**:
  - Ensures subagents read across adjacent chunks for list announcements (character update lists, gacha line-ups) so full counts (e.g. 7 male servants) are accurately captured.
- 📊 **555 Pulse & LiveChat Alignment**:
  - `analyze_555.py` aligns livechat messages per 5-minute chunk, identifying 555 laughter spikes and overriding flat tone verbs with authentic streamer/chat humor verbs.
  - `validate_mood.py` verifies mood-bearing timestamps honour the per-chunk mood verdict.
- 🧹 **Garbled-Word Auto-Correction**:
  - `clean_garbled_english.py` normalises Thai-Whisper garbled English (Thai syllable + Latin tail, e.g. `อีเวent` → `อีเวนต์`).
  - `garbled_replacements.json` is shared via `resource_path()` across all skill copies and auto-grows each stream via the `anibon-garbled-notes` feedback loop (94 rules and counting).
- 📦 **YouTube Comment Quota Optimization**:
  - Merges sparse entries into high-density topic-coherent sections (~2,500–3,300 bytes per section) with 0 validation errors via `check_sections.py`.

---

## Installation

### Recommended (Universal for any Agent CLI)
Install all skills globally across Claude Code, Antigravity, OpenCode, Codex, and other agents:

```bash
npx skills add zenithth/anibon-stream-synthesis --all -g
```

Or install any single skill individually (each skill is self-contained with zero external dependencies):

```bash
npx skills add zenithth/anibon-stream-synthesis/skills/anibon-timestamper -g
```

### Alternative Platform Commands

| Platform | Command |
|---|---|
| **Antigravity CLI** | `agy plugin install https://github.com/zenithth/anibon-stream-synthesis` |
| **OpenCode** | `opencode plugin -g anibon-stream-synthesis@git+https://github.com/ZenitHTH/anibon-stream-synthesis.git` |
| **Pi Coding Agent** | `pi install https://github.com/ZenitHTH/anibon-stream-synthesis.git` |
| **Manual Clone** | `git clone https://github.com/ZenitHTH/anibon-stream-synthesis.git` |

---

## Available Skills

| Skill | Description | Usage |
|---|---|---|
| `anibon-timestamper` | Master orchestrator for Anibon live streams timestamping | `/anibon-timestamper <URL>` |
| `anibon-livechat-analysis` | Download, parse, chunk, and analyze YouTube LiveChat replays for SuperChats & meme peaks | Auto-loaded / `/anibon-livechat-analysis` |
| `anibon-timestamper-local` | Sequential timestamp orchestrator for local LLMs (Ollama/Gemma) | Local model fallback |
| `whisper-corruption-recovery` | Parallel BFS divide-and-conquer recovery for Whisper repetition loops & vision frame extraction | `/whisper-corruption-recovery` |
| `creating-highlight-video` | Highlight video cutter (Planner → Cutter → Verifier) | `/creating-highlight-video <URL>` |
| `livestream-scene-selection` | Filter and mark timeline scenes for summary reels | Interactive timeline selection |
| `youtube-minutes-synthesis` | Extract YouTube transcripts into structured meeting minutes | `/youtube-minutes-synthesis <URL>` |
| `preparing-tools` | Pre-flight system tool verifier (`yt-dlp`, `ffmpeg`, `sqlite3`) | Auto-called by orchestrators |
| `antigravity-vision-proxy` | Frame extraction & visual inspection proxy for game/UI context | Visual verification fallback |
| `batching-subagents-concurrency` | Rate-limit-safe parallel subagent batching (MAX 6 concurrent) | Auto-loaded by orchestrators |

---

## Prerequisites

- **Python 3.10+** (Standard library only)
- **yt-dlp** (Download transcripts, live chat replays, and metadata)
- **ffmpeg** (Frame extraction and video cutting)
- **sqlite3** (FGO & Yu-Gi-Oh! local card lookups)

---

## Further Reading

- [`docs/SKILLS.md`](docs/SKILLS.md) — Detailed inventory of entry-point skills and reference guides
- [`docs/USAGE.md`](docs/USAGE.md) — MapReduce workflow patterns, Thai humor rules, and iron rules
- [`docs/REFERENCE.md`](docs/REFERENCE.md) — Directory structure, script reference, and DB setup

---

## License

Distributed under the MIT License. See `package.json` for details.
