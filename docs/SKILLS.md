# Anibon Stream Synthesis — Skills Index & Sitemap

This document lists all 20 skills available within the anibon-stream-synthesis plugin, categorized by their primary role in the pipeline.

## 1. Orchestrator Skills

Master skills that direct overall execution, chunking, and parallel subagent dispatch:

- anibon-timestamper — Master orchestrator for generating YouTube timestamps for Pu Boat live streams.
- anibon-timestamper-local — Sequential local LLM edition for running timestamps without cloud context.
- youtube-minutes-synthesis — Generates meeting-minutes style summaries and timestamp overviews.
- creating-highlight-video — Master orchestrator for creating highlight reels from streams.

## 2. Sub-Skills & Handlers (Loaded Dynamically)

Specialized handlers loaded by signal triggers or fallback logic:

- preparing-tools — Verifies system CLI dependencies (yt-dlp, ffmpeg, python3).
- anibon-world-identity — Verifies game lore, character names, and card names against FGO/YGO DBs.
- anibon-stream-activity — High-res storyboard sampling for on-screen gameplay, webcam presence/AFK, and visual grounding.
- anibon-local-transcription — Renders local audio via whisper.cpp when YouTube captions are missing.
- whisper-corruption-recovery — Detects repetition loops in Whisper output and re-renders corrupt audio tails.
- masking-royal-news — Applies strict political metaphor masking for Thai news & royal references.
- cleaning-auto-transcripts — Normalizes Thai-Whisper garbled English loanwords.
- anibon-livechat-analysis — Parses YouTube LiveChat replays for SuperChats, meme peaks, and Q&As.
- livestream-scene-selection — Selects timeline boundaries for highlight editing.
- antigravity-vision-proxy — Inspects video frames via ffmpeg + view_file when vision ground truth is needed.
- anibon-stream-activity — Tracks on-screen game activity and webcam presence for visual grounding during timestamping.
- verifying-stream-ground-truth — Extracts targeted video frames to verify disputed numbers, campaign banners, and proper nouns that ASR misspeaks.
- edit-cut-video-ffmpeg — Frame-accurate video cutting, concatenating, and audio sync fixing.
- anibon-stream-synthesis-ffmpeg — Advanced FFmpeg editing skill for seamless narrative flows.
- batching-subagents-concurrency — Rate-limit-safe parallel subagent dispatch (MAX 6 concurrent batches).

## 3. Utility & Synthesis Skills

Document creation, CLI tool building, and research utilities:

- synthesizing-knowledge — Synthesizes multi-source markdown research documents with citation links.
- building-reusable-cli-tools — Guidance for writing modular, testable Python processing utilities.
- writing-plugin-readme — Guidelines for writing professional README documentation.

## 4. Named Subagents (Wired into the timestamper pipeline)

First-class subagents that the orchestrator invokes by name — never generic Task/self agents:

- `anibon-chunk-timestamper` — One per chunk-group (4–5 chunks). Reads transcript XML + LiveChat log, writes timestamps, emits `GARBLED_NOTES:` blocks for surviving Thai-Latin hybrids.
- `anibon-garbled-notes` — One per stream, after merge. Consolidates `GARBLED_NOTES` blocks, writes `garbled_notes.json`, appends confirmed rules to `garbled_replacements.json`.
- `anibon-summarizer` — One per stream. Deduplicates cross-chunk overlaps, groups by activity period, packs into byte-limited parts, writes the final markdown.
