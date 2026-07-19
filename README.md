# Anibon Stream Synthesis Plugin

A suite of agent skills for deep research, live-stream transcript processing, and content synthesis. Works across **Antigravity CLI**, **Claude Code**, **OpenCode**, and **Pi Coding Agent**.

---

## Table of Contents

- [Background](#background)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Further Reading](#further-reading)
- [Contributing](#contributing)
- [License](#license)

---

## Background

**Anibon** (specifically **Pu Boat** or "บ๊อต" from **Anibon Official**) is a prominent Thai content creator, streamer, and pop-culture/gaming commentator. His content covers gacha games (FGO, Honkai Impact/Star Rail), anime discussions, tokusatsu franchise watch parties, and patch-note theorycrafting.

### Why was this created?

Boat's live streams are exceptionally long (often **2 to 10+ hours**) and highly unstructured. During a single stream he might transition chaotically from gacha pulls to discussing Thai news (masked in One Piece metaphors), reading patch notes, and hosting watch parties.

Manually timestamping these streams is extremely time-consuming. This plugin automates it via **hierarchical MapReduce** — splitting long streams, cleaning transcription noise, auto-routing content chunks to specialized sub-skills, and enforcing formatting and safety constraints.

---

## Prerequisites

- **Python 3.10+** (Standard library only; no third-party packages)
- **yt-dlp** (Download stream media, transcripts, comments)
- **ffmpeg** (Frame extraction, video cutting, audio processing)
- **sqlite3** (FGO and Yu-Gi-Oh! local lookup databases)

> Both `yt-dlp` and `ffmpeg` must be available in `PATH` for automated scripts and video cutting.

---

## Quick Start

### OpenCode (recommended)

```bash
opencode plugin -g anibon-stream-synthesis@git+https://github.com/ZenitHTH/anibon-stream-synthesis.git
```

Or add to `~/.config/opencode/opencode.jsonc`:

```json
{
  "plugin": ["anibon-stream-synthesis@git+https://github.com/ZenitHTH/anibon-stream-synthesis.git"]
}
```

Restart OpenCode. Plugin manager downloads package and registers all skills.

### Antigravity CLI

```bash
agy plugin install https://github.com/zenithth/anibon-stream-synthesis
```

Or clone manually:

```bash
cd ~/.gemini/config/plugins/
git clone https://github.com/zenithth/anibon-stream-synthesis.git
```

### Claude Code / Skills CLI

```bash
npx skills add zenithth/anibon-stream-synthesis --all -g
```

### Pi Coding Agent

```bash
pi install https://github.com/ZenitHTH/anibon-stream-synthesis.git
```

### Manual Clone

```bash
git clone https://github.com/ZenitHTH/anibon-stream-synthesis.git
```

Then point your agent to the `skills/` directory.

---

## Further Reading

| Document | Description |
|----------|-------------|
| [`docs/SKILLS.md`](docs/SKILLS.md) | Full skill inventory, sub-skills, knowledge base references |
| [`docs/USAGE.md`](docs/USAGE.md) | Workflow patterns (MapReduce, safety masking), iron rules |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | Directory structure, script reference, database setup, platform compatibility |

---

## Contributing

Contributions welcome. Ensure code changes maintain compatibility across all supported environments. Follow guidelines in [`skills/writing-plugin-readme/SKILL.md`](skills/writing-plugin-readme/SKILL.md).

---

## License

Distributed under the MIT License. See `package.json` for details.
