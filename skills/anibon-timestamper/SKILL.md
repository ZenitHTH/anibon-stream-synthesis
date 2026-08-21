---
name: anibon-timestamper
description: Use when generating detailed timestamps or topic summaries for long-form live streams and videos featuring speaker "Boat" (Pu Boat) from Anibon Official. This is the orchestrator skill.
---

# Anibon Timestamper (Orchestrator)

A routing skill for analyzing live stream transcripts to generate timestamps in YouTube format. Dynamically detects stream type and delegates to specialized sub-skills.

## When to Use

Streams or videos by "Boat" from Anibon Official that need timed topic labels.

## Sub-Skills & Permissions

**REQUIRED (first):** Load `preparing-tools` to verify dependencies (`yt-dlp`, `ffmpeg`, `python3`).
**REQUIRED (subagent execution):** Load `batching-subagents-concurrency` when running multi-subagent analysis (max 6 per batch turn, `Model: "flash"`). Ask user permission before downloading large external media or performing long web fetches.

Loaded by signal (add to prompt when needed):
- `anibon-world-identity` — verify game/char names against references before story stamps
- `anibon-local-transcription` — whisper.cpp fallback if YouTube has no captions
- `whisper-corruption-recovery` — recover transcript if repetition loops / corruption detected in Whisper output
- `anibon-livechat-analysis` — parse LiveChat replay so subagents can read the live from both sides (talker + chat)
- `antigravity-vision-proxy` — storyboard (sb0) frame inspection for ambiguous pronouns, game title verification, or unresolved garbled notes

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

Downstream of `align_live_chat.py`. Thai watchers mark laughter with `555...` / `xD` / `ฮา` / `ขำ`. A clustered burst in a short window = a meme/laugh peak. This is the only reliable laugh proxy when the autotranscript can't hear the streamer actually laughing. Emits per-chunk **mood verdicts + Thai tone guidance** that subagent prompts MUST weight when writing mood-bearing descriptions.

```bash
python3 -X utf8 scripts/analyze_555.py \
  --livechat ~/youtube_<id>_workspace/livechat/ \
  --index ~/youtube_<id>_workspace/livechat/livechat_index.json \
  --out ~/youtube_<id>_workspace/mood_555.json
```

Output: `mood_555.json` — dict chunk → `{density, n_markers, n_messages, peak_windows, pulse, mood, verdict, tone}`. The `tone` field carries Thai guidance (`tone` + suggested `verbs`) matched to the chunk's mood family. Verdicts:
- `*_PULSE` — burst passed the weighted score → mood-driven guidance. `MEME_PULSE` (funny), `CUTE_CUNNY_PULSE` (cute), `SHOCK_HYPE_PULSE` (hype), `DRAMA_NEWS_PULSE` (news/drama), `ANGRY_OUTRAGE_PULSE` (rant), etc.
- `HOT` / `WARM` — some markers, no burst → light banter / lively guidance
- `QUIET` — low chat, no burst → neutral, free verb choice

> [!NOTE]
> **Mood is guidance, not a rule.** The `tone`/`verbs` hint tells the subagent *which vibe the chat carried*; the AI still picks its own first verb from the situation. Only when a PULSE chunk gets timestamped as if the moment were flat does `validate_mood.py` (Step 11.5) remind the human.
>
> **Emoji Dictionary Reference**: Refer to [`references/anibon_emoji_dictionary.md`](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/references/anibon_emoji_dictionary.md) for complete channel-exclusive emote mapping (`:_CunnyBoat:`, `:_MonkeyBoat:`, `:_Nerd:`, `:_shutup:`, `:Grind:`, `:_Ripfish:`, `:_noname:`, `:_What:`, `:_WOW:`, `:_Ahh:`, `:_Meh:`, `:_MoneyBoat:`, `:_Tahaan:`, `:_KonDee:`, `:_NeoSlim:`, `:_Slim:`, `:_BoatSOM:`) and YouTube global emotes to mood pulse weights and safety masking triggers.

If a chunk is flagged `MEME_PULSE` but the subagent writes a flat, factual first-verb for it, that's the tone mismatch `validate_mood.py` (Step 11.5) surfaces for review.

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

> **Path convention:** every `best_file`/`matched_files` path in `knowledge.json` is **relative to the timestamper skill root**. `references/stream/*.md` = local to timestamper; `../anibon-world-identity/references/*.md` = world-identity skill; `../reference/*` = top-level data dir. Resolve all of them from the timestamper root, never from the current cwd.

> **Rarity = main idea**: `detect_signals.py` weights each matched keyword by inverse
> document frequency (`log(N/df)`). High-frequency (df high) words are daily-use filler
> and score 0 — ignored. Low-frequency (rare) words are the distinctive main idea.
> Hand `best_file` to a subagent only when `confidence` is clear; otherwise omit the knowledge file.

### 5.5 Load World-Identity (if signals match a game reference)

**Trigger:** `signals.json` `best_file`/`weighted_matched_files` resolves to a file under `../anibon-world-identity/references/` (i.e. post-cutoff game/char names). These names are the ones subagents hallucinate.

**Action:** Load the **`anibon-world-identity`** skill. It runs `references/INDEX.md` → cached story refs → reference SRT → websearch fallback to build a verified Thai-phoneme → EN name map. Bootstrap its game DBs first:

```bash
python3 ../anibon-world-identity/scripts/fetch_fgo_db.py --check --db "../reference/FGO and DATA/atlas_fgo.db" || \
  python3 ../anibon-world-identity/scripts/fetch_fgo_db.py --db "../reference/FGO and DATA/atlas_fgo.db"
python3 ../anibon-world-identity/scripts/fetch_ygo_db.py --check --db "../reference/Yu-Gi-Oh DATA/ygo_cards.db" || \
  python3 ../anibon-world-identity/scripts/fetch_ygo_db.py --db "../reference/Yu-Gi-Oh DATA/ygo_cards.db"
```

**Inject** the resolved name map into the Step 7 subagent prompts (any chunk whose signal matches one of these files) so `[Story]` stamps use canonical names, not phonetic guesses. Skip when stream covers well-known pre-cutoff content.

### 6. Detect Topic Boundaries (Optional)

For long streams with clear topic shifts. Run:

```bash
python3 -X utf8 scripts/detect_boundaries.py --chunks ~/youtube_<id>_workspace/chunks/ --signals ~/youtube_<id>_workspace/signals.json --output ~/youtube_<id>_workspace/boundaries.json
```

If boundaries look noisy, fall back to manual identification from `signals.json`: look for chunks where `matched_files` changes (e.g., gaming→Genshin→FGO). Note timestamps for `--break-at` in Step 9.

### 7. Spawn Subagents (Parallel)

Divide chunks into **groups of 4–5** (~20–25 min each). One **`anibon-chunk-timestamper`** per group.

> [!IMPORTANT]
> **Strict Concurrency Batching (Max 6 Subagents)**: To prevent API 429 `RESOURCE_EXHAUSTED` rate limits, NEVER spawn more than 6 subagents simultaneously. Launch subagents in controlled batches of **max 6 subagents per turn**, wait for all 6 to finish, and ONLY THEN launch the next batch of 6.
>
> **Use Flash Model Tier**: Always specify `Model: "flash"` when calling `invoke_subagent` for chunk timestampers to maximize speed and rate-limit headroom.

**Invoke pattern (one per group):**

```python
invoke_subagent(
    "anibon-chunk-timestamper",
    Model="flash",
    prompt=build_group_prompt(chunks[i:i+5])  # from references/subagent-prompt-template.md
)
```

Build each prompt from `references/subagent-prompt-template.md`. For each chunk in the group, inject:
- Chunk JSON content (agent reads sequentially — do NOT summarize chunks yourself)
- Per-chunk detection signals from `signals.json` (`best_file` + `primary_topic` + `confidence` + ranked `weighted_matched_files`)
- Per-chunk **LiveChat log** content (`livechat/livechat_chunk_NN.txt`) — inject when available, else `"no livechat available"`
- Per-chunk **mood verdict + tone guidance** from `mood_555.json` (if Step 3.7 ran) — inject the chunk's `tone`/`verbs` hint; the subagent keeps its own first-verb choice. If no mood file, omit.
- Knowledge file content for **`best_file` only** (verified against transcript by the subagent), plus lower-ranked files when `confidence` is ambiguous
- **PREVIOUS GROUP'S LAST TOPIC** — inject the final topic of the previous group so the agent applies continuity across group boundaries

**CRITICAL:** The agent reads chunks sequentially within its group and skips continuation chunks.
Do NOT inject your own topic summaries — inject signals data only.

Each `anibon-chunk-timestamper` returns plain-text timestamp lines (typically 2–4 per group).

### 8. Merge Timestamps

Write each subagent's output to its own file (e.g., `chunk_001.txt`, `chunk_002.txt`). Then merge + sort chronologically:

```bash
python3 scripts/merge_timestamps.py ~/youtube_<id>_workspace/chunk_*.txt \
  -o ~/youtube_<id>_workspace/all_timestamps.txt
```

### 8.5. Audit Gaps (MANDATORY before summarizer)

Enforces the **NO GAPS** iron rule. Run on the merged list; if it exits non-zero, spawn a fill agent for each flagged chunk (the tool prints the covering `chunk_NN` to re-run) and re-merge before Step 9.

```bash
python3 scripts/audit_gaps.py ~/youtube_<id>_workspace/all_timestamps.txt
# exit 0: no gaps. exit 1: prints e.g. "12m 01:13 -> 01:25 (fill around chunk_26)"
```

### 8.6 Collect Garbled Notes → Grow Dictionary (Automated)

Each chunk subagent emitted a `GARBLED_NOTES:` block (Step 3.5) for Thai-Latin hybrid words that survived cleaning. Extract them into `garbled_notes_raw/`, then automatically consolidate and sync into `resources/garbled_replacements.json`:

```bash
# 1. ALWAYS run dictionary updater to consolidate raw notes & generate garbled_notes.json on disk
python3 ../cleaning-auto-transcripts/scripts/update_garbled_dictionary.py \
  --from-raw-dir ~/youtube_<id>_workspace/garbled_notes_raw/ \
  --workspace ~/youtube_<id>_workspace
```

Optional: Spawn **`anibon-garbled-notes`** for deep LLM verification before writing. If spawned, save the returned JSON payload directly to `~/youtube_<id>_workspace/garbled_notes.json` and sync dictionary via `update_garbled_dictionary.py --sync-only`.

```python
invoke_subagent(
    "anibon-garbled-notes",
    prompt=(
        f"WORKSPACE: ~/youtube_<id>_workspace\n"
        f"PLUGIN_ROOT: <anibon-stream-synthesis plugin root>\n"
        f"Read garbled_notes_raw/*.txt, consolidate against raw_transcript.json + chunks/,\n"
        f"write garbled_notes.json, and run update_garbled_dictionary.py."
    )
)
```

Outputs:
- `~/youtube_<id>_workspace/garbled_notes.json` — all candidates (`garbled`, `correct` or `null`, `chunk`, `ts`, `context`)
- `resources/garbled_replacements.json` — auto-synced across root and skill resources with canonical grouped mappings (`TargetWord: [patterns...]`)

> [!TIP]
> **Vision Escalation Gate**: When audio is ambiguous (deictic "เกมนี้", ASR phonetics corrupted, or candidate `correct: null`), load `antigravity-vision-proxy` to download storyboard `sb0` (~15MB) and inspect exact timestamp frames. Never guess or hallucinate foreign titles when visual ground truth is available. If visually confirmed, undubt the candidate and set `correct: <CanonicalName>` before concluding. Only leave `correct: null` for items with no visual presence on screen.

The dictionary is shared (`resource_path()` walks up to plugin root), so every future stream
auto-loads the new rules. Truly unresolved proper nouns are left `correct: null` for human confirmation.

### 9. Final Assembly — `anibon-summarizer` (Replaces wrap + pack)

Pass the full sorted `all_timestamps.txt` to the **`anibon-summarizer`** subagent. It deduplicates cross-chunk overlaps, groups by topic coherence, enforces the 3,500-byte YouTube cap, writes caveman part headings, and produces the final markdown.

```python
with open("all_timestamps.txt") as f:
    merged = f.read()

invoke_subagent(
    "anibon-summarizer",
    prompt=f"TIMESTAMPS:\n{merged}"
)
```

The subagent outputs the complete `output.md` directly. Save it to `~/youtube_<id>_workspace/output.md`.

> [!NOTE]
> `pack_timestamps.py` is still available for offline/scripted runs or when the subagent cannot be invoked. In interactive orchestrator sessions, always prefer `anibon-summarizer` — it applies semantic deduplication that the script cannot.

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

Companion to `analyze_555.py`. Labels each timestamp with its chunk's **mood + Thai tone guidance** (the verbs the AI may draw from). Guidance-only — it never rejects a verb; the AI's verb creativity stays free. Report-only; exit 0. Use it to review whether a PULSE-span stamp actually carried the chunk's energy.

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
| `scripts/audit_gaps.py` | Gap audit (NO GAPS rule) + gap→chunk mapping (Step 8.5) |
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

- **Use named agents** — Step 7 MUST use `invoke_subagent("anibon-chunk-timestamper")` per chunk. Step 8.6 MUST use `invoke_subagent("anibon-garbled-notes")`. Step 9 MUST use `invoke_subagent("anibon-summarizer")`. Never substitute a generic Task/self agent.
- **STRICT SUBAGENT BATCHING (MAX 6)** — Never launch more than 6 subagents simultaneously. Process in batches of 6, wait for completion, then proceed to the next batch.
- **FLASH MODEL TIER FOR CHUNKS** — Use `Model: "flash"` for chunk timestamper subagents to ensure fast execution and avoid API rate limits.
- **NO HEURISTIC / REGEX FALLBACKS** — Never fall back to heuristic text-generation scripts if subagents hit errors or rate limits. All timestamps MUST be generated by authentic `anibon-chunk-timestamper` subagent runs reading real transcript XML and LiveChat logs.
- **Use detect_signals.py** — TF-IDF only. No ad-hoc grep/inline scanning.
- **Don't read chunks yourself** — subagents read XML. Inject signals.json data into prompts.
- **ONE FILE** — single `.md` with `═══` section blocks. No `part1.md`.
- **NO GAPS** — max 10 min between timestamps unless verified silent.
- **INTRO BREAKDOWN** — intro >10 min → break into 3-5 min sub-topic milestones.
- **NO AD-HOC TIMESTAMPS** — only via subagent pipeline → `merge_timestamps.py` → `anibon-summarizer`.
- **READ BOTH SIDES** — subagents must read the ENTIRE transcript chunk AND its LiveChat log (when present) before writing any timestamp. Situation + emotion come from both talks and chat, never from `primary_topic` alone.
- **HONOUR THE MOOD VERDICT** — when `mood_555.json` exists, inject each chunk's `tone` guidance (mood + suggested verbs) into the subagent prompt. The AI keeps its own first-verb choice, but must not flatline a chat-laugh/hype peak into a calm factual verb.
- **NON-SPOILER GACHA POLICY** — Never spoil whether the streamer won or lost a gacha pull in the timestamp description. Focus on anticipation, the featured banner/character, and chat interactions.
- **18+ / RULE 34 TONE INTEGRITY** — Do not trivialize adult fanart or Rule 34 commentary under generic comedic tags (`[Reaction] ฮา...`). Use `[Talk]` with mature, direct, and accurate summaries.
- **PROPER NOUN & GAME TITLE INTEGRITY** — When processing garbled notes (Step 8.6), NEVER map legitimate external game titles (e.g. *MARVEL Tōkon: Fighting Souls*, *Alien: Isolation*, *TMNT: The Last Ronin*), brand names, or common English phrases (e.g. *where we meet*) as noise patterns. Unconfirmed proper nouns must remain `correct: null` for human review rather than being forced into generic Thai terms.

