# Anibon Stream Synthesis Plugin

A suite of AI agent skills for deep research, live-stream transcript processing, automated timestamping, and highlight video cutting. Works across **Antigravity CLI**, **Claude Code**, **OpenCode**, and **Pi Coding Agent**.

---

## Table of Contents

- [Quick Start & Usage](#quick-start--usage)
- [Installation](#installation)
- [Available Skills](#available-skills)
- [Prerequisites](#prerequisites)
- [Further Reading](#further-reading)
- [License](#license)

---

## Quick Start & Usage

Once installed, simply trigger the skills in your AI agent:

### 1. Generate Stream Timestamps
Extract key topics, gaming moments, and donations into YouTube comment-ready blocks:
```text
/anibon-timestamper https://www.youtube.com/watch?v=VIDEO_ID
```

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

---

## Installation

### Recommended (Universal for any Agent CLI)
Install globally across Claude Code, Antigravity, OpenCode, Codex, and other agents:

```bash
npx skills add zenithth/anibon-stream-synthesis --all -g
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
| `anibon-timestamper-local` | Sequential timestamp orchestrator for local LLMs (Ollama/Gemma) | Local model fallback |
| `creating-highlight-video` | Highlight video cutter (Planner → Cutter → Verifier) | `/creating-highlight-video <URL>` |
| `livestream-scene-selection` | Filter and mark timeline scenes for summary reels | Interactive timeline selection |
| `youtube-minutes-synthesis` | Extract YouTube transcripts into structured meeting minutes | `/youtube-minutes-synthesis <URL>` |
| `preparing-tools` | Pre-flight system tool verifier (`yt-dlp`, `ffmpeg`, `sqlite3`) | Auto-called by orchestrators |
| `antigravity-vision-proxy` | Frame extraction & visual inspection proxy for game/UI context | Visual verification fallback |

---

## Prerequisites

- **Python 3.10+** (Standard library only)
- **yt-dlp** (Download transcripts and metadata)
- **ffmpeg** (Frame extraction and video cutting)
- **sqlite3** (FGO & Yu-Gi-Oh! local card lookups)

---

## Further Reading

- [`docs/SKILLS.md`](docs/SKILLS.md) — Detailed inventory of entry-point skills and reference guides
- [`docs/USAGE.md`](docs/USAGE.md) — MapReduce workflow patterns, safety masking, and iron rules
- [`docs/REFERENCE.md`](docs/REFERENCE.md) — Directory structure, script reference, and DB setup

---

## License

Distributed under the MIT License. See `package.json` for details.
