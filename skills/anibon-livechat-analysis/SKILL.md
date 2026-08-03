---
name: anibon-livechat-analysis
description: Download, parse, chunk, and analyze YouTube LiveChat replays for live streams. Extracts SuperChats/Donations, Hype/Meme peaks, viewer Q&As, and applies Thai internet subculture psychology.
---

# Anibon LiveChat Analysis Pipeline

## Overview & Triggers

Use this skill when analyzing viewer chat replays for YouTube live streams (such as Anibon Official streams) to extract donations, meme peaks, community sentiment, and stream highlights.

## Workflow

### 1. Download LiveChat Replay

Download the .live_chat.json file using yt-dlp:

`ash
yt-dlp --sub-langs live_chat --write-sub --skip-download "https://www.youtube.com/watch?v=<VIDEO_ID>" -o "%(id)s.%(ext)s"
`

> [!IMPORTANT]
> **Network Requirement**: yt-dlp requires network DNS resolution (BypassSandbox: true when running tool commands).

### 2. Parse & Chunk LiveChat File

Run the Python parser script to convert JSON lines into timestamped text chunks (livechat_chunk_1.txt to N.txt):

`ash
python3 scripts/parse_live_chat.py <VIDEO_ID>.live_chat.json --chunk-minutes 90 -o workspace/livechat_chunks
`

The script extracts:
- Timestamp formatted as HH:MM:SS
- Author name
- Message text
- SuperChat / Donation amounts (e.g. THB 40.00)
- Emotes & Stickers

### 3. Subagent Parallel Analysis

Spawn parallel subagents for each chunk file (livechat_chunk_N.txt).

Each subagent performs:
1. **SuperChat Extraction**: List all donations (Amount, Sender, Message).
2. **Hype / Meme Peaks**: Identify timestamps with high chat density, emote spams, or keyword peaks.
3. **Viewer Q&A**: Extract questions asked by chat.
4. **Thai Subculture & Psychology Rule**:
   - Reverse Meaning / Playful Envy ("กด dislike ละ" = celebration)
   - Ironic Cults / Overhype ("Eric คือ META" = meme banter)
   - Parasocial Memes ("กราบผัวเพื่อน" = community joke)
   - Coping Comedy (screaming at gacha failure = slapstick)

Write each agent output to livechat_analysis_N.txt.

### 4. Synthesize LiveChat Report & Integrate Timestamps

Merge chunk outputs into livechat_summary.md and merge top hype peak timestamps into nriched_timestamps.txt before running pack_timestamps.py.
