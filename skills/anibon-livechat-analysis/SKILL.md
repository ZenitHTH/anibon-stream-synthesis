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

`ash
python3 scripts/parse_live_chat.py <VIDEO_ID>.live_chat.json --chunk-minutes 90 -o workspace/livechat_chunks
`

The script extracts:
- Timestamp formatted as HH:MM:SS
- Author name
- Message text
- SuperChat / Donation amounts (e.g. THB 40.00)
- Emotes & Stickers

> [!TIP]
> **Timestamper integration**: pass `--raw-events workspace/livechat_events.txt` to also emit a
> seconds-prefixed event feed. The `anibon-timestamper` orchestrator (Step 3.5) then slices that feed
> to its 5-minute transcript chunks via `scripts/align_live_chat.py`, so each timestamp subagent can read
> the watchers' chat for its own chunk and infer situation + emotion from both sides.
> Refer to [`anibon_emoji_dictionary.md`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/references/anibon_emoji_dictionary.md) for custom Anibon channel emotes and YouTube global emote weights.

### 2.5 Fallback: On-Screen Burned-in LiveChat Extraction (When .live_chat.json is Missing)

When a livestream has been trimmed or edited in YouTube Studio (e.g., intro/outro cuts, copyright muting, or post-broadcast edits), YouTube permanently deletes the `.live_chat.json` chat replay track. In other cases, `yt-dlp` may report that no chat subtitles exist for the VOD.

When `.live_chat.json` is missing or stripped, use [`extract_visual_livechat.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py) to extract chat messages directly from the burned-in on-screen chat overlay using Gemini vision.

#### How It Works

1. **Video Slice Acquisition**: Automatically downloads a targeted section slice using `yt-dlp` with `--video-id` and `--range` (via `--cookies-from-browser chrome --download-sections "*<range>"`), or uses an existing local video file via `--video-path`.
2. **Layout Auto-Detection**: Employs edge-density analysis ([`visual_chat_crop.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/visual_chat_crop.py)) to detect whether the chat overlay is positioned in the `bottom-right` (`[x=0.68w, y=0.35h, w=0.31w, h=0.62h]`) or `left` (`[x=0.01w, y=0.10h, w=0.30w, h=0.85h]`) ROI. You can override detection with `--force-pos`.
3. **Frame Sampling & Cropping**: Extracts cropped chat region frames at a configurable sampling interval (default: `--fps 0.25`, or 1 frame every 4 seconds) using FFmpeg.
4. **Vision OCR via `agy`**: Delegates OCR to `agy` using `Gemini 3.6 Flash (Medium)`. Translates rendered visual channel emotes into standard tags (`:_CunnyBoat:`, `:_MonkeyBoat:`, `:_Nerd:`, `:_Grind:`, `:_Ripfish:`, `:_noname:`, `:_What:`, `:_WOW:`, `:_Ahh:`, `:_Meh:`, `:_BoatSOM:`, `:_Tahaan:`, `:_KonDee:`, `:_Tea:`, `:face-blue-smiling:`, `:hand-pink_waving:`).
5. **Deduplication & Formatting**: Deduplicates scrolling messages across sampled frames ([`visual_chat_dedup.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/visual_chat_dedup.py)) and emits lines formatted identically to the YouTube LiveChat raw event feed:
   ```text
   <sec>	[HH:MM:SS] <author>: <text>
   <sec>	[HH:MM:SS] 💰 SUPERCHAT (<amount>) from <author>: <text>
   ```

#### CLI Usage Examples

**Download and extract from YouTube directly (targeted section slice):**
```bash
python3 scripts/extract_visual_livechat.py \
  --video-id <VIDEO_ID> \
  --range 00:10:00-00:15:00 \
  -o workspace/livechat_events.txt
```

**Extract from an existing local video file or slice:**
```bash
python3 scripts/extract_visual_livechat.py \
  --video-path workspace/stream_slice.mp4 \
  --range 00:10:00-00:15:00 \
  --force-pos bottom-right \
  -o workspace/livechat_events.txt
```

#### CLI Flags & Options

| Flag | Required | Default | Description |
|---|---|---|---|
| `--video-id` | Conditional | `None` | YouTube Video ID (downloads section slice via `yt-dlp`) |
| `--video-path` | Conditional | `None` | Path to local video file (must provide either `--video-id` or `--video-path`) |
| `--range` | **Yes** | - | Target time range: `START-END` (`HH:MM:SS-HH:MM:SS`, `MM:SS-MM:SS`, or seconds) |
| `-o`, `--output` | No | stdout | Output file path for raw event lines |
| `--force-pos` | No | `auto` | Force overlay layout: `auto` (edge-density detection), `bottom-right`, or `left` |
| `--fps` | No | `0.25` | Sampling rate in frames per second (`0.25` = 1 frame every 4s) |
| `--workdir` | No | tempdir | Directory to retain temporary video slice and cropped frame images |

#### Downstream Alignment

The output file passed to `-o` contains tab-separated raw events that plug directly into [`align_live_chat.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts/align_live_chat.py):

```bash
python3 -X utf8 ../anibon-timestamper/scripts/align_live_chat.py \
  --events workspace/livechat_events.txt \
  --chunks workspace/chunks/ \
  -o workspace/livechat/
```

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
   - **Vlog & IRL Subculture Banter**:
     - Weeb Social Awkwardness ("ปู่เกร็ง", "แววตาสิ้นหวัง", "weeb เข้าสังคม", "Introvert อาการหนัก" = community banter about Boat's IRL shyness)
     - Booth / Food Navigators ("ไปบูธนี้ดิ", "ลองทาโกยากิร้านนั้น", "ข้างหลังมีคอสเพลย์..." = crowd steering)
     - Fan Sighting Celebrations ("เจอตัวจริงแล้ว", "ปู่หล่อมาก", "ขอลายเซ็นหน่อย" = real-time fan excitement)
     - Food Tasting Peer Pressure ("กินโชว์หน่อย", "เปย์เลย" = comedy encouragement)

Write each agent output to livechat_analysis_N.txt.

### 4. Synthesize LiveChat Report & Integrate Timestamps

Merge chunk outputs into livechat_summary.md and merge top hype peak timestamps into enriched_timestamps.txt before running pack_timestamps.py.

## Helper Scripts

| Script | Purpose |
|---|---|
| [`scripts/parse_live_chat.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/parse_live_chat.py) | Parse `.live_chat.json` to coarse chunks + raw event feed |
| [`scripts/extract_visual_livechat.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/extract_visual_livechat.py) | Extract burned-in on-screen livechat via Gemini vision proxy |
| [`scripts/visual_chat_crop.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/visual_chat_crop.py) | Calculate chat overlay ROI coordinates and FFmpeg crop filter |
| [`scripts/visual_chat_dedup.py`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-livechat-analysis/scripts/visual_chat_dedup.py) | Deduplicate scrolling messages across sampled frames into raw events |

