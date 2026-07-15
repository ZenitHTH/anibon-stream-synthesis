---
name: preparing-tools
description: Use when starting any anibon-stream-synthesis skill to verify all required system tools are installed and accessible before performing any other action.
---

# Preparing Tools

## Overview

A shared pre-flight checklist for all anibon-stream-synthesis skills. **Always run this first** before any download, processing, or analysis step. Catching a missing tool here prevents cryptic mid-task failures.

## When to Use

- **REQUIRED** at the start of every orchestrator skill in this plugin:
  - `anibon-timestamper`
  - `anibon-timestamper-local`
  - `creating-highlight-video`
  - `youtube-minutes-synthesis`

## Tool Check Commands

Run all checks in a single shell call before doing anything else:

```bash
echo "=== Tool Check ===" && \
yt-dlp --version && \
ffmpeg -version 2>&1 | head -1 && \
python3 --version && \
sqlite3 --version && \
echo "=== All tools OK ==="
```

## What to Do on Failure

| Tool Missing | Action |
| :--- | :--- |
| `yt-dlp` not found | Tell user: `yt-dlp is missing. Install via: pip install yt-dlp` |
| `ffmpeg` not found | Tell user: `ffmpeg is missing. Install via package manager (apt/brew/choco)` |
| `python3` not found | Tell user: `Python 3.10+ is required. Install from https://python.org` |
| `sqlite3` not found | Tell user: `sqlite3 is missing. Install via: sudo apt install sqlite3` |

> [!IMPORTANT]
> **Do NOT proceed with the skill's main task if any required tool is missing.** Stop and report all missing tools to the user together so they can fix them in one go.

## Quick Reference

| Tool | Min Version | Purpose |
| :--- | :--- | :--- |
| `yt-dlp` | latest | Download transcripts, captions, video streams |
| `ffmpeg` | 4.x+ | Video cutting, concat, AV sync |
| `python3` | 3.10+ | All processing scripts (`prepare_video.py`, etc.) |
| `sqlite3` | any | FGO / YGO card database lookups |

## Iron Rule

**First tool call = `echo "=== Tool Check ==="`. No exceptions.**

Never skip the tool check "because it probably worked last time." Network installs update. Paths break. Confirm every session.
