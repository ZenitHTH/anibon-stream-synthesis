# Anibon Stream Synthesis — Skills Index & Sitemap

This document lists all 18 skills available within the anibon-stream-synthesis plugin, categorized by their primary role in the pipeline.

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
- anibon-local-transcription — Renders local audio via whisper.cpp when YouTube captions are missing.
- whisper-corruption-recovery — Detects repetition loops in Whisper output and re-renders corrupt audio tails.
- masking-royal-news — Applies strict political metaphor masking for Thai news & royal references.
- cleaning-auto-transcripts — Normalizes Thai-Whisper garbled English loanwords.
- anibon-livechat-analysis — Parses YouTube LiveChat replays for SuperChats, meme peaks, and Q&As.
- livestream-scene-selection — Selects timeline boundaries for highlight editing.
- antigravity-vision-proxy — Inspects video frames via ffmpeg + view_file when vision ground truth is needed.
- edit-cut-video-ffmpeg — Frame-accurate video cutting, concatenating, and audio sync fixing.
- anibon-stream-synthesis-ffmpeg — Advanced FFmpeg editing skill for seamless narrative flows.

## 3. Utility & Synthesis Skills

Document creation, CLI tool building, and research utilities:

- synthesizing-knowledge — Synthesizes multi-source markdown research documents with citation links.
- building-reusable-cli-tools — Guidance for writing modular, testable Python processing utilities.
- writing-plugin-readme — Guidelines for writing professional README documentation.
