---
title: "prepare_video.py & lib/chunk/ (scripts/prepare_video.py)"
category: "engineering-script"
updated: "2026-11-21"
script_path: "scripts/prepare_video.py"
tags: ["python", "script", "preparation", "chunking", "transcript", "livechat", "pause"]
sources: []
status: "active"
---

# `prepare_video.py` & `lib/chunk/`

- **CLI Entrypoint**: [scripts/prepare_video.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py)
- **Chunk Package**: [lib/chunk/__init__.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/__init__.py) ([chunk_io.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/chunk_io.py), [parsers.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/parsers.py), [pause.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/pause.py), [state.py](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py))
- **Pipeline**: [[prep-first-full-context-48k]]
- **Related Scripts**: [[chunk-enrichment-py]], [[process-chunks-local-py]], [[update-garbled-dictionary-py]]

## Purpose & Responsibility
Initializes a stream workspace (`~/youtube_<video_id>_workspace` by default) during **Stage 1 Download & Chunking**. Downloads YouTube metadata, subtitles, optional storyboard MHTML slides, and optional live-chat replay; normalizes auto-generated transcripts against garbled-English rules; extracts music anchors; and writes overlapping 150-second transcript chunks into `chunks/`. The `lib/chunk/` package provides the shared I/O, timestamp parsing, worker checkpoint/pause signaling, and multimodal context loading utilities consumed across downstream stages.

## Key Functions & CLI Contracts

### `scripts/prepare_video.py`
- **CLI Arguments** ([prepare_video.py:110-164](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L110-L164)):
  - `url`: Positional YouTube video URL or video ID.
  - `--format` (`json` | `txt` | `xml`, default `json`): Output chunk serialization format.
  - `--block` (`int`, default `150`): Chunk window width in seconds (`2.5 min`).
  - `--overlap` (`int`, default `15`): Sliding window overlap in seconds.
  - `--vision`: Extract and annotate visual frames for ambiguous pronoun cues.
  - `--no-storyboard`: Skip downloading YouTube storyboard MHTML slides.
  - `--sub-langs` (default `DEFAULT_SUB_LANGS`): Subtitle language priority.
  - `--live-chat`: Download, parse, and align YouTube live-chat replay into `livechat/`.
  - `--keep-silent-chunks`: Emit placeholder chunk files even when a window has zero transcript items.
  - `--workspace` / `-o`: Custom target workspace path.
- `ChunkBuildOptions` ([prepare_video.py:45-51](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L45-L51)): Frozen dataclass holding `block`, `overlap`, and `fmt`.
- `_extract_and_save_anchors(cleaned, workspace)` ([prepare_video.py:33-42](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L33-L42)): Loads compiled replacements via `load_replacements()`, extracts `[เพลง]`/`[Music]` markers via `extract_and_clean_music_anchors()`, applies `clean_text()`, and writes `music_anchors.json` via `save_music_anchors()`.
- `_write_chunk_windows(workspace, opts, include_empty)` ([prepare_video.py:77-97](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L77-L97)): Computes `step = max(1, opts.block - opts.overlap)`, slices items in `[start, end)`, skips empty windows unless `include_empty[0]` is `True`, and delegates to `_write_single_chunk()` ([prepare_video.py:63-74](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L63-L74)).
- `chunk_transcript(...)` & `chunk_transcript_with_silent_windows(...)` ([prepare_video.py:100-107](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L100-L107)): Public helpers returning the number of chunk files written.

### `lib/chunk/` Helpers
- **`chunk_io.py`**:
  - `load_chunks(path)` ([chunk_io.py:21-42](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/chunk_io.py#L21-L42)) & `load_chunks_list(workspace_dir)` ([chunk_io.py:45-93](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/chunk_io.py#L45-L93)): Load JSON (preferred) or XML chunks sorted numerically by `chunk_sort_key()` ([chunk_io.py:132-137](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/chunk_io.py#L132-L137)).
  - `write_chunk_json` / `write_chunk_xml` / `write_chunk_txt` ([chunk_io.py:143-171](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/chunk_io.py#L143-L171)): Serialize chunks; `.txt` headers include `cutoff=HH:MM:SS` (`end_sec - overlap`).
- **`parsers.py`**:
  - `parse_timestamps(lines)` ([parsers.py:20-45](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/parsers.py#L20-L45)) & `parse_timestamp_line(line)` ([parsers.py:48-72](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/parsers.py#L48-L72)): Parse `HH:MM:SS - [Tag] Description` lines (defaulting missing tags to `"[Talk]"` in `parse_timestamp_line`) and sort chronologically by `sec`.
- **`pause.py`**:
  - Cooperative worker pause/resume via `.pause` (`PAUSE_FILENAME`, [pause.py:13](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/pause.py#L13)) and `timestamper.pid` (`PID_FILENAME`, [pause.py:14](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/pause.py#L14)).
  - `request_pause`, `clear_pause`, `write_worker_pid`, `remove_worker_pid`, `is_pid_alive`, `get_worker_status`, `wait_if_paused`, and `wait_for_pause_ack` ([pause.py:29-151](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/pause.py#L29-L151)).
- **`state.py`**:
  - `load_state` / `save_state` ([state.py:19-39](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L19-L39)): Persist checkpoints in `anibon_timestamper_state.json`.
  - `discover_chunks(workspace)` ([state.py:119-144](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L119-L144)): Prioritizes `chunk_*.txt`, falls back to `chunk_*.json` only if no `.txt` files exist (never mixing both).
  - `load_chunk_livechat`, `load_chunk_activity`, `load_chunk_enrichment`, `load_chunk_mood` ([state.py:42-116](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L42-L116)): Load per-chunk auxiliary files; `load_chunk_livechat()` prioritizes lines containing `"SUPERCHAT"`, `"ปู่"`, `"?"`, `"มั้ย"`, `"ไหม"`, `"ทำไม"`, or `"เกมอะไร"` when `max_lines > 0`.
  - `scrub_speaker_identity(text)` ([state.py:147-151](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L147-L151)) & `load_chunk_file(path, mappings)` ([state.py:194-204](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L194-L204)): Normalize speaker typos to `ปู่โบ๊ต` and apply transcript mappings while enforcing `cutoff` filtering on `.txt` chunks.

## Error Handling & Invariants
- **Workspace Persistence**: `main()` writes `.video_url` ([prepare_video.py:177](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/scripts/prepare_video.py#L177)) before downloading metadata/subtitles so downstream stages (`assembly.py`, `garbled_collector`) can recover the source URL.
- **No Mixed Chunk Formats**: `discover_chunks()` ([state.py:129-140](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/state.py#L129-L140)) strictly selects either `.txt` or `.json` and raises `FileNotFoundError` if `chunks/` is missing or empty.
- **PID Ownership Guard**: `remove_worker_pid()` ([pause.py:71-75](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/lib/chunk/pause.py#L71-L75)) only unlinks `timestamper.pid` if the stored PID matches the caller's PID.
- **Streamer Identity Invariant**: `scrub_speaker_identity()` deterministically enforces `ปู่โบ๊ต` on every chunk item loaded via `load_chunk_file()`.
