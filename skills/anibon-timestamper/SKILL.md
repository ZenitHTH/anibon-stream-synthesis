---
name: anibon-timestamper
description: Use when generating detailed timestamps or topic summaries for long-form live streams and videos featuring speaker "Boat" (Pu Boat) from Anibon Official. This is the orchestrator skill.
---

# Anibon Timestamper (Orchestrator)

A routing skill for analyzing live stream transcripts to generate timestamps in YouTube format. Dynamically detects stream type and delegates to specialized sub-skills.

## When to Use

Streams or videos by "Boat" from Anibon Official that need timed topic labels.

## Sub-Skills

**REQUIRED (first):** Load `preparing-tools` to verify dependencies (`yt-dlp`, `ffmpeg`, `python3`).

Loaded by signal (add to prompt when needed):
- `anibon-world-identity` — verify game/char names against references before story stamps
- `anibon-local-transcription` — whisper.cpp fallback if YouTube has no captions
- `whisper-corruption-recovery` — recover transcript if repetition loops / corruption detected in Whisper output
- `anibon-livechat-analysis` — parse LiveChat replay so subagents can read the live from both sides (talker + chat)

## Pipeline (Linear, Top-to-Bottom)

All paths relative to the skill root directory (`skills/anibon-timestamper/`).

### 0. Environment

`scripts/` directory contains all helper scripts. Run `<script>.py --help` for flags.
Store working files in `youtube_<video_id>_workspace/`.

### 1. Initialize

Ask output language. Verify channel and speaker nicknames against `resources/channels.json`:
- **Own Channel**: `Anibon Official` (`@anibonofficial`)
- **Primary Speaker**: `Boat` / `Pu Boat` (`ปู่โบ๊ต` / `PhuBoat` / `โบ๊ต`)

Ensure transcript speaker attribution maps to `own_channel` nicknames before continuing.


### 2. Prepare Video

```bash
python3 -X utf8 scripts/prepare_video.py "URL" --format xml --block 300 --overlap 30
# Talk-heavy → --block 600 --overlap 60
```

Downloads transcript, creates `<workspace>/chunks/chunk_*.xml`.

> [!IMPORTANT]
> **Check Corruption**: If transcript is from local Whisper transcription (or audio ≥2h), verify tail entries for repetition loops. If corruption found (>0.5 match ratio), load `whisper-corruption-recovery` skill to split, re-run corrupted tail segment, and dedup-merge before chunking.

### 3. Clean Transcript (Optional)

Normalizes Thai-Whisper garbled English before signal detection. The script lives in the `cleaning-auto-transcripts` skill — resolve from the timestamper skill root.

```bash
python3 -X utf8 ../cleaning-auto-transcripts/scripts/clean_garbled_english.py --chunks ~/youtube_<id>_workspace/chunks/
```

### 3.5 Download & Align LiveChat (Optional but preferred)

Gives each subagent the watchers' chat for its own chunk, so situation + emotion are read from BOTH talks and chat. Requires network; if a VOD has no `live_chat` subtitle, skip this step and rely on transcript-only emotion.

```bash
# 1. Download LiveChat replay (network required)
yt-dlp --sub-langs live_chat --write-sub --skip-download "https://www.youtube.com/watch?v=<VIDEO_ID>" -o "<workspace>/%(id)s.%(ext)s"
# 2. Parse to coarse chunks + a seconds-prefixed raw event feed
python3 -X utf8 ../anibon-livechat-analysis/scripts/parse_live_chat.py <workspace>/<id>.live_chat.json --chunk-minutes 90 --raw-events <workspace>/livechat_events.txt -o <workspace>/livechat_90/
# 3. Align raw feed to transcript chunk windows
python3 -X utf8 scripts/align_live_chat.py --events <workspace>/livechat_events.txt --chunks <workspace>/chunks/ -o <workspace>/livechat/
```

Output: `livechat/livechat_chunk_NN.txt` (per transcript chunk) + `livechat/livechat_index.json`. If `yt-dlp` reports no `live_chat` subtitles, continue — the subagent falls back to transcript-only.

### 3.7 Detect Thai-Laugh / Meme Pulses (Optional but preferred)

Downstream of `align_live_chat.py`. Thai watchers mark laughter with `555...` / `xD` / `ฮา` / `ขำ`. A clustered burst in a short window = a meme/laugh peak. This is the only reliable laugh proxy when the autotranscript can't hear the streamer actually laughing. Emits per-chunk mood verdicts that subagent prompts MUST weight when writing mood-bearing descriptions.

```bash
python3 -X utf8 scripts/analyze_555.py \
  --livechat ~/youtube_<id>_workspace/livechat/ \
  --index ~/youtube_<id>_workspace/livechat/livechat_index.json \
  --out ~/youtube_<id>_workspace/mood_555.json
```

Output: `mood_555.json` — dict chunk → `{density, n_markers, n_messages, peak_windows, mood, verdict}`. Verdicts:
- `QUIET` — low chat, no burst → neutral mood, normal sampling
- `MEME_PULSE` — strong burst (count ≥ pulse) → funny/meme mood: laugh first-verb
- `WARM` — some markers, no burst → light banter, optional laugh verb

> [!NOTE]
> **Emoji Dictionary Reference**: Refer to [`references/anibon_emoji_dictionary.md`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/references/anibon_emoji_dictionary.md) for complete channel-exclusive emote mapping (`:_CunnyBoat:`, `:_MonkeyBoat:`, `:_Nerd:`, `:_shutup:`, `:Grind:`, `:_Ripfish:`, `:_noname:`, `:_What:`, `:_WOW:`, `:_Ahh:`, `:_Meh:`, `:_MoneyBoat:`, `:_Tahaan:`, `:_KonDee:`, `:_NeoSlim:`, `:_Slim:`, `:_BoatSOM:`) and YouTube global emotes to mood pulse weights and safety masking triggers.

If a chunk is flagged `MEME_PULSE` but the subagent writes a flat, factual first-verb for it, that's the bug `validate_mood.py` (Step 11.5) catches.

### 4. Analyze (Pre-flight)

Quick summary of chunk categories, gaps, byte sizes. Note: On Windows, use `-X utf8` to avoid console `UnicodeEncodeError`.

```bash
python3 -X utf8 scripts/anibon-analyzer.py ~/youtube_<id>_workspace/
```

### 5. Detect Signals → Match Knowledge Files

TF-IDF across all chunks. Matches keywords to knowledge files per chunk.

```bash
python3 -X utf8 scripts/detect_signals.py \
  --chunks ~/youtube_<id>_workspace/chunks/ \
  --knowledge ./resources/knowledge.json \
  --output ~/youtube_<id>_workspace/signals.json
```

Output: `signals.json` — per-chunk weighted signal: `matched_files` (with `df`/`weight`), `weighted_matched_files` (ranked), `best_file`, `primary_topic`, `confidence`.

> **Rarity = main idea**: `detect_signals.py` weights each matched keyword by inverse
> document frequency (`log(N/df)`). High-frequency (df high) words are daily-use filler
> and score 0 — ignored. Low-frequency (rare) words are the distinctive main idea.
> Hand `best_file` to a subagent only when `confidence` is clear; otherwise omit the knowledge file.

### 6. Detect Topic Boundaries (Optional)

For long streams with clear topic shifts. Run:

```bash
python3 -X utf8 scripts/detect_boundaries.py --chunks ~/youtube_<id>_workspace/chunks/ --signals ~/youtube_<id>_workspace/signals.json --output ~/youtube_<id>_workspace/boundaries.json
```

If boundaries look noisy, fall back to manual identification from `signals.json`: look for chunks where `matched_files` changes (e.g., gaming→Genshin→FGO). Note timestamps for `--break-at` in Step 9.

### 7. Spawn Subagents (Parallel)

Divide chunks into groups of 4-5 (40-50 min each). One Task agent per group.

> [!IMPORTANT]
> **Pre-Grant Workspace Permissions**: Before spawning subagents, call `ask_permission` for `read_file` on `<workspace>` so background subagents do not time out waiting for permission prompts when accessing transcript XML files or `signals.json`.

**Each subagent prompt MUST contain:**
- Chunk file paths (agent reads XML directly — do NOT read chunks yourself)
- Per-chunk detection signals from `signals.json` (inject `best_file` + `primary_topic` + `confidence` + ranked `weighted_matched_files`; keep `matched_files`/`signal_score` for back-compat)
- Per-chunk **LiveChat log** content (`livechat/livechat_chunk_NN.txt`) — inject when available, else "no livechat available"
- Per-chunk **mood verdict** from `mood_555.json` (if Step 3.7 ran) — a `MEME_PULSE` chunk MUST use a Thai laugh/banter first-verb, never a flat factual verb. Tuple as "mood_555: <verdict>" per chunk. If no mood file, omit.
- The `references/subagent-prompt-template.md` output contract (0-2 stamps per chunk, merge same topic → 0)
- Knowledge file content for the **`best_file` only** (verified against transcript by the subagent), plus lower-ranked files as context when `confidence` is ambiguous

**CRITICAL:** Do NOT write topic descriptions yourself. Let the agent read the XML + signals. Inject signals.json data, not your analysis. Do NOT force-feed every matched file — the subagent must confirm the dominant topic before naming it.

Each agent returns timestamps as plain text lines.

### 8. Merge Timestamps

Write each agent's output to its own file (e.g., `agent_1.txt`, `agent_2.txt`). Then merge + sort chronologically:

```bash
python3 scripts/merge_timestamps.py ~/youtube_<id>_workspace/agent_*.txt \
  -o ~/youtube_<id>_workspace/all_timestamps.txt
```

### 8.5 Wrap Same-Topic Timestamps (Fixes duplicate stamps)

`merge_timestamps.py` only collapses byte-identical or same-second+near-identical lines. Real runs still ship **30-40 same-topic duplicates** (same event/same subject stamped twice 0-120s apart, e.g. `00:11:40` + `00:11:41` both "gacha revenue"). Fix with a semantic wrap pass before packing:

1. Read `all_timestamps.txt` fully.
2. Wrap consecutive timestamps that describe the **SAME single topic** (same event, same discussion thread, same subject) and occur **close in time** (typically ≤~2 min) into ONE line.
3. KEEP the **earliest** timestamp's time. Prefer the most specific tag/description; merge descriptions into one concise line. When the later line is more informative, carry its wording — don't blindly keep the first verbatim.

Rules for what counts as SAME topic (merge): same gacha-revenue news stamped twice; a `[Reaction]`+`[Reaction]` on the same ad; `[WatchParty]`+`[Reaction]` on the same PV just watched; `[Gameplay]`+`[Talk]` on the same skill review; `[Chat]`+`[Donation]` answering the same viewer question.

**DO NOT merge** (different topics even if same-second/nearby): a `[Gameplay]` analysis and a `[Gacha]` banner analysis at the same second; two different games; a boss fight vs. a donation read; distinct questions in a Q&A. Same timestamp ≠ same topic.

Expected: this collapses ~20-25% of lines on a typical run without losing distinct events.

> [!TIP]
> Reuse the target contract in `references/subagent-prompt-template.md` ("## Wrap Same-Topic Timestamps"). Run once per whole `all_timestamps.txt` (not per chunk — cross-chunk dupes are the point).

### 9. Pack into Sections

Split into byte-limited sections (YouTube comment cap ~3500B). Use `--topic-json` with `boundaries.json` from Step 6 for section headings + forced topic splits.

> [!IMPORTANT]
> **Topic Group Section Headers**: Section header titles synthesized by `pack_timestamps.py` represent the overall topic group across all entries in that section (e.g., `Topic A | Topic B | Topic C`), never just the first line.
>
> **Verify & Refine Section Header Titles**: Never leave generic placeholder section titles (such as `fgo knowledge base` or `gaming-stream`) in `output.md`. If `pack_timestamps.py` outputs generic titles, inspect the timestamps within each section and replace the header title with a concise summary of the primary topics in that part (e.g., `ส่วนที่ N: Topic A & Topic B (⏱ เริ่ม: HH:MM:SS)`).
>
> **Granular High-Meme & Streamer-Chat Synergy**: When analyzing peak trolling, meme sequences, or clutch gameplay (e.g., 15 HP survivals, low-star unit runs, streamer x livechat donation banter), increase timestamp density from standard 5-minute sampling to **1-2 minute micro-timestamps** to capture precise dialogue quotes and live chat reactions.
>
> **Section Time-Range Balancing**: Aim for broad, evenly distributed section time ranges (e.g., 1h to 1h30m per part on multi-hour streams). Avoid creating narrow section fragments (<40 minutes). If forced topic boundaries create narrow parts, re-pack timestamps without rigid boundary json to achieve smooth byte-and-time balancing.

```bash
python3 -X utf8 scripts/pack_timestamps.py ~/youtube_<id>_workspace/all_timestamps.txt \
  --topic-json ~/youtube_<id>_workspace/boundaries.json \
  --title "Video Title | ANIBON" \
  -o ~/youtube_<id>_workspace/output.md
```

### 10. Validate Sections

```bash
python3 scripts/check_sections.py ~/youtube_<id>_workspace/output.md
```

Checks: byte cap per section ✅, no ASR garbled patterns.

### 11. Validate Topic Coherence (Optional)

Cross-references timestamp game names against `signals.json` ground truth. Flags fabricated names or topic bleed between parts.

```bash
python3 scripts/validate_part_coherence.py ~/youtube_<id>_workspace/output.md \
  --signals ~/youtube_<id>_workspace/signals.json \
  --chunks ~/youtube_<id>_workspace/chunks/
```

### 11.5 Validate Mood vs Chat Pulse (Optional)

Companion to `analyze_555.py`. Checks the generated timestamps actually honour the `mood_555.json` verdicts — i.e. no `MEME_PULSE` chunk got timestamped with a flat, factual first-verb (the streamer was joking, the transcript flatlined it). Report-only; exit 0. Fix any flat/mismatched stamps by hand before posting.

```bash
python3 scripts/validate_mood.py \
  --timestamps ~/youtube_<id>_workspace/all_timestamps.txt \
  --mood ~/youtube_<id>_workspace/mood_555.json \
  --livechat ~/youtube_<id>_workspace/livechat/ \
  --index ~/youtube_<id>_workspace/livechat/livechat_index.json
```

## Output Format

Single `.md` file with `═══` section blocks:

```
# Title | ANIBON

═════════════════════════════════════════════════════
 Part 1: Section Header (⏱ เริ่ม: HH:MM:SS)
═════════════════════════════════════════════════════
HH:MM:SS - [Tag] Description
...

═════════════════════════════════════════════════════
 Part 2: Section Header (⏱ เริ่ม: HH:MM:SS)
═════════════════════════════════════════════════════
...
```

## Helper Scripts

| Script | Purpose |
|--------|---------|
| `scripts/prepare_video.py` | Download + clean + chunk |
| `scripts/dump_chunk_text.py` | Dump clean formatted text from XML chunks for subagents |
| `scripts/anibon-analyzer.py` | Pre-flight: gaps, categories, byte sizes |
| `scripts/detect_signals.py` | TF-IDF signal + knowledge file matching |
| `scripts/detect_boundaries.py` | Detect topic boundaries (feeds `--topic-json` in Step 9) |
| `scripts/align_live_chat.py` | Slice LiveChat event feed to per-transcript-chunk logs (Step 3.5) |
| `scripts/analyze_555.py` | Detect Thai-laugh/meme pulses from aligned LiveChat → per-chunk mood verdict (Step 3.7) |
| `scripts/validate_mood.py` | Verify mood-bearing timestamps honour mood_555 verdicts (Step 11.5) |
| `../anibon-livechat-analysis/scripts/parse_live_chat.py` | Parse `.live_chat.json` to event feed (Step 3.5) |
| `scripts/merge_timestamps.py` | Combine + sort subagent outputs |
| `scripts/pack_timestamps.py` | Byte-limited section packing (supports `--break-at`, `--topic-json`) |
| `scripts/check_sections.py` | Validate byte cap + ASR garbles |
| `scripts/validate_part_coherence.py` | Cross-reference game names vs signals |
| `scripts/validate_tags.py` | Validate timestamp tag vocabulary |
| `../cleaning-auto-transcripts/scripts/clean_garbled_english.py` | Normalize Thai-Whisper garbled English (Step 3) |
| `../cleaning-auto-transcripts/scripts/clean_transcript.py` | Raw json3 cleaner (called by prepare_video) |
| `../anibon-world-identity/scripts/fetch_story_ref.py` | Fetch/cache story synopses (user consent for websearch) |
| `../anibon-world-identity/scripts/align_ref_timeline.py` | Align reference SRT timestamps with chunks |
| `../anibon-world-identity/scripts/fetch_fgo_db.py`, `fetch_ygo_db.py` | Build card databases (World Identity) |

## Iron Rules

- **Use detect_signals.py** — TF-IDF only. No ad-hoc grep/inline scanning.
- **Don't read chunks yourself** — subagents read XML. Inject signals.json data into prompts.
- **ONE FILE** — single `.md` with `═══` section blocks. No `part1.md`.
- **NO GAPS** — max 10 min between timestamps unless verified silent.
- **INTRO BREAKDOWN** — intro >10 min → break into 3-5 min sub-topic milestones.
- **NO AD-HOC TIMESTAMPS** — only via subagent pipeline → `merge_timestamps.py` → `pack_timestamps.py`.
- **READ BOTH SIDES** — subagents must read the ENTIRE transcript chunk AND its LiveChat log (when present) before writing any timestamp. Situation + emotion come from both talks and chat, never from `primary_topic` alone.
- **HONOUR THE MOOD VERDICT** — when `mood_555.json` exists, a `MEME_PULSE` chunk must open with a Thai laugh/banter first-verb (แซว/ฮา/ขำ). Never flatline a chat-laugh peak into a factual verb.
